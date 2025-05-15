# Adafruit Feather

Trying to get an Adafruit Feather working as a potential processor for the controller.

## Guides

https://learn.adafruit.com/introducing-the-adafruit-nrf52840-feather/update-bootloader

## Development

- Downloaded the Arduino IDE

### For some reason it won't be visible in the IDE anymore

-- Couldn't find the Feather, got confused. Need to g into Boards Manager and download it via `nRF52`
-- That didn't work. Folloewd this guide https://learn.adafruit.com/bluefruit-nrf52-feather-learning-guide/arduino-bsp-setup and added https://adafruit.github.io/arduino-board-index/package_adafruit_index.json
-- Feather is then identifiable as `Adafruit Bluefruit nRF52840 Feather Express`

This is all detailed in the Git repo
https://github.com/adafruit/Adafruit_nRF52_Arduino/tree/master?tab=readme-ov-file#recommended-adafruit-nrf52-bsp-via-the-arduino-board-manager

Try to run the test sketch: nordicsemi.exceptions.NordicSemiException:

- pip install nrfutil
- ls /dev/tty.\*

I tried to download some drivers etc., what fixed it was hitting the double reset button fast.

## First Script

This flashes the D3 LED:

```
#if defined(USE_TINYUSB)
#include <Adafruit_TinyUSB.h> // for Serial
#endif

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
}

void loop() {
  digitalWrite(LED_BUILTIN, HIGH);   // turn the LED on (HIGH is the voltage level)
  delay(1000);                       // wait for a second
  digitalWrite(LED_BUILTIN, LOW);    // turn the LED off by making the voltage LOW
  delay(1000);                       // wait for a second
}
```

### At this point I realized this was kinda stupid to write this weird arudino language, so I just flashed a boot loader

https://learn.adafruit.com/welcome-to-circuitpython/installing-circuitpython

For whatever reason, I couldn't transfer the file on my Mac to the Arduino. I rsynced the file to the PI and copied it in similarly to
drivers/rotary_encoder/updated.sh

## Now I can write python!

Jk there's always a bug. Next:

Can't find the bluetooth modules!

Download those at https://circuitpython.org/libraries, copy the ones you want into `lib` on the board

I just copied in adafruit_ble

## ...

Many hours later, I got this all mostly working. The drivers have a lot of robustness added to them, but generally it can easily transfer a lot of information at a decent speed now!
