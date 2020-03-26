#! /usr/bin/env python3
#
# Experiments with talking to Rollease Acmeda hub over RS485
# Requires Python 3.7 or later

import asyncio
import logging
import aioserial

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

    # This is a motor command, but it's at this level because
    # it allows us to find the motors and register them.

    async def request_motor_info(self, motor: str = "000", cmd: str = "v", data: str ="?"):
        await self.conn.send_motor_cmd(self.addr, motor, cmd, data)

    def register_motor(self, addr: str):
        if addr in self.motors:
            return
        self.motors[addr] = Motor(self, addr)
        # TODO: Ideally here, we need a way to inform calling parties
        # that a new motor has been discovered.

    def handle_uplink(self, delim: str, resp: str):
        """
        If an incoming message is from this hub,
        handle the top-level delimiter (typically 'D')
        and the rest of the resonse.
        """

        if delim == "V":
            log.info("Got address message from hub %s", self.addr)
        elif delim == "A":
            log.warning("We don't handle hub test/address change responses yet")
        elif delim == "D":
            log.debug("Received motor message %s %s", delim, resp)
            self.handle_motor_info(resp)

    def _parse_motor_info(self, info: str) -> Tuple[str, str, str]:
        motor_addr = info[:3]
        command, remainder = None, None
        command = info[3]
        remainder = info[4:]
        return motor_addr, command, remainder

    def handle_motor_info(self, resp: str):
        motor_addr, command, remainder = self._parse_motor_info(resp)
        if motor_addr not in self.motors:
            self.register_motor(motor_addr)

        motor = self.motors[motor_addr]
        motor.handle_uplink(command, remainder)


class Motor:
    def __init__(self, hub: Hub, addr: str):
        log.info(f"Registering motor {addr} on {hub}")
        self.hub = hub
        self.addr = addr
        self.travel_pc: Optional[str] = None
        self.rotation_deg: Optional[str] = None
        self.version: Optional[str] = None
        log.info(f"Requesting position info for motor {addr} on hub {hub.addr}")
        asyncio.create_task(self.request_current_position())

    def __str__(self):
        return f"motor {self.name} on {self.hub}"

    async def request_cmd(self, cmd: str = "r", data: str = ""):
        await self.hub.request_motor_info(self.addr, cmd, data)

    # Generic motor response handler

    def handle_uplink(self, command: str, remainder: str):
        if command == "U":
            log.error("Can't get position/stroke not set")
        elif command in (">", "<") and remainder is not None:
            self.handle_motion_position_info(remainder)
        elif command == "r" and remainder is not None:
            self.handle_stop_position_info(remainder)
        elif command == "v" and remainder is not None:
            self.handle_version_info(remainder)
        else:
            log.warning("unknown motor command %s%s", command, remainder)

    # Version

    def handle_version_info(self, info: str):
        self.version = info
        log.info(
            "Recorded version of %s motor %s as '%s'", self.hub, self.addr, self.version
        )

    # Position

    def handle_motion_position_info(self, info: str):
        self.travel_pc, self.rotation_deg = travel_pc, rotation_deg = info.split("b")
        log.info(
            "Recorded motion of %s motor %s from %s%%, %s deg",
            self.hub,
            self.addr,
            self.travel_pc,
            self.rotation_deg,
        )
        # do a callback if we have one
        if self.hub.conn.callback is not None:
            asyncio.create_task(self.hub.conn.callback(self.hub, self))

    def handle_stop_position_info(self, info: str):
        self.travel_pc, self.rotation_deg = travel_pc, rotation_deg = info.split("b")
        log.info(
            "Recorded position of %s motor %s as %s%%, %s deg",
            self.hub,
            self.addr,
            self.travel_pc,
            self.rotation_deg,
        )

        # do a callback if we have one
        if self.hub.conn.callback is not None:
            asyncio.create_task(self.hub.conn.callback(self.hub, self))

    # Motior requests

    async def request_close(self):
        await self.request_cmd(cmd="c", data="")

    async def request_open(self):
        await self.request_cmd(cmd="o", data="")

    async def request_stop(self):
        await self.request_cmd(cmd="s", data="")

    async def request_jog_down(self):
        await self.request_cmd(cmd="cA", data="")

    async def request_jog_up(self):
        await self.request_cmd(cmd="oA", data="")

    async def request_move_percent(self, pc: int):
        await self.request_cmd(cmd="m", data="%03d" % pc)

    async def request_rotate_percent(self, pc: int):
        await self.request_cmd(cmd="b", data="%03d" % pc)

    async def request_move_preferred_position(self):
        await self.request_cmd(cmd="f", data="")

    async def request_motor_param(self):
        await self.request_cmd(cmd="N", data="?")

    async def request_current_position(self):
        await self.request_cmd(cmd="r", data="?")

    async def request_preferred_position(self):
        await self.request_cmd(cmd="f", data="?")

    async def request_motor_speed(self):
        await self.request_cmd(cmd="pSc", data="?")

    async def request_motor_voltage(self):
        await self.request_cmd(cmd="pVc", data="?")

    async def request_version(self):
        await self.request_cmd(cmd="v", data="?")

    async def request_position_limit_setting(self):
        await self.request_cmd(cmd="pP", data="?")

    # Haven't bothered with the motor limits etc yet


class AcmedaConnection(object):
    def __init__(self, device: str, timeout: int = 30, callback=None):
        """
        A connection to one or more Acmeda hubs on the given RS485 device.
        Timeout is how long to wait for any single response.
        A callback, if given, will be called as a task with parameters
        (hub, motor) when an update is detected.
        """
        self.device = device
        self.ser = aioserial.AioSerial(port=device, baudrate=9600, timeout=timeout)
        self.hubs: Dict[str, Hub] = {}
        self.callback = callback

        # Start a watcher
        asyncio.create_task(self.monitor_updates())

    # Low-level stuff to do with marchalling and parsing the messages

    async def _send_cmd(self, cmd: str) -> int:
        """
        Take command string, convert to bytes and send.
        Return number of bytes written
        """
        cmd_bytes = b"!" + cmd.encode() + b";"
        log.debug("  sending %s", cmd_bytes)
        return await self.ser.write_async(cmd_bytes)

    async def send_hub_cmd(self, hub: str = "000", cmd: str = "V", data: str = "?"):
        """
        Send the specified command and data to the specified hub.
        """
        cmd = "%03s%s%s" % (hub, cmd, data)
        log.debug("  sending hub command %s ", cmd)
        sent = await self._send_cmd(cmd)
        log.debug("  sent hub command %s: %s bytes ", cmd, sent)

    async def send_motor_cmd(
        self, hub: str = "000", motor: str = "000", cmd: str = "v", data: str = "?"
    ):
        """
        Send the specified command and data to the specified motor on the specified hub.
        """
        cmd = "%03sD%03s%s%s" % (hub, motor, cmd, data)
        return await self._send_cmd(cmd)

    async def _get_response(self) -> str:
        """
        Get the next response (up to a semicolon) as a string.
        Returns None on a timeout or invalid response.
        """
        resp = await self.ser.read_until_async(b";")
        log.debug("  got %s", resp)
        if resp is None:
            raise TimeoutError("Timed out in _get_response")
        return resp.decode()

    def _parse_response(self, resp: str) -> Tuple[str, str, str]:
        """
        Split up a top-level response into the hub address,
        the delimiter, and the bit after the delimiter.
        Returns hub, delim, response.
        """
        if resp.startswith("!") and resp.endswith(";"):
            hub, delim, resp = resp[1:4], resp[4], resp[5:-1]
            return (hub, delim, resp)
        else:
            raise FormatError("Didn't find response delimited by '!' and ';' :'{}'".format(resp))

    async def response_iter(self, timeouts=10):
        """
        An iterator for retrieving possibly several responses.
        We don't usually have a way to know how many responses to 
        wait for, so we have to use a timeout.
        'timeouts' specifies the number of times we'll wait for the
        connection's standard timeout before deciding we're done.
        Example:

            async for resp in self.response_iter():
                print(resp)
        
        """
        timeout_count = 0
        while timeout_count < 2:
            res = await self._get_response()
            if not res:
                timeout_count += 1
            else:
                yield self._parse_response(res)

    async def monitor_updates(self):
        """
        Receive responses and pass them to the appropriate
        party.
        """

        while True:
            log.info("Watching for serial updates")
            async for hub, delim, resp in self.response_iter():
                # If this is a hub we haven't seen before,
                # create it.

                if hub not in self.hubs:
                    self.hubs[hub] = Hub(self, hub)

                self.hubs[hub].handle_uplink(delim, resp)
                # print(f"  Hub {hub} response: {resp}")

    async def request_hub_info(self):
        """
        Ask all hubs to report in with address info
        """
        log.info("Ask hubs to report in")
        await self.send_hub_cmd(hub="000", cmd="V", data="?")
