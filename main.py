#! /usr/bin/env python3
#
# Experiments with talking to Rollease Acmeda hub over RS485
# Requires Python 3.6 or later

import asyncio
import logging
import aioserial
import serial
import sys
import time

from typing import Optional, Tuple, List, Dict

DEVICE = "/dev/serial/by-id/usb-Silicon_Labs_CP2104_USB_to_UART_Bridge_Controller_018DF044-if00-port0"

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

class Hub():
    def __init__(self, addr: str, motors : Dict = {}):
        print(f"Registering hub {addr}")
        self.addr = addr
        self.motors = motors

    def __str__(self):
        return f"Hub {self.addr}"

class Motor():
    def __init__(self, hub: Hub, addr: str):
        print(f"Registering motor {addr} on {hub}")
        self.hub = hub
        self.addr = addr
        self.position = None

    def __str__(self):
        return  f"motor {self.name} on {self.hub}"

class AcmedaConnection(object):

    def __init__(self, device: str, timeout: int = 5):
        """
        A connection to one or more Acmeda hubs on the given RS485 device.
        Timeout is how long to wait for any single response.
        """
        self.device = device
        self.ser = aioserial.AioSerial(port=device, baudrate=9600, timeout=timeout)

    async def send_hub_cmd(self,
                     hub: bytes = b'000',
                     cmd: bytes = b'V',
                     data: bytes = b'?'):
        cmd = b'%03b%b%b' % (hub, cmd, data)
        await self.send_cmd(cmd)
        print("sent hub command",cmd)

    async def send_motor_cmd(self,
                       hub: bytes = b'000',
                       motor: bytes = b'000',
                       cmd: bytes = b'v',
                       data: bytes = b'?'):
        """
        Note that non-integer parameters are bytestrings not strings.
        """
        cmd = b'%03bD%03b%b%b' % (hub, motor, cmd, data)
        return await self.send_cmd(cmd)

    async def send_cmd(self, cmd: bytes):
        cmd = b'!' + cmd + b';'
        #print('  send', cmd)
        return await self.ser.write_async(cmd)
        # self.ser.flush()

    async def get_response(self) -> Optional[Tuple[bytes, bytes]]:
        """
        Returns None on a timeout or invalid response.
        """
        resp = await self.ser.read_until_async(b';')
        # print("  got", resp)
        return resp

    async def response_iter(self, timeouts=1):
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
        # print("Waiting for multiple responses")
        responses = []
        timeout_count = 0
        while timeout_count < 2:
            res = await self.get_response()
            if not res:
                timeout_count += 1
            else:
                yield self.parse_response(res)


    def parse_response(self, resp: bytes) -> Optional[bytes]:
        """
        Returns None on a timeout or invalid response.
        """
        if resp.startswith(b'!') and resp.endswith(b';'):
            hub, resp = resp[1:4], resp[5:-1]
            return (hub, resp)
        else:
            return None

    def parse_motor_info(self, info: bytes) -> Tuple[bytes, bytes, bytes]:
        motor_addr, command, remainder = None, None, None
        motor_addr = info[:3]
        if len(info) > 3:
            command = info[3]
        if len(info) > 4:
            remainder = info[4:]
        return motor_addr, command, remainder

    def parse_position_info(self, info: bytes) -> Tuple[bytes, bytes, bytes]:
        motor_addr, command, remainder = None, None, None
        motor_addr = info[:3]
        if len(info) > 3:
            command = info[3]
        if len(info) > 4:
            travel_pc = info[4:7]
        delimiter = info[7]
        if len(info) > 7:
            rotation_deg = info[8:11]
        return motor_addr, travel_pc, rotation_deg

    async def get_hubs(self) -> List[Tuple[bytes, bytes]]:
        """
        Get the information about the first hub that responds.
        """
        print("Find hub...")
        await self.send_hub_cmd(hub=b'000', cmd=b'V', data=b'?')
        # We're assuming one hub here for now
        res = self.parse_response(await self.get_response())
        print("  hub info:", res)
        return res
        
    async def get_motors(self, hub: bytes) -> List[Tuple[bytes, bytes, bytes]]:
        # This is tricky because we don't know when all the motors have
        # responded.  I think the only way to do this is a timeout.
        log.info("Find motors...")
        await self.send_motor_cmd(hub, motor=b'000', cmd=b'v', data=b'?')
        infos = []
        async for hub, resp in self.response_iter():
            info = self.parse_motor_info(resp)
            print("  motor info:", info)
            infos.append( info )
        return infos

    async def get_positions(self, hub: bytes, motor: bytes=b'000') -> List[Tuple[bytes, bytes, bytes]]:
        log.info("Request positions...")
        await self.send_motor_cmd(hub, motor, cmd=b'r', data=b'?')
        infos = []
        async for motor, resp in self.response_iter():
            info = self.parse_position_info(resp)
            print("  position info:", info)
            infos.append( info )
        return infos

async def main():
    conn = AcmedaConnection(device=DEVICE, timeout=3)
    print("Looking for hubs")
    hubs = await conn.get_hubs()  # Need this first

    print("Looking for motors")
    motor_infos = await conn.get_motors(hubs[0])
    await asyncio.sleep(0.3)

    print("Looking for motor positions (slow)")
    for motor_addr, cmd, remainder in motor_infos:
        print(f"Motor {motor_addr.decode()}")
        position_infos = await conn.get_positions(hubs[0], motor_addr)
    await asyncio.sleep(0.3)

asyncio.run(main())



