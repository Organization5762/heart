import asyncio
from bleak import BleakScanner

comp_id_to_manufacturer = {
    "0x004C": "Apple Inc.",
    "0x0057": "Harman International Industries, Inc.",
    "0x0065": "HP Inc.",
    "0x03C1": "Ember Technologies, Inc.",
    "0x0075": 'Samsung Electronics Co. Ltd.'
}

async def scan_and_report(timeout: float = 5.0):
    # Do a full discovery, which returns BLEDevice objects with metadata
    devices = await BleakScanner.discover(timeout=timeout)
    # Sort descending by RSSI (strongest first)
    devices = sorted(devices, key=lambda d: d.rssi or -999, reverse=True)

    for dev in devices:
        print(f"{dev.address:>17}  {dev.name or 'Unknown':<20}  RSSI={dev.rssi}")
        md = dev.metadata or {}

        # Local name from the advertisement payload (may differ from dev.name)
        if 'local_name' in md and md['local_name']:
            print(f"  ▸ Adv Local Name: {md['local_name']}")

        # Service UUIDs the device is advertising
        if 'uuids' in md and md['uuids']:
            print(f"  ▸ Service UUIDs: {md['uuids']}")

        # Manufacturer data: keys are Bluetooth‐SIG company IDs, values are raw bytes
        mfg = md.get('manufacturer_data', {})
        if mfg:
            for comp_id, blob in mfg.items():
                key = f"0x{comp_id:04X}"
                name = comp_id_to_manufacturer.get(key, "Unknown")
                print(f"  ▸ Manufacturer ID: {key} [{name}] Data: {blob.hex()}")

        # Service‐specific data (UUID → bytes)
        svcdata = md.get('service_data', {})
        if svcdata:
            for uuid, blob in svcdata.items():
                print(f"  ▸ Service Data [{uuid}]: {blob.hex()}")

        # TX power level (if the advertiser included it)
        if 'tx_power' in md and md['tx_power'] is not None:
            print(f"  ▸ TX Power: {md['tx_power']} dBm")

        print()  # blank line between devices

if __name__ == "__main__":
    asyncio.run(scan_and_report())