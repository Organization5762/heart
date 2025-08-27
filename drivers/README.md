# Input Devices

Possible future input types (Based on parts I've ordered):

## 🎛️ Direct Input Devices

| Part Name                                                        | Description                                                                 | Supported | Driver Link                         |
| ---------------------------------------------------------------- | --------------------------------------------------------------------------- | --------- | ----------------------------------- |
| [Rotary Encoder + Extras](https://www.adafruit.com/product/4964) | Adafruit Rotary Trinkey - USB NeoPixel Rotary Encoder                       | Yes       | [Driver](../drivers/rotary_encoder) |
| [I2C Quad Rotary Encoder](https://www.adafruit.com/product/5752) | Adafruit I2C Quad Rotary Encoder Breakout with NeoPixel - STEMMA QT / Qwiic | No        | N/A                                 |
| [Analog Thumb Joystick](https://www.adafruit.com/product/512)    | 2-axis joystick with select button + breakout board                         | No        | N/A                                 |

______________________________________________________________________

## 🌡️ Sensors

| Part Name                                                     | Description                                                    | Supported | Driver Link                        |
| ------------------------------------------------------------- | -------------------------------------------------------------- | --------- | ---------------------------------- |
| [ISM330DHCX IMU](https://www.adafruit.com/product/4502)       | 6 DoF accelerometer + gyroscope – STEMMA QT / Qwiic            | Yes       | [Driver](../drivers/accelerometer) |
| [SCD-41 CO₂ Sensor](https://www.adafruit.com/product/5190)    | True CO₂, temperature, and humidity sensor – STEMMA QT / Qwiic | No        | N/A                                |
| [Piezoelectric Ribbon](https://www.adafruit.com/product/4931) | 2 ft (600mm) piezoelectric ribbon sensor                       | No        | N/A                                |
| [MPL3115A2 Sensor](https://www.adafruit.com/product/1893)     | I2C barometric pressure / altitude / temperature               | No        | N/A                                |

______________________________________________________________________

## 👁️ Visual Input

| Part Name                                                          | Description                        | Supported | Driver Link |
| ------------------------------------------------------------------ | ---------------------------------- | --------- | ----------- |
| [PiCowbell Camera Breakout](https://www.adafruit.com/product/5946) | Autofocus 120° lens                | No        | N/A         |
| [MLX90640 Thermal Camera](https://www.adafruit.com/product/4469)   | 24x32 IR thermal camera – 110° FoV | No        | N/A         |

______________________________________________________________________

## 🎤 Audio Input

| Part Name                                                    | Description                         | Supported | Driver Link |
| ------------------------------------------------------------ | ----------------------------------- | --------- | ----------- |
| [Mini USB Microphone](https://www.adafruit.com/product/3367) | Plug-and-play USB mic               | No        | N/A         |
| [I2S MEMS Microphone](https://www.adafruit.com/product/3421) | SPH0645LM4H MEMS mic breakout – I2S | No        | N/A         |

______________________________________________________________________

## 📡 Location & Navigation

| Part Name                                                      | Description                         | Supported | Driver Link |
| -------------------------------------------------------------- | ----------------------------------- | --------- | ----------- |
| [Ultimate GPS USB GNSS](https://www.adafruit.com/product/4279) | USB GPS – 99 channels, 10Hz updates | No        | N/A         |
| [Ultra-Wide-Band Positioning Development Kit (UWB, BU-03)](https://core-electronics.com.au/ultra-wide-band-module-development-kit-bu03.html) | Distance between two boards | No | N/A ~

# Bridges

A bridge connects two hardware devices, allowing them to share data and communicate across different protocols. It translates and relays signals or data, ensuring compatibility and enhancing the overall system’s functionality.

## USB Bridges

Most drivers expect a direct USB connection to the Pi, sometimes mediated by a small controller on the board. We currently offer easy-setup for:

- [KB2040](https://www.adafruit.com/product/5302)

## Bluetooth LE Bridges

**Note**: This driver is a work in progress. At the moment, it mainly forwards placeholder data. However, it’s still useful as a starting point for bridging to existing setups.

We have also explored Bluetooth-based bridges, which do not plug directly into the PI:

- [Adafruit Feather nRF52840 Express](https://www.adafruit.com/product/4062) - Driver is at [this link](../drivers/bluetooth-bridge/)

## Future Bridges

- [Garmin ANT+](https://www.amazon.com/Garmin-USB-Stick-Fitness-Devices/dp/B00CM381SQ/ref=sr_1_1?ie=UTF8&qid=1475691048&sr=8-1&keywords=ant%2B+stick)
- [Flowtoy USB Bridge](https://flowtoys.com/usb-bridge) (Note, this is just a special-case of Bluetooth and may not be required)

# Development Notes

## Accessing Driver IO

I've found the most reliable script to be this:
`python3 -m serial.tools.miniterm /dev/ttyACM0 115200`

It'll drop you in with a Python interpret and read STDOUT from the serial port. You can directly run commands via the REPL to help with debugging and see errors. It isn't the best, but it isn't bad.

If you're on an OSx device, `screen /dev/ttyACM0 115200` might be more ergonomic.

## Understanding Interface

Each board is really different, the following code can get you really far in understanding what is going on with a given board:

```python
import board
dir(board)
```
