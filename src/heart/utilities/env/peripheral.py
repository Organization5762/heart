import os

from heart.utilities.env.enums import BleUartBufferStrategy


class PeripheralConfiguration:
    @classmethod
    def ble_uart_buffer_strategy(cls) -> BleUartBufferStrategy:
        strategy = os.environ.get(
            "HEART_BLE_UART_BUFFER_STRATEGY", "bytes"
        ).strip().lower()
        try:
            return BleUartBufferStrategy(strategy)
        except ValueError as exc:
            raise ValueError(
                "HEART_BLE_UART_BUFFER_STRATEGY must be 'bytes' or 'text'"
            ) from exc
