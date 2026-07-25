from __future__ import annotations

from pathlib import Path

LINUX_JOYSTICK_SYSFS = Path("/sys/class/input")
SCREEN_SLOT_BLUETOOTH_MACS: tuple[str | None, ...] = (
    "E4:17:D8:E9:76:C8",  # Screen 1 / player 1
    "E4:17:D8:43:5C:48",  # Screen 2 / player 2
    "E4:17:D8:58:22:8A",  # Screen 3 / player 3
    "E4:17:D8:91:15:35",  # Screen 4 / player 4
)


def bluetooth_mac_for_screen_slot(slot: int) -> str | None:
    if slot >= len(SCREEN_SLOT_BLUETOOTH_MACS):
        return None
    return SCREEN_SLOT_BLUETOOTH_MACS[slot]


def normalize_bluetooth_mac(mac_address: str) -> str:
    return mac_address.replace(":", "").lower()


def screen_slot_for_joystick(joystick_id: int) -> int:
    joystick_paths = sorted(LINUX_JOYSTICK_SYSFS.glob("js*"))
    if joystick_id >= len(joystick_paths):
        return joystick_id
    try:
        controller_mac = (
            (joystick_paths[joystick_id] / "device" / "uniq").read_text().strip()
        )
    except OSError:
        return joystick_id
    normalized = normalize_bluetooth_mac(controller_mac)
    for slot, configured_mac in enumerate(SCREEN_SLOT_BLUETOOTH_MACS):
        if (
            configured_mac is not None
            and normalize_bluetooth_mac(configured_mac) == normalized
        ):
            return slot
    return joystick_id
