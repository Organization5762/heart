# from collections import defaultdict
# from dataclasses import dataclass
# from typing import Any, Callable

# import pygame
# from heart.utilities.env import Configuration
# from pygame.event import Event

# class InputBus:
#     def __init__(self) -> None:
#         self.subcribers = defaultdict(list)

#     def subscribe(self, event_type: str, callback: Callable[[Input], Event | None]):
#         self.subcribers[event_type].append(callback)

#     def submit(self, input: Input) -> None:
#         if Configuration.is_debug_mode():
#             print(input)

#         # Convert into primary event loop event
#         for callback in self.subcribers.get(input.event_type, []):
#             event = callback(input)
#             if event is not None:
#                 pygame.event.post(event)
