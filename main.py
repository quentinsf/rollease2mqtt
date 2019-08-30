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
log.setLevel(logging.DEBUG)

async def monitor_mqtt_requests(hub, mqtt_client):
    # Subscribe to mqtt topics for motors

    await mqtt_client.subscribe([
        (f'{MQTT_TOPIC_ROOT}/{motor_addr}/#', QOS_1) for motor_addr in hub.motors
    ])

    while True:
        log.debug("Waiting for MQTT messages")

        # wait for an MQTT message on our topics
        message = await mqtt_client.deliver_message()
        packet = message.publish_packet
        topic = packet.variable_header.topic_name
        payload = packet.payload.data.decode()

        log.info("MQTT received %s => %s", topic, payload)
        if topic.startswith(MQTT_TOPIC_ROOT):
            motor, subtopic = topic[len(MQTT_TOPIC_ROOT)+1:].split('/')
            log.info(f"  motor {motor} subtopic {subtopic}")
            if motor in hub.motors:
                if subtopic == MQTT_COMMAND_TOPIC:
                    if payload == "CLOSE":
                        await hub.motors[motor].request_close()
                    elif payload == "OPEN":
                        await hub.motors[motor].request_open()
                    elif payload == "STOP":
                        await hub.motors[motor].request_stop()
            else:
                log.warning("Request for unknown motor {motor}")
        else:
            log.error("Topic not under expected topic root")


async def update_mqtt_positions(hub, mqtt_client):
    while True:
        await asyncio.sleep(5)

        for motor_addr in hub.motors:
            position = str(hub.motors[motor_addr].travel_pc).encode()
            topic = f"{MQTT_TOPIC_ROOT}/{motor_addr}/{MQTT_POSITION_TOPIC}"
            log.debug("Sending position %s to topic %s", position, topic)
            message = await mqtt_client.publish( topic, position )


async def main():

    mqtt_client = MQTTClient(client_id="rollease2mqtt")
    await mqtt_client.connect(MQTT_URL)

    conn = rollease.AcmedaConnection(device=DEVICE, timeout=3)

    await conn.request_hub_info()
    
    await asyncio.sleep(8)
    hub_addr, hub = next(iter(conn.hubs.items()))
    
    asyncio.create_task(update_mqtt_positions(hub, mqtt_client))
    asyncio.create_task(monitor_mqtt_requests(hub, mqtt_client))

    while True:
        log.info("rollease2mqtt alive and waiiting")
        await asyncio.sleep(300)

asyncio.run(main())
