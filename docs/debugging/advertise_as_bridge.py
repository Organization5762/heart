#!/usr/bin/env python3
# Advertises a minimal Flowtoys bridge named “Bridge”

import asyncio, sys
from datetime import datetime
from dbus_next.aio import MessageBus
from dbus_next.constants import BusType
from dbus_next import Variant
from dbus_next.service import ServiceInterface, dbus_property, method, PropertyAccess

UART_SVC = "49550001-aad5-59bd-934c-023d807e01d5"


def ts():
    return datetime.now().strftime("[%H:%M:%S]")


async def proxy(bus, name, path):
    xml = await bus.introspect(name, path)
    return bus.get_proxy_object(name, path, xml)


class BridgeAd(ServiceInterface):
    """Legacy, discoverable, local-name-only advertisement."""

    def __init__(self):
        super().__init__("org.bluez.LEAdvertisement1")

    @dbus_property(access=PropertyAccess.READ)
    def Type(self) -> "s":
        return "peripheral"

    @dbus_property(access=PropertyAccess.READ)
    def ServiceUUIDs(self) -> "as":
        return [UART_SVC]

    @dbus_property(access=PropertyAccess.READ)
    def LocalName(self) -> "s":
        return "Bridge"  # exact string

    @dbus_property(access=PropertyAccess.READ)
    def Discoverable(self) -> "b":
        return True  # ensures Flags 0x06

    @method()  # required
    def Release(self):
        pass


async def main():
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

    # choose the first adapter that supports advertising
    om = (await proxy(bus, "org.bluez", "/")).get_interface(
        "org.freedesktop.DBus.ObjectManager"
    )
    objs = await om.call_get_managed_objects()
    adapter = next(p for p, i in objs.items() if "org.bluez.LEAdvertisingManager1" in i)

    ad_path = "/org/flowbridge/adv0"
    bus.export(ad_path, BridgeAd())
    adv_mgr = (await proxy(bus, "org.bluez", adapter)).get_interface(
        "org.bluez.LEAdvertisingManager1"
    )
    await adv_mgr.call_register_advertisement(ad_path, {})
    print(ts(), "📣 Advertising legacy packet “Bridge” (UUID 4955…)")

    await asyncio.Event().wait()


if __name__ == "__main__":
    if sys.version_info < (3, 9):
        print("Python 3.9+ required")
        sys.exit(1)
    asyncio.run(main())
