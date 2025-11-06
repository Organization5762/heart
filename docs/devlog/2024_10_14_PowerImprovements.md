# Power Supply Measurements

## Problem Statement

Quantify the power draw of a single LED panel under various input voltages and document open hardware questions for the ribbon cable assembly.

## Materials

- LED panel with Heart runtime test pattern.
- Adjustable DC power supply.
- [Adafruit buck converters](https://www.adafruit.com/product/1385).
- [Distribution bus](https://www.adafruit.com/product/737).
- Multimeter or inline power meter.

## Technical Approach

Drive the panel with an all-white frame while adjusting supply voltage. Record current draw and note visual artefacts. Capture outstanding mechanical considerations for extending ribbon cables.

## Measurements

| Voltage (V) | Current (A) | Power (W) | Number of Screens |
| ----------- | ----------- | --------- | ----------------- |
| 10 | 1.125 | 11.24 | 1 |
| 17 | 0.666 | 11.32 | 1 |
| 5 | 1.717 | 8.58 | 1 |
| 6 | 1.822 | 10.94 | 1 |

Voltages below 5 V produced visible artefacts, so testing should use ≥6 V for a single panel.

## Ribbon Cable Investigation

Reference part: [Assmann WSW H3CCS-1636G](https://www.digikey.com/en/products/detail/assmann-wsw-components/H3CCS-1636G/999349).

| Specification | Value |
| -------------------- | ---------------- |
| Pitch – Connector | 0.100" (2.54 mm) |
| Pitch – Cable | 0.050" (1.27 mm) |
| Length | 3.00' (914.40 mm) |
| Number of Positions | 16 |
| Number of Rows | 2 |

A ribbon cable with the required pitch and connector combination is still outstanding, leaving the extension strategy unresolved.
