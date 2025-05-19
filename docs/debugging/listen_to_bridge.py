import asyncio
from dataclasses import dataclass

from bleak import BleakClient


DEVICE_ADDRESS = "FA:AE:A2:B3:EB:59"
SERVICE_UUID    = "49550001-aad5-59bd-934c-023d807e01d5"




def notification_handler(sender: int, data: bytearray):
    print(f"[NOTIFY] → {data.hex()}")

async def main():
    async with BleakClient(DEVICE_ADDRESS) as client:
        # Wait for connection
        if not await client.is_connected():
            print("❌ Failed to connect")
            return
        print(f"✅ Connected to {DEVICE_ADDRESS}")

        services = await client.get_services()
        svc = services.get_service(SERVICE_UUID)
        if svc is None:
            print(f"❌ Service {SERVICE_UUID} not found")
            return

        print(f"Service {SERVICE_UUID} characteristics:")
        for char in svc.characteristics:
            props = ",".join(char.properties)
            print(f" • {char.uuid} [{props}]")

            # Subscribe to notifications
            if "notify" in char.properties:
                await client.start_notify(char.uuid, notification_handler)
                print(f"   → Subscribed to NOTIFY on {char.uuid}")

            # Or do a one‑time read
            elif "read" in char.properties:
                val = await client.read_gatt_char(char.uuid)
                print(f"   → READ {char.uuid}: {val.hex()}")

        # Keep the script alive to receive notifications
        print("Listening for notifications…  Press Ctrl+C to exit.")
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())