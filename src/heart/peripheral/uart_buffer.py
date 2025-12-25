from __future__ import annotations

from collections.abc import Callable, Iterable

from heart.utilities.env import BleUartBufferStrategy, Configuration


class UartMessageBuffer:
    """Incrementally buffer UART payloads and yield delimited messages."""

    __slots__ = (
        "_strategy",
        "_delimiter",
        "_text_delimiter",
        "_bytes_buffer",
        "_text_buffer",
    )

    def __init__(
        self,
        *,
        strategy_provider: Callable[[], BleUartBufferStrategy] | None = None,
        delimiter: bytes = b"\n",
    ) -> None:
        self._strategy = (
            strategy_provider or Configuration.ble_uart_buffer_strategy
        )()
        self._delimiter = delimiter
        self._text_delimiter = delimiter.decode("utf-8", errors="ignore")
        self._bytes_buffer = bytearray()
        self._text_buffer = ""

    @property
    def strategy(self) -> BleUartBufferStrategy:
        return self._strategy

    @property
    def buffer_size(self) -> int:
        if self._strategy == BleUartBufferStrategy.TEXT:
            return len(self._text_buffer)
        return len(self._bytes_buffer)

    def append(self, data: bytes | bytearray) -> Iterable[str | bytes]:
        if self._strategy == BleUartBufferStrategy.TEXT:
            decoded = data.decode("utf-8", errors="ignore")
            self._text_buffer += decoded
            return self._drain_text()
        self._bytes_buffer.extend(data)
        return self._drain_bytes()

    def clear(self) -> None:
        self._bytes_buffer.clear()
        self._text_buffer = ""

    def _drain_bytes(self) -> list[bytes]:
        messages: list[bytes] = []
        delimiter = self._delimiter
        delimiter_len = len(delimiter)
        while True:
            try:
                index = self._bytes_buffer.index(delimiter)
            except ValueError:
                break
            line = bytes(self._bytes_buffer[:index])
            del self._bytes_buffer[: index + delimiter_len]
            messages.append(line)
        return messages

    def _drain_text(self) -> list[str]:
        messages: list[str] = []
        delimiter = self._text_delimiter
        delimiter_len = len(delimiter)
        while True:
            index = self._text_buffer.find(delimiter)
            if index == -1:
                break
            line = self._text_buffer[:index]
            self._text_buffer = self._text_buffer[index + delimiter_len :]
            messages.append(line)
        return messages
