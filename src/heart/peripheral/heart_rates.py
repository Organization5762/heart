import asyncio
import logging
from typing import Dict, Iterator, List, Set

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice
from heart.peripheral import Peripheral

# Heart Rate Service and Characteristic UUIDs
HEART_RATE_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HEART_RATE_CHARACTERISTIC_UUID = "00002a37-0000-1000-8000-00805f9b34fb"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("bluetooth.log"), logging.StreamHandler()],
)
logger = logging.getLogger("HeartRateManager")


# This dictionary is what external code will use to get the BPM data for each sensor.
current_bpms: dict[str, int] = {}


# This is a single peripheral that manages all heart rate sensors.
# It is responsible for scanning for and connecting to Bluetooth Heart Rate sensors,
# collecting BPM data, and managing the connection to each sensor.
class HeartRateManager(Peripheral):
    """
    A peripheral that scans for and connects to Bluetooth Heart Rate sensors,
    collecting BPM data.
    """

    def __init__(self) -> None:
        self._connected_clients: Dict[str, BleakClient] = {}
        self._managing_tasks: Dict[str, asyncio.Task] = {}

    @staticmethod
    def detect() -> Iterator["HeartRateManager"]:
        """Detects the presence of the Heart Rate Sensor system."""
        # This peripheral manages the capability, so we always yield one instance.
        yield HeartRateManager()

    def _parse_hr_measurement(self, data: bytearray) -> int:
        """Parses the heart rate measurement data (UINT8 or UINT16 format)."""
        try:
            flags = data[0]
            hr_format_bit = flags & 0x01
            if hr_format_bit:  # UINT16
                if len(data) < 3:
                    raise ValueError("UINT16 data too short")
                bpm = int.from_bytes(data[1:3], byteorder="little")
            else:  # UINT8
                if len(data) < 2:
                    raise ValueError("UINT8 data too short")
                bpm = data[1]
            return bpm
        except (IndexError, ValueError) as e:
            logger.warning(f"Could not parse HR data: {data.hex()} ({e})")
            return -1  # Indicate invalid data

    async def _handle_hr_notification(
        self, client: BleakClient, sender_handle: int, data: bytearray
    ) -> None:
        """Callback for heart rate notifications."""
        bpm = self._parse_hr_measurement(data)
        if bpm != -1:
            current_bpms[client.address] = bpm
            logger.debug(
                f"Received HR: {bpm} BPM from {client.address} ({current_bpms})"
            )

    async def _manage_connection(self, device: BLEDevice) -> None:
        """Connects to a device, starts notifications, and handles disconnection."""
        address = device.address
        logger.info(f"Attempting to connect to {address}")
        disconnected_event = asyncio.Event()
        client = BleakClient(
            device,
            disconnected_callback=lambda c: (
                disconnected_event.set(),
                logger.warning(f"Disconnected callback triggered for {c.address}"),
            ),
        )

        try:
            await client.connect(timeout=20.0)
            if client.is_connected:
                logger.info(f"Connected to {address}")
                self._connected_clients[address] = client

                await client.start_notify(
                    HEART_RATE_CHARACTERISTIC_UUID,
                    lambda handle, data: asyncio.create_task(
                        self._handle_hr_notification(client, handle, data)
                    ),
                )
                logger.info(f"Started HR notifications for {address}")
                await disconnected_event.wait()

        except Exception as e:
            logger.error(f"Error managing connection to {address}: {e}", exc_info=True)
        finally:
            logger.warning(f"Device {address} processing finished or disconnected.")
            if client.is_connected:
                try:
                    # Check if notifications were started before stopping
                    if (
                        HEART_RATE_CHARACTERISTIC_UUID
                        in client.services.characteristics
                    ):  # Basic check
                        char = client.services.get_characteristic(
                            HEART_RATE_CHARACTERISTIC_UUID
                        )
                        # A more robust check might involve tracking notification state externally
                        # if notifications_active_for_char(char):
                        await client.stop_notify(HEART_RATE_CHARACTERISTIC_UUID)
                except Exception as e:
                    logger.error(f"Error stopping notify for {address}: {e}")
                try:
                    await client.disconnect()
                except Exception as e:
                    logger.error(f"Error disconnecting {address}: {e}")

            self._connected_clients.pop(address, None)
            self._managing_tasks.pop(address, None)  # Remove task reference
            current_bpms.pop(address, None)
            logger.info(f"Removed {address} from current_bpms")

    async def _scan_and_manage(self) -> None:
        """Scans for devices and launches connection management tasks."""
        scanner = BleakScanner(
            service_uuids=[HEART_RATE_SERVICE_UUID],
            detection_callback=self._handle_detection,
        )

        logger.info("Starting scanner for HR devices...")
        await scanner.start()

        try:
            while True:
                await asyncio.sleep(
                    30
                )  # Keep scanner alive and periodically clean tasks
                await self._cleanup_finished_tasks()
        except asyncio.CancelledError:
            logger.info("Scan task cancelled.")
        finally:
            logger.info("Stopping scanner...")
            await scanner.stop()
            await self._cleanup_finished_tasks(cancel_remaining=True)

    async def _handle_detection(self, device: BLEDevice, advertisement_data):
        """Callback for BleakScanner device detection."""
        logger.debug(
            f"Discovered HR device: {device.address} - {advertisement_data.local_name}"
        )
        if (
            device.address not in self._connected_clients
            and device.address not in self._managing_tasks
        ):
            logger.info(f"Found new HR device {device.address}, attempting to manage.")
            task = asyncio.create_task(self._manage_connection(device))
            self._managing_tasks[device.address] = task

    async def _cleanup_finished_tasks(self, cancel_remaining: bool = False):
        """Cleans up tasks that have completed or cancels them if requested."""
        addresses_to_remove = set()
        for address, task in self._managing_tasks.items():
            if task.done():
                addresses_to_remove.add(address)
                try:
                    exc = task.exception()
                    if exc:
                        logger.warning(
                            f"Task for {address} finished with exception: {exc}",
                            exc_info=exc,
                        )
                except asyncio.CancelledError:
                    logger.info(f"Task for {address} was cancelled.")
                except Exception as e:
                    logger.error(
                        f"Unexpected error getting exception for task {address}: {e}"
                    )
            elif cancel_remaining:
                task.cancel()
                addresses_to_remove.add(
                    address
                )  # Assume cancellation will lead to removal

        for address in addresses_to_remove:
            logger.debug(f"Cleaning up task reference for {address}")
            self._managing_tasks.pop(address, None)

    def run(self) -> None:
        """Runs the heart rate monitoring logic using asyncio."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        main_task = loop.create_task(self._scan_and_manage())
        try:
            loop.run_until_complete(main_task)
        except KeyboardInterrupt:
            logger.info("HeartRateManager run loop stopped by user.")
        except Exception as e:
            logger.exception(f"Error in HeartRateManager run loop: {e}")
        finally:
            logger.info("Shutting down HeartRateManager run loop...")
            main_task.cancel()
            # Run loop until the main task is cancelled and cleanup happens
            try:
                # Allow cancellation to propagate and cleanup tasks to run
                loop.run_until_complete(main_task)
            except asyncio.CancelledError:
                logger.info("Main task successfully cancelled.")
            except Exception as e:
                logger.error(f"Error during final loop run: {e}")

            # Explicitly close clients that might still be connected
            # (though _manage_connection should handle this)
            # Run loop briefly to allow disconnects to complete
            loop.run_until_complete(self._shutdown_clients())
            loop.close()
            logger.info("HeartRateManager run loop finished.")

    async def _shutdown_clients(self):
        """Ensure all clients are disconnected during shutdown"""
        disconnect_tasks = []
        for address, client in self._connected_clients.items():
            if client.is_connected:
                logger.info(f"Explicitly disconnecting {address} during shutdown")
                disconnect_tasks.append(asyncio.create_task(client.disconnect()))
        await asyncio.gather(*disconnect_tasks, return_exceptions=True)
        self._connected_clients.clear()
