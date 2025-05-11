import dbus
import dbus.exceptions
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib

BLUEZ_SERVICE_NAME = "org.bluez"
ADAPTER_IFACE = "org.bluez.Adapter1"
LE_ADV_MANAGER_IFACE = "org.bluez.LEAdvertisingManager1"
LE_ADVERTISEMENT_IFACE = "org.bluez.LEAdvertisement1"

ADAPTER_PATH = "/org/bluez/hci0"


class Advertisement(dbus.service.Object):
    PATH_BASE = "/com/example/advertisement"

    def __init__(self, bus, index):
        self.path = self.PATH_BASE + str(index)
        self.bus = bus
        self.ad_type = "broadcast"
        self.service_uuids = ["180F"]  # Battery Service
        self.local_name = "PiBeacon"
        self.include_tx_power = True

        dbus.service.Object.__init__(self, bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    @dbus.service.method(LE_ADVERTISEMENT_IFACE,
                         in_signature="", out_signature="")
    def Release(self):
        print("Advertisement Released")

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.Properties",
                         in_signature="ss", out_signature="v")
    def Get(self, interface, prop):
        if interface != LE_ADVERTISEMENT_IFACE:
            raise dbus.exceptions.DBusException(
                "org.freedesktop.DBus.Error.InvalidArgs",
                "Invalid interface {}".format(interface)
            )

        props = self._get_properties()[LE_ADVERTISEMENT_IFACE]
        if prop not in props:
            raise dbus.exceptions.DBusException(
                "org.freedesktop.DBus.Error.InvalidArgs",
                "Invalid property {}".format(prop)
            )

        return props[prop]

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.Properties",
                         in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != LE_ADVERTISEMENT_IFACE:
            raise dbus.exceptions.DBusException(
                "org.freedesktop.DBus.Error.InvalidArgs",
                "Invalid interface {}".format(interface)
            )

        return self._get_properties()[interface]

    def _get_properties(self):
        return {
            LE_ADVERTISEMENT_IFACE: {
                "Type": dbus.String(self.ad_type),
                "ServiceUUIDs": dbus.Array(self.service_uuids, signature="s"),
                "LocalName": dbus.String(self.local_name),
                "IncludeTxPower": dbus.Boolean(self.include_tx_power),
            }
        }


def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    system_bus = dbus.SystemBus()

    adapter = system_bus.get_object(BLUEZ_SERVICE_NAME, ADAPTER_PATH)
    ad_manager = dbus.Interface(adapter, LE_ADV_MANAGER_IFACE)

    advertisement = Advertisement(system_bus, 0)

    ad_manager.RegisterAdvertisement(advertisement.get_path(), {},
                                     reply_handler=lambda: print("Advertisement registered"),
                                     error_handler=lambda e: print(f"Failed to register ad: {e}"))

    try:
        GLib.MainLoop().run()
    except KeyboardInterrupt:
        print("Terminating...")
        ad_manager.UnregisterAdvertisement(advertisement.get_path())
        GLib.MainLoop().quit()


if __name__ == "__main__":
    main()
