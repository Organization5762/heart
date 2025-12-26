"""Utilities for sharing frames over a memory-mapped file.

The goal of this module is to provide a very small proof of concept for
sharing rendered frames between processes without any socket hop.  The
renderer process (this package) owns the shared memory file and exposes a
``SharedMemoryWatcher`` that keeps the active :class:`FrameBuffer` in sync
whenever another process updates the shared memory contents.

The counterpart exposed to third-party renderers is
``SharedMemoryFrameWriter``.  It is intentionally minimal – it only requires
the caller to provide pixel bytes (or a :class:`PIL.Image.Image`) matching the
configured dimensions.  The writer follows a very small
"odd/even" protocol around a monotonically increasing version counter so that
the reader never observes partially written frames.

``SharedMemoryWatcher`` simply polls the mapped file.  This is sufficient for a
proof-of-concept implementation and keeps the design extremely small.  It can
be replaced with event based notifications in the future if we need to scale
the design beyond an experiment.
"""

from __future__ import annotations

import mmap
import os
import struct
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image

from .buffer import FrameBuffer

MAGIC = b"HRMM"
_HEADER = struct.Struct("<4sHHQ")  # magic, width, height, version
_HEADER_SIZE = _HEADER.size
_VERSION_SIZE = struct.calcsize("<Q")
_VERSION_OFFSET = _HEADER_SIZE - _VERSION_SIZE
READ_RETRY_SLEEP_SECONDS = 0.0005
DEFAULT_POLL_INTERVAL_SECONDS = 0.002


def _pixel_stride(mode: str) -> int:
    return len(mode)


def _frame_size(width: int, height: int, mode: str) -> int:
    return width * height * _pixel_stride(mode)


@dataclass
class _SharedMemoryMapping:
    fd: int
    mm: mmap.mmap
    size: int


class SharedMemoryError(RuntimeError):
    """Raised when the shared memory file cannot be used."""


class SharedMemoryFile:
    """Helper around a shared memory file containing frame data."""

    def __init__(self, path: Path, size: Tuple[int, int], mode: str = "RGB") -> None:
        self.path = Path(path)
        self.width, self.height = size
        self.mode = mode
        self._expected_frame_bytes = _frame_size(self.width, self.height, mode)
        self._mapping: Optional[_SharedMemoryMapping] = None

    # -- lifecycle -----------------------------------------------------------------
    def _open(self) -> _SharedMemoryMapping:
        if self._mapping is not None:
            return self._mapping

        flags = os.O_RDWR | os.O_CREAT
        fd = os.open(self.path, flags, 0o600)
        try:
            total_size = _HEADER_SIZE + self._expected_frame_bytes
            current_size = os.fstat(fd).st_size
            if current_size != total_size:
                os.ftruncate(fd, total_size)

            mm = mmap.mmap(fd, total_size, access=mmap.ACCESS_WRITE)
            self._mapping = _SharedMemoryMapping(fd=fd, mm=mm, size=total_size)
            self._maybe_initialize_header(mm)
            return self._mapping
        except Exception:
            os.close(fd)
            raise

    def close(self) -> None:
        if self._mapping is None:
            return
        self._mapping.mm.close()
        os.close(self._mapping.fd)
        self._mapping = None

    # -- header helpers -------------------------------------------------------------
    @staticmethod
    def _read_header(mm: mmap.mmap) -> tuple[bytes, int, int, int]:
        return _HEADER.unpack_from(mm, 0)

    def _maybe_initialize_header(self, mm: mmap.mmap) -> None:
        magic, width, height, version = self._read_header(mm)
        if magic != MAGIC or width != self.width or height != self.height:
            mm.seek(0)
            mm.write(_HEADER.pack(MAGIC, self.width, self.height, 0))
            mm.flush()
        elif version % 2 != 0:
            # If a crashed writer left the version counter odd, normalise it.
            self._write_version(mm, version + 1)

    @staticmethod
    def _write_version(mm: mmap.mmap, version: int) -> None:
        mm.seek(_VERSION_OFFSET)
        mm.write(struct.pack("<Q", version))
        mm.flush()

    @staticmethod
    def _read_version(mm: mmap.mmap) -> int:
        _, _, _, version = _HEADER.unpack_from(mm, 0)
        return version

    # -- frame access ----------------------------------------------------------------
    def write_pixels(self, payload: bytes) -> int:
        if len(payload) != self._expected_frame_bytes:
            raise SharedMemoryError(
                f"Expected {self._expected_frame_bytes} bytes but received {len(payload)}"
            )

        mapping = self._open()
        mm = mapping.mm
        version = self._read_version(mm)
        next_version = version + 1
        # Odd version signals "writer in progress".
        self._write_version(mm, next_version)
        mm.seek(_HEADER_SIZE)
        mm.write(payload)
        mm.flush()
        committed_version = next_version + 1
        self._write_version(mm, committed_version)
        return committed_version

    def read_pixels_if_updated(self, last_version: int) -> tuple[int, Optional[bytes]]:
        mapping = self._open()
        mm = mapping.mm
        while True:
            version = self._read_version(mm)
            if version % 2 == 1:
                # Writer in progress. Give it a moment.
                time.sleep(READ_RETRY_SLEEP_SECONDS)
                continue
            if version == last_version:
                return version, None
            mm.seek(_HEADER_SIZE)
            payload = mm.read(self._expected_frame_bytes)
            version_after = self._read_version(mm)
            if version != version_after:
                # A concurrent writer updated the buffer while we were reading. Try again.
                continue
            return version, payload


class SharedMemoryFrameWriter:
    """Tiny helper for writing RGB frames into a shared memory file."""

    def __init__(self, path: Path, size: Tuple[int, int], mode: str = "RGB") -> None:
        self._file = SharedMemoryFile(path, size=size, mode=mode)
        self.mode = mode

    def write_image(self, image: Image.Image) -> int:
        frame = image.convert(self.mode)
        if frame.size != (self._file.width, self._file.height):
            raise SharedMemoryError(
                f"Image size {frame.size} does not match expected {(self._file.width, self._file.height)}"
            )
        return self.write_bytes(frame.tobytes())

    def write_bytes(self, payload: bytes) -> int:
        return self._file.write_pixels(payload)

    def close(self) -> None:
        self._file.close()


class SharedMemoryWatcher:
    """Background worker that mirrors a shared memory file into a ``FrameBuffer``."""

    def __init__(
        self,
        path: Path,
        frame_buffer: FrameBuffer,
        poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
    ) -> None:
        self._file = SharedMemoryFile(path, size=frame_buffer.size, mode=frame_buffer.mode)
        self._frame_buffer = frame_buffer
        self._poll_interval = poll_interval
        self._last_version = 0
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="SharedMemoryWatcher", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()
            self._thread = None
        self._file.close()

    # -- main loop ------------------------------------------------------------------
    def _run(self) -> None:
        while not self._stop_event.is_set():
            version, payload = self._file.read_pixels_if_updated(self._last_version)
            if payload is None:
                time.sleep(self._poll_interval)
                continue

            image = Image.frombytes(self._frame_buffer.mode, self._frame_buffer.size, payload)
            self._frame_buffer.update_image(image)
            self._last_version = version
