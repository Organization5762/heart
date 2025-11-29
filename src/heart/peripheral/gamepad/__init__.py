"""Convenience imports for the gamepad peripheral."""

from .gamepad import Gamepad as Gamepad
from .gamepad import GamepadIdentifier as GamepadIdentifier

# TODO Observable
# def _process_gamepad_key_input(self, peripheral_manager: PeripheralManager):
#         gamepad = peripheral_manager.get_gamepad()
#         mapping = BitDoLite2Bluetooth() if Configuration.is_pi() else BitDoLite2()

#         switch = peripheral_manager._deprecated_get_main_switch()
#         state = self.get_switch_state()
#         gamepad.update()

#         # payload = None
#         # if gamepad.is_connected() and self.in_select_mode:
#         #     # print("gamepad connectee")
#         #     x_dir, y_dir = gamepad.get_dpad_value()
#         #     if x_dir != 0 and x_dir != self.gamepad_last_frame["DPAD_X"]:
#         #         payload = {
#         #             "event_type": SWITCH_ROTATION,
#         #             "data": state.rotational_value + x_dir,
#         #         }
#         #     self.gamepad_last_frame["DPAD_X"] = x_dir
#         #     if y_dir != 0 and y_dir != self.gamepad_last_frame["DPAD_Y"]:
#         #         payload = {"event_type": BUTTON_LONG_PRESS, "data": 1}
#         #     self.gamepad_last_frame["DPAD_Y"] = y_dir

#         # # i.e. this branch to listen for exit request when inside a scene
#         # elif gamepad.is_connected():
#         #     # i.e. press plus + minus to exit from any mode
#         #     plus_tapped = gamepad.is_held(mapping.BUTTON_PLUS)
#         #     minus_tapped = gamepad.is_held(mapping.BUTTON_MINUS)
#         #     if plus_tapped and minus_tapped:
#         #         payload = {"event_type": BUTTON_LONG_PRESS, "data": 1}

#         if payload is not None:
#             switch.update_due_to_data(payload)
#             state = self.get_switch_state()

#         pygame.display.set_caption(
#             "R: {rot}, NR: {nr}, B: {button}, BL: {long}".format(
#                 rot=state.rotational_value,
#                 nr=state.rotation_since_last_button_press,
#                 button=state.button_value,
#                 long=state.long_button_value,
#             )
#         )

#     def _process_debugging_key_presses(
#         self, peripheral_manager: PeripheralManager
#     ) -> None:
#         # Only run this if not on the Pi
#         if Configuration.is_pi() and not Configuration.is_x11_forward():
#             return

#         keys = pygame.key.get_pressed()

#         switch = peripheral_manager._deprecated_get_main_switch()
#         state = self.get_switch_state()
#         payload = None

#         # TODO: Start coming up with a better way of handling this + simulating N peripherals all with different signals
#         DEFAULT_PRODUCER_ID = 0
#         if keys[pygame.K_LEFT] and not self.key_pressed_last_frame[pygame.K_LEFT]:
#             payload = {
#                 "event_type": SWITCH_ROTATION,
#                 "producer_id": DEFAULT_PRODUCER_ID,
#                 "data": state.rotational_value - 1,
#             }
#         self.key_pressed_last_frame[pygame.K_LEFT] = keys[pygame.K_LEFT]

#         if keys[pygame.K_RIGHT] and not self.key_pressed_last_frame[pygame.K_RIGHT]:
#             payload = {
#                 "event_type": SWITCH_ROTATION,
#                 "producer_id": DEFAULT_PRODUCER_ID,
#                 "data": state.rotational_value + 1,
#             }
#         self.key_pressed_last_frame[pygame.K_RIGHT] = keys[pygame.K_RIGHT]

#         if keys[pygame.K_UP] and not self.key_pressed_last_frame[pygame.K_UP]:
#             payload = {
#                 "event_type": BUTTON_LONG_PRESS,
#                 "producer_id": DEFAULT_PRODUCER_ID,
#                 "data": 1,
#             }
#         self.key_pressed_last_frame[pygame.K_UP] = keys[pygame.K_UP]

#         if keys[pygame.K_DOWN] and not self.key_pressed_last_frame[pygame.K_DOWN]:
#             payload = {
#                 "event_type": BUTTON_PRESS,
#                 "producer_id": DEFAULT_PRODUCER_ID,
#                 "data": 1,
#             }

#         self.key_pressed_last_frame[pygame.K_DOWN] = keys[pygame.K_DOWN]

#         if payload is not None:
#             switch.update_due_to_data(payload)
#             state = self.get_switch_state()

#         pygame.display.set_caption(
#             "R: {rot}, NR: {nr}, B: {button}, BL: {long}".format(
#                 rot=state.rotational_value,
#                 nr=state.rotation_since_last_button_press,
#                 button=state.button_value,
#                 long=state.long_button_value,
#             )
#         )