#! /usr/bin/env python3
#
# Experiments with talking to Rollease Acmeda hub over RS485.
# Not very tidy yet.
#
# Requires Python 3.7 or later

import asyncio
import rollease
import logging
import sys
import time
from hbmqtt.client import MQTTClient, ClientException
from hbmqtt.mqtt.constants import QOS_1, QOS_2

from typing import Optional, Tuple, List, Dict

DEVICE = "/dev/serial/by-id/usb-Silicon_Labs_CP2104_USB_to_UART_Bridge_Controller_018DF044-if00-port0"
MQTT_URL = "mqtt://hassio-mqtt:9qaHD6@192.168.0.31"
MQTT_TOPIC_ROOT = "home-assistant/cover"  # followed by /motor_addr/command
MQTT_COMMAND_TOPIC = "set"
MQTT_POSITION_TOPIC = "position"
MQTT_SET_POSITION_TOPIC = "set_position"

logging.basicConfig()
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

async def monitor_mqtt_requests(hub, mqtt_client):
    # Subscribe to mqtt topics for motors

    await mqtt_client.subscribe(
        [
            (f'{MQTT_TOPIC_ROOT}/{motor_addr}/{MQTT_COMMAND_TOPIC}', QOS_1) for motor_addr in hub.motors
        ] + [
            (f'{MQTT_TOPIC_ROOT}/{motor_addr}/{MQTT_SET_POSITION_TOPIC}', QOS_1) for motor_addr in hub.motors
        ]

    )

    while True:
        log.debug("Waiting for MQTT messages")

        # wait for an MQTT message on our topics
        message = await mqtt_client.deliver_message()
        packet = message.publish_packet
        topic = packet.variable_header.topic_name
        payload = packet.payload.data.decode()

        log.info("MQTT received %s => %s", topic, payload)
        if topic.startswith(MQTT_TOPIC_ROOT):
            motor_addr, subtopic = topic[len(MQTT_TOPIC_ROOT)+1:].split('/')
            log.info(f"  motor {motor_addr} subtopic {subtopic}")
            if motor_addr in hub.motors:
                motor = hub.motors[motor_addr]
                if subtopic == MQTT_COMMAND_TOPIC:
                    if payload == "CLOSE":
                        await motor.request_close()
                    elif payload == "OPEN":
                        await motor.request_open()
                    elif payload == "STOP":
                        await motor.request_stop()
                elif subtopic == MQTT_SET_POSITION_TOPIC:
                    await motor.request_move_percent(int(payload))
                else:
                    log.warning("Unexpected topic: %s, payload %s", topic, payload)
            else:
                log.warning("Request for unknown motor {motor}")
        else:
            log.error("Topic not under expected topic root")


async def update_mqtt_positions(hub, mqtt_client):
    # Update the positions once per minute
    while True:
        await asyncio.sleep(60)

        for motor_addr in hub.motors:
            travel_pc = hub.motors[motor_addr].travel_pc
            if travel_pc is not None:
                position = str(travel_pc).encode()
                topic = f"{MQTT_TOPIC_ROOT}/{motor_addr}/{MQTT_POSITION_TOPIC}"
                log.debug("  Sending position %s to topic %s", position, topic)
                message = await mqtt_client.publish( topic, position )


async def main():

    mqtt_client = MQTTClient(client_id="rollease2mqtt")
    await mqtt_client.connect(MQTT_URL)

    async def update_callback(hub: rollease.Hub, motor: rollease.Motor):
        travel_pc = motor.travel_pc
        if travel_pc is not None:
            position = str(travel_pc).encode()
            topic = f"{MQTT_TOPIC_ROOT}/{motor.addr}/{MQTT_POSITION_TOPIC}"
            log.debug("Sending updated position %s to topic %s", position, topic)
            message = await mqtt_client.publish( topic, position )

    conn = rollease.AcmedaConnection(device=DEVICE, callback=update_callback)
    await conn.request_hub_info()
    
    await asyncio.sleep(8)
    hub_addr, hub = next(iter(conn.hubs.items()))
    
    asyncio.create_task(update_mqtt_positions(hub, mqtt_client))
    asyncio.create_task(monitor_mqtt_requests(hub, mqtt_client))


    while True:
        log.info("rollease2mqtt alive and waiting")
        await asyncio.sleep(300)

asyncio.run(main())
