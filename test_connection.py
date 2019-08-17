#! /usr/bin/env python3
#
# Experiments with talking to Rollease Acmeda hub over RS485
# Requires Python 3.5 or later

import serial

DEVICE = "/dev/serial/by-id/usb-Silicon_Labs_CP2104_USB_to_UART_Bridge_Controller_018DF044-if00-port0"


ser = serial.Serial(port=DEVICE, baudrate=9600, timeout=2)   # 9600 8N1 are the defaults

# flush buffers
ser.reset_input_buffer()
ser.reset_output_buffer()
ser.write(b'!000V?;')
ser.flush()
print(ser.read_until(b';'))

