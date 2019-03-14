# Experiments with controlling Rollease Acmeda blinds from Python & Linux

*I'll turn this into a proper async library in due course, but these are just some quick experiments and notes.  It's mostly public at present just in case anybody else wants to experiement with it sooner than I can!  This requires Python 3.5 or later.*

The Rollease Acmeda motorised blinds (or 'shades', depending on where you live) have a hub which communicates with the outside world, provides timer-based operation, and allows control using their phone app.  It connects to wifi and to the 433 MHz radio used by the blinds and the remotes.  There is no public API that I am aware of for accessing the hub over the network.

However, it does have an RS485 port, for integration with other building management systems such as Control4.

The protocol is documented [here](https://www.rolleaseacmeda.com/docs/default-source/us/smart-home-integration/serial-protocol/Serial_Protocol_PRGM_GL_v1_3pdf.pdf?sfvrsn=26) and various cabling installation examples can be found at the bottom of [this page](https://www.rolleaseacmeda.com/au/products/product-detail/automate_serial-guide_au).

I have successfully tried basic communication under Linux using two different RS485 interfaces:
* The [WINGONEER USB 2.0 to RS485 Serial Converter Adapter](https://www.amazon.co.uk/WINGONEER-Converter-Adapter-SN75176-protection-2/dp/B01N3LM0PU/ref=sr_1_10).  I used this under Debian on an Intel NUC and it appears as `/dev/ttyUSB1` for me because I have another serial device.
* The [AB Electronics RS485 Pi](https://www.abelectronics.co.uk/p/77/rs485-pi) interface for the Raspberry Pi.  (If you're using this, you should read the instructions on their site about disabling Bluetooth and console serial port usage, and you probably need to set `DEVICE = "/dev/ttyAMA0"`).

If you get permission errors when accessing the port, you probably need to add yourself to the 'dialout' group, and log out and back in again.

When making up cables, it's worth noting that some manufacturers use letters A & B to describe the two signal lines in RS485 and some use '+' and '-', but not always consistently.  You should be safe to swap '+' and '-' if your first attempt doesn't succeed.  Ground, however, is always ground!  I debugged mine by running minicom or miniterm.py to look at the port, e.g.

    miniterm.py --raw /dev/ttyUSB1 9600

and power-cycling the hub.  I got a couple of short lines of text when the connections were the right way around, and gobbledegook when they weren't.

The `test_connection.py` simply sends a request asking the hub to identify itself.  You should get back something like

    b'!626V;'

which would indicate that the ID of your hub is '626'.

The `main.py` script starts to impose a bit of structure and does a bit more.  It currently just looks for hubs (because more than one could theoretically be connected on the RS485 bus), and then asks each one for the motors it knows about.  It then asks each motor for its current position.

Some things to note:

* It doesn't find *all* of my motors.  I'm not yet sure why.  I have a mix of Roman and roller blinds.
* You can't always know how many responses will come back for a particular request.  When I send the command to ask for the motor position, I get two or three, for example, from each motor.  There's a certain amount of waiting for timeouts.
* In the middle of my experiments, the timer that closes my blinds in the evening kicked in.  The hub didn't respond while the blinds were moving.

More in due course.  Contributions welcome!

Quentin Stafford-Fraser - https://quentinsf.com - March 2019


