#!/usr/bin/env python3
# fake_bridge.py  – advertise a minimal Flowtoys bridge (BLE UART v2)

import asyncio, sys
from datetime import datetime
from dbus_next.aio import MessageBus
from dbus_next.constants import BusType
from dbus_next import Variant
from dbus_next.service import ServiceInterface, method, dbus_property, PropertyAccess

UART_SVC = "49550001-aad5-59bd-934c-023d807e01d5"
UART_TX = "49550002-aad5-59bd-934c-023d807e01d5"
UART_RX = "49550003-aad5-59bd-934c-023d807e01d5"


def ts():
    return datetime.now().strftime("[%H:%M:%S]")


async def proxy(bus, name, path):
    xml = await bus.introspect(name, path)
    return bus.get_proxy_object(name, path, xml)


# ───── GATT tree ────────────────────────────────────────────────────────────
class UartService(ServiceInterface):
    def __init__(self, path):
        super().__init__("org.bluez.GattService1")
        self.path = path

    @dbus_property(access=PropertyAccess.READ)  # required properties
    def UUID(self) -> "s":
        return UART_SVC

    @dbus_property(access=PropertyAccess.READ)
    def Primary(self) -> "b":
        return True


class UartTx(ServiceInterface):
    def __init__(self, path):
        super().__init__("org.bluez.GattCharacteristic1")
        self.path = path
        self.notifying = False

    @method()
    def StartNotify(self):
        self.notifying = True
        print(ts(), "Phone ENABLED notify")

    @method()
    def StopNotify(self):
        self.notifying = False
        print(ts(), "Phone DISABLED notify")

    @dbus_property(access=PropertyAccess.READ)
    def Service(self) -> "o":
        return self.path.rsplit("/", 1)[0]

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> "s":
        return UART_TX

    @dbus_property(access=PropertyAccess.READ)
    def Flags(self) -> "as":
        return ["notify"]


class UartRx(ServiceInterface):
    def __init__(self, path):
        super().__init__("org.bluez.GattCharacteristic1")
        self.path = path

    @method()
    def WriteValue(self, value: "ay", _opts: "a{sv}"):
        print(ts(), "RX", bytes(value).hex())

    @dbus_property(access=PropertyAccess.READ)
    def Service(self) -> "o":
        return self.path.rsplit("/", 1)[0]

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> "s":
        return UART_RX

    @dbus_property(access=PropertyAccess.READ)
    def Flags(self) -> "as":
        return ["write", "write-without-response"]


# ───── Advertisement object ────────────────────────────────────────────────
class BridgeAd(ServiceInterface):
    def __init__(self, service_uuid):
        super().__init__("org.bluez.LEAdvertisement1")
        self._svc = service_uuid

    @dbus_property(access=PropertyAccess.READ)  # required props
    def Type(self) -> "s":
        return "peripheral"

    @dbus_property(access=PropertyAccess.READ)
    def ServiceUUIDs(self) -> "as":
        return [self._svc]

    @dbus_property(access=PropertyAccess.READ)
    def LocalName(self) -> "s":
        return "Bridge"  # <-- EXACT string app scans for

    @method()
    def Release(self):
        pass  # called by BlueZ when ad is removed


# ───── Main ────────────────────────────────────────────────────────────────
async def main():
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

    base = "/org/flowbridge/uart0"
    bus.export(base, UartService(base))
    bus.export(base + "/tx", UartTx(base + "/tx"))
    bus.export(base + "/rx", UartRx(base + "/rx"))

    # pick first adapter that supports advertising
    om = (await proxy(bus, "org.bluez", "/")).get_interface(
        "org.freedesktop.DBus.ObjectManager"
    )
    objs = await om.call_get_managed_objects()
    adapter = next(p for p, i in objs.items() if "org.bluez.LEAdvertisingManager1" in i)

    # register GATT application
    gatt_mgr = (await proxy(bus, "org.bluez", adapter)).get_interface(
        "org.bluez.GattManager1"
    )
    await gatt_mgr.call_register_application("/org/flowbridge", {})

    # register advertisement
    ad_path = "/org/flowbridge/adv0"
    bus.export(ad_path, BridgeAd(UART_SVC))
    adv_mgr = (await proxy(bus, "org.bluez", adapter)).get_interface(
        "org.bluez.LEAdvertisingManager1"
    )
    await adv_mgr.call_register_advertisement(ad_path, {})
    print(ts(), 'Advertising as "Bridge" with UART service')

    # keep running
    await asyncio.Event().wait()


if __name__ == "__main__":
    if sys.version_info < (3, 9):
        print("Python 3.9+ required")
        sys.exit(1)
    asyncio.run(main())
