# Controlling Rollease Acmeda blinds from Python & Linux

*My plan is to turn this into a proper utility in due course, probably as a gateway allowing the blinds to be controlled via MQTT.  At this stage, though, these are some experiments and notes.   This requires Python 3.6 or later.*

## Background

The Rollease Acmeda motorised blinds (or 'shades') can be controlled directly with RF-based remote controls, but a hub is also available which connects to wifi and to the 433 MHz radio used by the blinds and the remotes.  It communicates with the outside world, provides timer-based operation, and allows control using the official phone app.  I want to enable some control of the hub using standard network protocols, so  it can be integrated with home automation systems such as [Home Assistant](https://home-assistant.io).

The radio protocol is proprietary and has so far resisted attempts to record and playback its signals. There is also no public API that I am aware of for accessing the hub over the local network. A project in the OpenHab community has been attempting to reverse-engineer the network protocols, but with only partial success.

There is, however, an official way for third-parties to interact with the hub: it has an RS485 serial port, for integration with other building management systems such as Control4.  The protocol is documented [here](https://www.rolleaseacmeda.com/docs/default-source/us/smart-home-integration/serial-protocol/Serial_Protocol_PRGM_GL_v1_3pdf.pdf?sfvrsn=26) and various cabling installation examples can be found at the bottom of [this page](https://www.rolleaseacmeda.com/au/products/product-detail/automate_serial-guide_au).

This code will communicate with the hub over RS485, and listen on the network for commands to be sent to the blinds, and send status reports back. 

## You will need...

### An RS485 adapter

I have successfully tried basic communication under Linux using two different RS485 interfaces:
* The [WINGONEER USB 2.0 to RS485 Serial Converter Adapter](https://www.amazon.co.uk/WINGONEER-Converter-Adapter-SN75176-protection-2/dp/B01N3LM0PU/ref=sr_1_10). These are cheaply available under a variety of other brand names too.
* The [AB Electronics RS485 Pi](https://www.abelectronics.co.uk/p/77/rs485-pi) interface for the Raspberry Pi.  (If you're using this, you should read the instructions on their site about disabling Bluetooth and console serial port usage, and you probably need to set `DEVICE = "/dev/ttyAMA0"`).

These appear as serial devices in Linux, such as `/dev/ttyUSB0` or `/dev/ttyAMA0`.   On a typical Linux system, especially if you have more than one device connected, you may find they start up or are recognised in a different order, so the thing that was `ttyUSB0` today might become `ttyUSB1` on the next reboot. 

So a better way to specify the devices, if it's available, is to use one of the symbolic links under `/dev/serial/by-id/`.  These should automatically point to the right place.  On my system, the Wingoneer USB adapter appears as

    /dev/serial/by-id/usb-Silicon_Labs_CP2104_USB_to_UART_Bridge_Controller_018DF044-if00-port0

It's more verbose, but should be more reliable.   Copy the full pathname and paste it into the code as the DEVICE setting.

**NOTE**: If you get permission errors when accessing the port, you probably need to add yourself to the 'dialout' group, and log out and back in again.

## An RS485 cable

You will need to connect your RS485 adapter to the port on the hub using what is technically a '4p4c connector'.  This is the thing traditionally used to connect phone handsets to their bases, and you should note that it is smaller than an RJ45 ethernet connector or an RJ11 phone socket connector.  I bought a phone handset cable and cut it in half.

![cable](docs/cable-400.jpg)

Yes, I know, it's not pretty, but it does the job well!

![wingoneer](docs/wingoneer-400.jpg)

![connector](docs/connector-400.jpg)

When making up cables, it's worth noting that some manufacturers use letters A & B to describe the two signal lines in RS485 and some use '+' and '-', but not always consistently.  You should be safe to swap '+' and '-' if your first attempt doesn't succeed.  Ground, however, is always ground!  I debugged mine by running minicom or miniterm.py to look at the port, e.g.

    miniterm.py --raw /dev/ttyUSB1 9600

and power-cycling the hub.  I got a couple of short lines of text when the connections were the right way around, and gobbledegook when they weren't.

The `test_connection.py` simply sends a request asking the hub to identify itself.  You should get back something like

    b'!626V;'

which would indicate that the ID of your hub is '626'.

The `main.py` script starts to impose a bit of structure and does a bit more.  It currently just looks for hubs (because more than one could theoretically be connected on the RS485 bus), and then asks each one for the motors it knows about.  It then asks each motor for its current position.  It does this with async calls, though those aren't needed yet.

Some things to note:

* It doesn't find *all* of my motors.  I'm not yet sure why.  I have a mix of Roman and roller blinds.
* You can't always know how many responses will come back for a particular request.  When I send the command to ask for the motor position, I get two or three, for example, from each motor.  There's a certain amount of waiting for timeouts.
* In the middle of my experiments, the timer that closes my blinds in the evening kicked in.  The hub didn't respond while the blinds were moving.

More in due course.  Contributions welcome!

Quentin Stafford-Fraser - https://quentinsf.com - Aug 2019


