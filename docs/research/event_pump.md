# Event Pump Extraction Research Note

## Problem Statement

Document the runtime change that separates pygame event processing from the main loop so the control flow is easier to audit and mypy can track the event handling surface area.

## Materials

- Local checkout of the Heart repository.
- Python environment with the dependencies listed in `pyproject.toml` installed.
- `src/heart/runtime/game_loop.py` and `src/heart/runtime/event_pump.py`.

## Notes

- The main loop now delegates pygame event draining and joystick reset handling to `EventPump`, keeping `GameLoop` focused on orchestration and rendering.
- `EventPump` is responsible for detecting `pygame.QUIT` and joystick reset events and reporting back to the loop via a boolean running flag.
- The runtime diagram in `docs/code_flow.md` includes the event pump alongside the loop and other runtime services for future audits.

## Sources

- `src/heart/runtime/event_pump.py`
- `src/heart/runtime/game_loop.py`
- `docs/code_flow.md`
