from __future__ import annotations

from collections.abc import Callable, Iterable

from manyfold.sensor_io import DelimitedMessageBuffer

from heart.utilities.env import BleUartBufferStrategy, Configuration


class UartMessageBuffer:
    """Incrementally buffer UART payloads and yield delimited messages."""

    __slots__ = (
        "_strategy",
        "_buffer",
    )

    def __init__(
        self,
        *,
        strategy_provider: Callable[[], BleUartBufferStrategy] | None = None,
        delimiter: bytes = b"\n",
    ) -> None:
        self._strategy = (strategy_provider or Configuration.ble_uart_buffer_strategy)()
        self._buffer = DelimitedMessageBuffer(
            delimiter=delimiter,
            mode="text" if self._strategy == BleUartBufferStrategy.TEXT else "bytes",
        )

    @property
    def strategy(self) -> BleUartBufferStrategy:
        return self._strategy

    @property
    def buffer_size(self) -> int:
        return self._buffer.buffer_size

    def append(self, data: bytes | bytearray) -> Iterable[str | bytes]:
        return self._buffer.append(data)

    def clear(self) -> None:
        self._buffer.clear()
