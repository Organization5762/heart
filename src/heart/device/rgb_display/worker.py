import queue
import threading
from typing import Any, Optional

from PIL import Image


class MatrixDisplayWorker:
    """Worker thread that handles sending images to the RGB matrix."""

    def __init__(self, matrix: Any) -> None:
        self.matrix = matrix
        self.offscreen = self.matrix.CreateFrameCanvas()
        self.q: queue.Queue[Optional[Image.Image]] = queue.Queue(maxsize=2)
        self._worker = threading.Thread(
            target=self._run, daemon=True, name="matrix display worker"
        )
        self._worker.start()

    def set_image_async(self, img: Image.Image) -> None:
        try:
            self.q.put_nowait(img)
        except queue.Full:
            _ = self.q.get_nowait()
            self.q.put_nowait(img)

    def shutdown(self) -> None:
        self.q.put(None)
        self._worker.join()

    def _run(self) -> None:
        while True:
            img = self.q.get()
            if img is None:
                break

            self.offscreen.Clear()
            self.offscreen.SetImage(img, 0, 0)
            self.offscreen = self.matrix.SwapOnVSync(self.offscreen)
            self.q.task_done()
