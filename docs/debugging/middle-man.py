#!/usr/bin/env python3
"""
flow_bridge_proxy.py
────────────────────
• central    Pi ↔ REAL Flowtoys bridge  (Nordic‑UART)
• peripheral phone ↔ Pi                (fake “Flowtoys Bridge”)

Tested on Raspberry Pi 4/5 with BlueZ ≥ 5.64 and Python 3.9‑3.12
"""

import asyncio
from bleak import BleakScanner, BleakClient
from dbus_next.aio import MessageBus
from dbus_next import Variant
from dbus_next.constants import BusType
from dbus_next.service import ServiceInterface, method, dbus_property, PropertyAccess

# ───────────────────────────  UUIDs
UART_SVC = "49550001-aad5-59bd-934c-023d807e01d5"
UART_TX = "49550002-aad5-59bd-934c-023d807e01d5"  # notify  (bridge → Pi → phone)
UART_RX = "49550003-aad5-59bd-934c-023d807e01d5"  # write   (phone  → Pi → bridge)

# ───────────────────────────  queues
from_bridge = asyncio.Queue()  # packets arriving  from REAL bridge
to_bridge = asyncio.Queue()  # packets arriving  from PHONE


# ───────────────────────────  CENTRAL side  (Pi ↔ real bridge)
async def connect_bridge() -> BleakClient:
    print("Scanning for real Flowtoys bridge…")
    dev = None
    for d in await BleakScanner.discover():
        if UART_SVC.lower() in [u.lower() for u in d.metadata.get("uuids", [])]:
            dev = d
            break
    if not dev:
        raise RuntimeError("No Flowtoys bridge advertising")

    client = BleakClient(dev)
    await client.connect()
    print(f"Connected to real bridge {dev.address}")

    # bridge → Pi → phone
    await client.start_notify(
        UART_TX, lambda _, data: from_bridge.put_nowait(bytes(data))
    )

    # phone → Pi → bridge
    async def pump():
        while True:
            pkt = await to_bridge.get()
            await client.write_gatt_char(UART_RX, pkt, False)

    asyncio.create_task(pump())

    return client


# ───────────────────────────  PERIPHERAL side  (phone ↔ Pi)
class UartTx(ServiceInterface):
    """Notify‑only characteristic (Pi → phone)."""

    def __init__(self, path):
        super().__init__("org.bluez.GattCharacteristic1")
        self.path, self.notifying = path, False

    @method()  # StartNotify / StopNotify
    def StartNotify(self):
        self.notifying = True

    @method()
    def StopNotify(self):
        self.notifying = False

    @dbus_property(access=PropertyAccess.READ)
    def Service(self) -> "o":
        return self.path.rsplit("/", 1)[0]

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> "s":
        return UART_TX

    @dbus_property(access=PropertyAccess.READ)
    def Flags(self) -> "as":
        return ["notify"]

    async def push(self, data: bytes):
        if self.notifying:
            self.emit_properties_changed({"Value": Variant("ay", list(data))})


class UartRx(ServiceInterface):
    """Write / Write‑wo‑rsp characteristic (phone → Pi)."""

    def __init__(self, path):
        super().__init__("org.bluez.GattCharacteristic1")
        self.path = path

    @method()
    def WriteValue(self, value: "ay", _opts: "a{sv}"):
        to_bridge.put_nowait(bytes(value))

    @dbus_property(access=PropertyAccess.READ)
    def Service(self) -> "o":
        return self.path.rsplit("/", 1)[0]

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> "s":
        return UART_RX

    @dbus_property(access=PropertyAccess.READ)
    def Flags(self) -> "as":
        return ["write-without-response", "write"]


class UartSvc(ServiceInterface):
    """Primary Nordic‑UART service."""

    def __init__(self, path):
        super().__init__("org.bluez.GattService1")
        self.path = path

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> "s":
        return UART_SVC

    @dbus_property(access=PropertyAccess.READ)
    def Primary(self) -> "b":
        return True


# helper to build BlueZ proxy objects
async def proxy(bus, name, path):
    xml = await bus.introspect(name, path)
    return bus.get_proxy_object(name, path, xml)


async def make_peripheral(bus: MessageBus):
    """Register GATT objects + advertisement."""
    base = "/org/flowproxy/uart0"
    svc_path, tx_path, rx_path = base, base + "/tx", base + "/rx"

    svc = UartSvc(svc_path)
    tx = UartTx(tx_path)
    rx = UartRx(rx_path)

    bus.export(svc_path, svc)
    bus.export(tx_path, tx)
    bus.export(rx_path, rx)

    # 1. find adapter that supports advertising
    obj_mgr = (await proxy(bus, "org.bluez", "/")).get_interface(
        "org.freedesktop.DBus.ObjectManager"
    )
    objs = await obj_mgr.call_get_managed_objects()
    adapter = next(p for p, i in objs.items() if "org.bluez.LEAdvertisingManager1" in i)

    # 2. register GATT application
    gatt_mgr = (await proxy(bus, "org.bluez", adapter)).get_interface(
        "org.bluez.GattManager1"
    )
    await gatt_mgr.call_register_application("/org/flowproxy", {})

    # 3. advertise
    ad_props = {
        "Type": Variant("s", "peripheral"),
        "ServiceUUIDs": Variant("as", [UART_SVC]),
        "LocalName": Variant("s", "Flowtoys Bridge"),
    }
    ad_path = "/org/flowproxy/adv0"

    class Adv(ServiceInterface):
        def __init__(self):
            super().__init__("org.bluez.LEAdvertisement1")

        @method()  # dummy Release method
        def Release(self):
            pass

        def get_properties(self):
            return ad_props

    bus.export(ad_path, Adv())

    adv_mgr = (await proxy(bus, "org.bluez", adapter)).get_interface(
        "org.bluez.LEAdvertisingManager1"
    )
    await adv_mgr.call_register_advertisement(ad_path, {})

    print("Peripheral: advertising as “Flowtoys Bridge”")
    return tx


# ───────────────────────────  MAIN
async def main():

    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

    # peripheral
    tx_char = await make_peripheral(bus)

    # bridge → phone relay
    async def phone_tx_loop():
        while True:
            pkt = await from_bridge.get()
            await tx_char.push(pkt)

    asyncio.create_task(phone_tx_loop())

    # central
    await connect_bridge()  # run forever

    await asyncio.Event().wait()


asyncio.run(main())
