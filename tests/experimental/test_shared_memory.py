import importlib
import sys
import time
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTAL_SRC = ROOT / "experimental" / "isolated_rendering" / "src"


def _load_experimental_classes():
    if str(EXPERIMENTAL_SRC) not in sys.path:
        sys.path.insert(0, str(EXPERIMENTAL_SRC))

    if not EXPERIMENTAL_SRC.exists():
        pytest.skip(
            "experimental isolated_rendering sources are not available",
            allow_module_level=True,
        )

    buffer_module = importlib.import_module("isolated_rendering.buffer")
    shared_module = importlib.import_module("isolated_rendering.shared_memory")
    return (
        buffer_module.FrameBuffer,
        shared_module.SharedMemoryError,
        shared_module.SharedMemoryFrameWriter,
        shared_module.SharedMemoryWatcher,
    )


(
    FrameBuffer,
    SharedMemoryError,
    SharedMemoryFrameWriter,
    SharedMemoryWatcher,
) = _load_experimental_classes()


def _wait_for(predicate, timeout: float = 1.0) -> bool:
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


class TestExperimentalSharedMemory:
    """Group Experimental Shared Memory tests so experimental shared memory behaviour stays reliable. This preserves confidence in experimental shared memory for end-to-end scenarios."""

    def test_shared_memory_roundtrip_updates_frame_buffer(self, tmp_path: Path) -> None:
        """Verify that the shared memory watcher reflects images written by the frame writer. This confirms the IPC bridge works for external render processes to stream frames."""
        size = (4, 4)
        target = FrameBuffer(size=size)
        watcher = SharedMemoryWatcher(tmp_path / "frame.mmap", target, poll_interval=0.0005)
        writer = SharedMemoryFrameWriter(tmp_path / "frame.mmap", size=size)

        try:
            watcher.start()
            image = Image.new("RGB", size, (10, 20, 30))
            writer.write_image(image)

            assert _wait_for(
                lambda: list(target.snapshot().image.getdata())[0] == (10, 20, 30)
            )
        finally:
            watcher.stop()
            writer.close()



    def test_writer_rejects_wrong_payload_size(self, tmp_path: Path) -> None:
        """Verify that SharedMemoryFrameWriter rejects byte payloads that are smaller than the frame size. This avoids corrupting shared memory by catching truncated writes early."""
        path = tmp_path / "frame.mmap"
        writer = SharedMemoryFrameWriter(path, size=(2, 2))
        try:
            with pytest.raises(SharedMemoryError):
                writer.write_bytes(b"short")
        finally:
            writer.close()
