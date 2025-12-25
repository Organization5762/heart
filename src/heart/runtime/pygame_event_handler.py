from __future__ import annotations

import pygame

from heart.peripheral.core import events
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class PygameEventHandler:
    def handle_events(self) -> bool:
        running = True
        try:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == events.REQUEST_JOYSTICK_MODULE_RESET:
                    logger.info("resetting joystick module")
                    pygame.joystick.quit()
                    pygame.joystick.init()
        except SystemError:
            # (clem): gamepad shit is weird and can randomly put caught segfault
            #   events on queue, I see allusions to this online, people say
            #   try pygame-ce instead
            logger.exception("Encountered segfaulted event")
        return running
