#! /usr/bin/env python3
#
# Experiments with talking to Rollease Acmeda hub over RS485
# Requires Python 3.7 or later

import asyncio
import rollease
import logging
import sys
import time

from typing import Optional, Tuple, List, Dict

DEVICE = "/dev/serial/by-id/usb-Silicon_Labs_CP2104_USB_to_UART_Bridge_Controller_018DF044-if00-port0"

logging.basicConfig()
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

async def main():
    conn = rollease.AcmedaConnection(device=DEVICE, timeout=3)

    # print("Move motor 2 to 50%")
    # await conn.send_motor_cmd(hub, "002", cmd="m", data="050")

    
    await asyncio.sleep(30)

asyncio.run(main())
