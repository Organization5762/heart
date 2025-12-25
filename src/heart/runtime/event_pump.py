from __future__ import annotations

import pygame

from heart.peripheral.core import events
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class EventPump:
    """Process pygame events and update runtime flags."""

    def pump(self, running: bool) -> bool:
        try:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == events.REQUEST_JOYSTICK_MODULE_RESET:
                    self._reset_joystick()
        except SystemError:
            # (clem): gamepad input can leave invalid events on the queue.
            logger.exception("Encountered segfaulted event")
        return running

    def _reset_joystick(self) -> None:
        logger.info("resetting joystick module")
        pygame.joystick.quit()
        pygame.joystick.init()
