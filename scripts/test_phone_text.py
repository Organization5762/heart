#!/usr/bin/env python3
"""
Test runner for the *PhoneText* BLE peripheral.

This small helper script simply instantiates :class:`heart.peripheral.phone_text.PhoneText`
so that it can be launched from the command line.  The actual BLE handling logic
now lives in the *heart* package.
"""

from heart.peripheral.phone_text import PhoneText


def main():  # noqa: D401 – simple entry-point
    PhoneText().run()


if __name__ == "__main__":
    main()
