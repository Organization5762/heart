from __future__ import annotations

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
