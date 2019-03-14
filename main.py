#! /usr/bin/env python3
#
# Experiments with talking to Rollease Acmeda hub over RS485
# Requires Python 3.5 or later

import logging
import serial
import serial.rs485
import serial_asyncio
import sys
import time

from typing import Optional, Tuple, List

DEVICE = "/dev/ttyUSB1"

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class AcmedaConnection(object):

    def __init__(self, device: str, timeout: int = 3):
        """
        A connection to one or more Acmeda hubs on the given RS485 device.
        Timeout is how long to wait for any single response.
        """
        self.device = device
        self.ser = serial.Serial(port=device, baudrate=9600, timeout=2)   # 9600 8N1 are the defaults

        # flush buffers
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

    def send_hub_cmd(self,
                     hub: bytes = b'000',
                     cmd: bytes = b'V',
                     data: bytes = b'?'):
        cmd = b'%03b%b%b' % (hub, cmd, data)
        self.send_cmd(cmd)

    def send_motor_cmd(self,
                       hub: bytes = b'000',
                       motor: bytes = b'000',
                       cmd: bytes = b'v',
                       data: bytes = b'?'):
        """
        Note that non-integer parameters are bytestrings not strings.
        """
        cmd = b'%03bD%03b%b%b' % (hub, motor, cmd, data)
        self.send_cmd(cmd)

    def send_cmd(self, cmd: bytes):
        cmd = b'!' + cmd + b';'
        log.info('Sending %s', cmd)
        self.ser.write(cmd)
        self.ser.flush()

    def get_response(self) -> Optional[Tuple[bytes, bytes]]:
        """
        Returns None on a timeout or invalid response.
        """
        resp = self.ser.read_until(b';')
        return self.parse_response(resp)

    def get_responses(self, timeouts=2) -> List[Tuple[bytes, bytes]]:
        """
        Wait for possibly several responses.
        'timeouts' specifies the number of times we'll wait for the
        connection's standard timeout before deciding there are no more
        responses.

        NOTE: This is not at all async at present, and may take many seconds!
        """
        responses = []
        timeout_count = 0
        while timeout_count < 2:
            res = self.get_response()
            if res is None:
                timeout_count += 1
            else:
                responses.append(res)
        return responses

    def parse_response(self, resp: bytes) -> Optional[bytes]:
        """
        Returns None on a timeout or invalid response.
        """
        if resp.startswith(b'!') and resp.endswith(b';'):
            hub, resp = resp[1:4], resp[4:-2]
            return (hub, resp)
        else:
            return None

    def get_hubs(self) -> List[Tuple[bytes, bytes]]:
        log.info("Find hub...")
        self.send_hub_cmd(hub=b'000', cmd=b'V', data=b'?')
        return self.get_responses()

    def get_motors(self, hub: bytes) -> List[Tuple[bytes, bytes]]:
        log.info("Find motors...")
        self.send_motor_cmd(hub, motor=b'000', cmd=b'v', data=b'?')
        # we should get back a list inf the format [(hub, 'D003vD?'), ...]
        return [
            (d[1:4], d[4:]) for h, d in self.get_responses()
        ]


def main():
    conn = AcmedaConnection(device=DEVICE)
    print("Looking for hubs")
    hub_info = conn.get_hubs()
    if len(hub_info) == 0:
        log.error('No hubs found')
        sys.exit(1)
    
    print("Looking for motors")
    for hub_id, hub_data in hub_info:
        motor_info = conn.get_motors(hub_id)
        for motor, motor_data in motor_info:
            print("  Hub %s Motor %s" % (hub_id, motor))

    print("Get motor positions")
    for hub_id, hub_data in hub_info:
        for motor, motor_data in motor_info:
            conn.send_motor_cmd(hub=hub_id, motor=motor, cmd=b'r?')
            # In practice, each motor seems to return multiple responses, 
            # perhaps because this is used while it's moving?
            # So we wait for them.
            print("  Hub %s Motor %s: %s" % (hub_id, motor, conn.get_responses()))

    print("Anything left?  (Ctrl-C to interrupt)")
    while True:
        print(conn.get_response())


if __name__ == '__main__':
    main()
