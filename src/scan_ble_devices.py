from bluepy.btle import Scanner


def scan_ble_devices():
    scanner = Scanner()
    devices = scanner.scan(10.0)  # Scan for 10 seconds

    for device in devices:
        # if device.addr == "cc:4d:5a:4b:8c:b6".lower():
        print(f"Device {device.addr} ({device.addrType}), RSSI={device.rssi} dB")
        for adtype, desc, value in device.getScanData():
            print(f"  {desc} = {value}")


if __name__ == "__main__":
    scan_ble_devices()
