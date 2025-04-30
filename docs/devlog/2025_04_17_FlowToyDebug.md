# USB Bridge

## Looking for USB
* Doesn't show up as an LSB via `lsusb` or `lsblk`

## Scanning Bluetooth
Scanned bluetooth ports via `sudo hcitool lescan --duplicates`
found `... Flowtoys Bridge`

## Ran script
```python
import asyncio
from bleak import BleakClient

ADDRESS = "..."

async def explore():
    async with BleakClient(ADDRESS) as client:
        svcs = await client.get_services()
        for svc in svcs:
            print(f"[Service] {svc.uuid}:")
            for char in svc.characteristics:
                props = ",".join(char.properties)
                print(f"  └─ {char.uuid}  (handle: {char.handle}  props: {props})")
                # If it’s readable:
                if "read" in char.properties:
                    val = await client.read_gatt_char(char.uuid)
                    print(f"     → {bytes(val).hex()}")

asyncio.run(explore())
```

To try to figure out what's going on with it

It declares the following
```bash
[Service] 00001801-0000-1000-8000-00805f9b34fb:
[Service] 49550001-aad5-59bd-934c-023d807e01d5:
  └─ 49550003-aad5-59bd-934c-023d807e01d5  (handle: 12  props: write-without-response,write)
  └─ 49550004-aad5-59bd-934c-023d807e01d5  (handle: 17  props: write-without-response,write)
  └─ 49550002-aad5-59bd-934c-023d807e01d5  (handle: 14  props: notify)
  └─ 49550005-aad5-59bd-934c-023d807e01d5  (handle: 19  props: write-without-response,write)
  ```

Downloaded the flowtoys app to see if that is also transmitting in an open way so I can just snoop on their IO

There's another service named:
```bash
EA:3C:74:98:B8:5F  EA-3C-74-98-B8-5F     RSSI=-24
FA:AE:A2:B3:EB:59  Flowtoys Bridge       RSSI=-31
5A:0B:DF:43:A9:C3  5A-0B-DF-43-A9-C3     RSSI=-34
71:F3:80:A5:1A:D3  71-F3-80-A5-1A-D3     RSSI=-34
64:2D:96:6C:BE:31  64-2D-96-6C-BE-31     RSSI=-44
```

## Installing Bettercap
This was just divine.