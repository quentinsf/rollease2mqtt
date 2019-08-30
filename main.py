#! /usr/bin/env python3
#
# Experiments with talking to Rollease Acmeda hub over RS485
# Requires Python 3.6 or later

import asyncio
import logging
import aioserial
import re
import serial
import sys
import time

from typing import Optional, Tuple, List, Dict

DEVICE = "/dev/serial/by-id/usb-Silicon_Labs_CP2104_USB_to_UART_Bridge_Controller_018DF044-if00-port0"

logging.basicConfig()
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

# Things that might go wrong:

class Error(Exception):
    pass

class FormatError(Error):
    pass

class TimeoutError(Error):
    pass

class Hub:
    def __init__(self, conn: "AcmedaConnection", addr: str):
        """
        Create a new hub and ask it to send its motor info
        """
        log.info(f"Registering hub {addr}")
        self.conn = conn
        self.addr = addr
        self.motors: Dict[str, "Motor"] = {}
        log.info(f"Requesting motor info for hub {addr}")
        asyncio.create_task(self.request_motor_info())

    def __str__(self):
        return f"Hub {self.addr}"

    async def request_motor_info(self, motor="000", cmd="v", data="?"):
        await self.conn.send_motor_cmd(self.addr, motor, cmd, data)

    def register_motor(self, addr):
        if addr in self.motors:
            return
        self.motors[addr] = Motor(self, addr)

    def parse_motor_info(
        self, info: str
    ) -> Tuple[str, Optional[str], Optional[str]]:
        motor_addr = info[:3]
        command, remainder = None, None
        if len(info) > 3:
            command = info[3]
        if len(info) > 4:
            remainder = info[4:]
        return motor_addr, command, remainder

    def handle_motor_info(self, resp: str):
        motor_addr, command, remainder = self.parse_motor_info(resp)
        if motor_addr not in self.motors:
            self.register_motor(motor_addr)

        motor = self.motors[motor_addr]
        if command == 'r':
            motor.handle_position_info(remainder)
        elif command == 'v':
            motor.handle_version_info(remainder)
        else:
            log.warning("unknown motor command %s%s", command, remainder)


class Motor:
    def __init__(self, hub: Hub, addr: str):
        log.info(f"Registering motor {addr} on {hub}")
        self.hub = hub
        self.addr = addr
        self.travel_pc = None
        self.rotation_deg = None
        self.version = None
        log.info(f"Requesting position info for motor {addr} on hub {hub.addr}")
        asyncio.create_task(self.request_position_info())

    def __str__(self):
        return f"motor {self.name} on {self.hub}"

    async def request_position_info(self):
        await self.hub.request_motor_info(motor=self.addr, cmd="r", data="?")

    def parse_position_info(
        self, info: str
    ) -> Tuple[str, str]:
        if 'b' not in info:
            raise FormatError("Expected position info but didn't find a 'b'")
        travel_pc, rotation_deg = info.split('b')
        return travel_pc, rotation_deg

    def handle_version_info(self, info: str):
        self.version = info
        log.info("Recorded version of hub %s motor %s as '%s'", 
            self.hub, self.addr, self.version)

    def handle_position_info(self, info:str):
        self.travel_pc, self.rotation_deg = self.parse_position_info(info)
        log.info("Recorded position of hub %s motor %s as %s%%, %s deg", 
            self.hub, self.addr, self.travel_pc, self.rotation_deg)


class AcmedaConnection(object):
    def __init__(self, device: str, timeout: int = 5):
        """
        A connection to one or more Acmeda hubs on the given RS485 device.
        Timeout is how long to wait for any single response.
        """
        self.device = device
        self.ser = aioserial.AioSerial(port=device, baudrate=9600, timeout=timeout)
        self.hubs: Dict[str, Hub] = {}

    async def send_hub_cmd(self, hub: str = "000", cmd: str = "V", data: str = "?"):
        cmd = "%03s%s%s" % (hub, cmd, data)
        log.debug("sending hub command %s ", cmd)
        await self.send_cmd(cmd)
        log.debug("sent hub command %s ", cmd)

    async def send_motor_cmd(
        self, hub: str = "000", motor: str = "000", cmd: str = "v", data: str = "?"
    ):
        """
        Note that non-integer parameters are bytestrings not strings.
        """
        cmd = "%03sD%03s%s%s" % (hub, motor, cmd, data)
        return await self.send_cmd(cmd)

    async def send_cmd(self, cmd: str) -> int:
        """
        Take command string, convert to bytes and send.
        Return number of bytes written
        """
        cmd_bytes = b"!" + cmd.encode() + b";"
        log.debug("  sending %s", cmd_bytes)
        return await self.ser.write_async(cmd_bytes)

    async def get_response(self) -> str:
        """
        Get the next response (up to a semicolon) as a string.
        Returns None on a timeout or invalid response.
        """
        resp = await self.ser.read_until_async(b";")
        log.debug("  got %s", resp)
        if resp is None:
            raise TimeoutError("Timed out in get_response")
        return resp.decode()

    async def response_iter(self, timeouts=10):
        """
        An iterator for possibly several responses.
        We don't usually have a way to know how many responses to 
        wait for, so we have to use a timeout.
        'timeouts' specifies the number of times we'll wait for the
        connection's standard timeout before deciding we're done.
        Example:

            async for resp in self.response_iter():
                print(resp)
        
        """
        responses = []
        timeout_count = 0
        while timeout_count < 2:
            res = await self.get_response()
            if not res:
                timeout_count += 1
            else:
                yield self.parse_response(res)

    def parse_response(self, resp: str) -> Tuple[str, str, str]:
        """
        Returns hub, delim, response.
        """
        if resp.startswith("!") and resp.endswith(";"):
            hub, delim, resp = resp[1:4], resp[4], resp[5:-1]
            return (hub, delim, resp)
        else:
            raise FormatError("Didn't find response delimited by '!' and ';'")

    


    async def get_hubs(self) -> List[str]:
        """
        Get the information about the first hub that responds.
        """
        log.debug("Find hub...")
        await self.send_hub_cmd(hub="000", cmd="V", data="?")
        # We're assuming just one hub here for now
        hub_info = await self.get_response()
        res, _, _ = self.parse_response(hub_info)
        log.info("  hub info: %s", res)
        return [res]

    async def watch_updates(self):
        print("Watching for updates")
        async for hub, delim, resp in self.response_iter():
            # If this is a hub we haven't seen before,
            # create it.

            if hub not in self.hubs:
                self.hubs[hub] = Hub(self, hub)
            
            # Are we likely to have motor info next?
            if delim == 'D':
                self.hubs[hub].handle_motor_info(resp)
                
            # print(f"  Hub {hub} response: {resp}")


async def main():
    conn = AcmedaConnection(device=DEVICE, timeout=3)
    # print("Looking for hubs...")
    # hubs = await conn.get_hubs()  # Need this first
    # hub = hubs[0]   # we actually only get one
    # print(f"   found {hub}")

    # Start a watcher
    asyncio.create_task(conn.watch_updates())
    await asyncio.sleep(0.3)

    print("Ask about hubs")
    await conn.send_hub_cmd(hub="000", cmd="V", data="?")
    await asyncio.sleep(1)


    # print("Move motor 2 to 50%")
    # await conn.send_motor_cmd(hub, "002", cmd="m", data="050")

    
    await asyncio.sleep(30)

asyncio.run(main())
