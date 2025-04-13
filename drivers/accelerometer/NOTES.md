# Design

Current plan to to wire the Accelerometer into the KB2040, then connect the KB2040 to the Pi via USB

## Setup

Start with this guide (https://learn.adafruit.com/adafruit-kb2040/circuitpython) to get the KB2040 in the right state 
Datasheet: https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf
Pinout Reference w/ Compatibility: https://learn.adafruit.com/adafruit-kb2040/pinouts

Downloaded https://circuitpython.org/board/adafruit_kb2040/

Resynced it ot the PI (Had issues previously with transfering on Mac)
`rsync ~/Downloads/adafruit-circuitpython-adafruit_kb2040-en_US-9.2.7.uf2 michael@totem2.local:Desktop`

Drive named RPI-RP2
`mv ~/Desktop/adafruit-circuitpython-adafruit_kb2040-en_US-9.2.7.uf2 /media/michael/RPI-RP2/`

New Media named CIRCUITPY showed up (yey!)

### First Programming
LED wasn't flashing, so I ran this to connect to it with a Python REPL and inspect the board object:
`python3 -m serial.tools.miniterm /dev/ttyACM0 115200`
```python
import digitalio
import board

led = digitalio.DigitalInOut(board.LED)
dir(board)
```

This showed a NEOPixel field, so I sorta assume that's the right LED

```python
led = digitalio.DigitalInOut(board.NEOPIXEL)
led.direction = digitalio.Direction.OUTPUT
```

This didn't work, screw it who cares it an LED

## Accelerometer
I have a STEMMA QT connector that I plugged into the accelerometer, it only have one Female end though.  So I pinned this out now

### Powering up
1. I connected the red wire to the RAW and the black to the GND to give it power
2. Now I need to decide whre the blue and yellow go; I think TX and RX initially?

From here: https://www.adafruit.com/product/5385
Red - 3.3VDC Power
Black - Ground
Blue - I2C SDA Data (TX/D0 - The main UART0 TX pin. It is also I2C0 SDA)
Yellow - I2C SCL Clock (RX/D1 - The main UART0 RX pin. It is also I2C0 SCL)

Device is now connected

### Getting Data
```python
data = digitalio.DigitalInOut(board.RX)
data.value
```

This reads a value of True, I'm clearly missing something (Which is that this is a digital signal and not acceleration..)

Find another guide: https://learn.adafruit.com/lsm6dsox-and-ism330dhc-6-dof-imu/python-circuitpython

Ok so I need to add a new lib

Went to the big list of libs at https://github.com/adafruit/Adafruit_CircuitPython_Bundle/releases/tag/20250412

```
rsync -a /Users/michael/Downloads/adafruit-circuitpython-bundle-9.x-mpy-20250412/lib/adafruit_lsm6ds michael@totem2.local:Desktop
# From the future, you'll need both of these:

rsync -a /Users/michael/Downloads/adafruit-circuitpython-bundle-9.x-mpy-20250412/lib/adafruit_register michael@totem2.local:Desktop
```


Downloaded it and synced the relevant lib
Then moved it in
```
mv ~/Desktop/adafruit_lsm6ds lib/
```

```
ImportError: no module named 'adafruit_register'
```

Just more imports, so rinse and repeat etc.

```
import time
import board
import busio
import adafruit_lsm6ds

i2c = busio.I2C(board.RX, board.TX)
sox = adafruit_lsm6ds.LSM6DSOX(i2c)
```

Module not found `LSM6DSOX` ..

Let's try just installing all the recommended ones this time:
https://learn.adafruit.com/lsm6dsox-and-ism330dhc-6-dof-imu/python-circuitpython#circuitpython-installation-of-lsm6ds-library-3048524

Which was just adding `adafruit_bus_device`, the other ones seem a bit dated

Looks like my controlled just moved to:
https://github.com/adafruit/Adafruit_CircuitPython_LSM6DS/blob/0aefcb69b26b72e2b46c81651f2ae1731da311a9/adafruit_lsm6ds/ism330dhcx.py#L20

```
from adafruit_lsm6ds.ism330dhcx import ISM330DHCX
import time
import board
import busio

i2c = busio.I2C(board.RX, board.TX)
sensor = ISM330DHCX(i2c)
```