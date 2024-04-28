import math
import random


class ObjectLocation:
    def __init__(self) -> None:
        self.current_location = (0, 0)

        self.is_initialized = False

    def _initialize(self, window) -> None:
        self.current_location = (random.randint(0, window.get_width()), random.randint(0, window.get_height()))

        self.is_initialized = True

    def right(self, x: int) -> None:
        return self.move_x(x)

    def left(self, x: int) -> None:
        return self.move_x(-x)

    def up(self, y: int) -> None:
        return self.move_y(-y)

    def down(self, y: int) -> None:
        return self.move_y(y)

    def move_x(self, x: int) -> None:
        self.current_location = (self.current_location[0] + x, self.current_location[1])

    def move_y(self, y: int) -> None:
        self.current_location = (self.current_location[0], self.current_location[1] + y)

    def get_y(self) -> int:
        return self.current_location[1]

    def get_x(self) -> int:
        return self.current_location[0]

    def process(self, surface, window, clock):
        if not self.is_initialized:
            self._initialize(window)

        window.blit(surface, self.current_location)

class UpAndDown:
    def __init__(self) -> None:
        self.moving_direction = 1
        self.location = ObjectLocation()

    def process(self, surface, window, clock, reference_objects) -> None:
        if self.location.get_y() >= (window.get_height() - 100):
            self.moving_direction = -1
        elif self.location.get_y() <= 0:
            self.moving_direction = 1

        self.location.move_y(1 * self.moving_direction)
        self.location.process(surface, window, clock)

class SideToSide:
    def __init__(self) -> None:
        self.moving_direction = 1
        self.location = ObjectLocation()

    def process(self, surface, window, clock, reference_objects) -> None:
        if self.location.get_x() >= (window.get_width() - 100):
            self.moving_direction = -1
        elif self.location.get_x() <= 0:
            self.moving_direction = 1

        self.location.move_x(1 * self.moving_direction)
        self.location.process(surface, window, clock)

class Orbit:
    def __init__(self) -> None:
        self.angle = 0
        self.radius = 100
        # Eh this is just for demo but it helps
        self.center = (random.randint(100, 300), random.randint(100, 300))
        self.location = ObjectLocation()

    def process(self, surface, window, clock, reference_objects: list[ObjectLocation]) -> None:
        self.angle += 0.01  # Adjust this value to change the speed of the orbit
        if self.angle >= 2 * math.pi:
            self.angle = 0

        x = self.center[0] + self.radius * math.cos(self.angle)
        y = self.center[1] + self.radius * math.sin(self.angle)

        # Calculate the difference between the new position and the current position
        dx = x - self.location.get_x()
        dy = y - self.location.get_y()

        # Use the move_x and move_y functions to update the location
        self.location.move_x(dx)
        self.location.move_y(dy)

        self.location.process(surface, window, clock)

import math
import random

class ChaoticOrbit:
    def __init__(self) -> None:
        self.angle = random.uniform(0, 2 * math.pi)
        self.radius = 100
        self.center = (random.randint(100, 300), random.randint(100, 300))
        self.location = ObjectLocation()
        self.speed = 1
        self.interaction_range = 100
        self.repulsion_range = 50  # Range for repulsion, smaller than interaction range
        self.interaction_strength = 0.05
        self.repulsion_strength = 0.5  # Strength of the repulsion force
        self.inertia = 0.1  # Inertia factor to smooth out changes in acceleration

    def process(self, surface, window, clock, reference_objects: list[ObjectLocation]) -> None:
        # Update position based on current angle and speed
        self.angle += self.speed * 0.05
        x = self.center[0] + self.radius * math.cos(self.angle)
        y = self.center[1] + self.radius * math.sin(self.angle)
        self.location.current_location = (x, y)

        # Interact with other objects
        new_angle = self.angle
        for ref_obj in reference_objects:
            if ref_obj != self.location:
                dx = ref_obj.get_x() - self.location.get_x()
                dy = ref_obj.get_y() - self.location.get_y()
                distance = math.sqrt(dx**2 + dy**2)

                if distance < self.repulsion_range:  # Repulsion condition
                    angle_to_other = math.atan2(dy, dx)
                    new_angle -= self.repulsion_strength * math.sin(self.angle - angle_to_other)

                elif distance < self.interaction_range:  # Attraction condition
                    angle_to_other = math.atan2(dy, dx)
                    new_angle += self.interaction_strength * math.sin(angle_to_other - self.angle)

        # Smooth out the angle change using inertia
        self.angle += (new_angle - self.angle) * self.inertia

        # Ensure the angle stays within the range [0, 2*pi]
        self.angle %= 2 * math.pi

        # Update the location on the window
        self.location.process(surface, window, clock)
