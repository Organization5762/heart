# CLI command structure research note

## Summary

The loop CLI commands were all defined in a single module, which made it harder to
isolate command responsibilities and to reuse shared setup logic. This change splits the
commands into a dedicated `heart.cli.commands` package and introduces a shared game-loop
builder for the run command so setup stays consistent and focused.

## Notes

- The `run` command now delegates game-loop construction to a shared helper.
- The entry point imports each command explicitly to keep CLI exports clear.

## Materials

- `src/heart/loop.py`
- `src/heart/cli/commands/bench_device.py`
- `src/heart/cli/commands/game_loop.py`
- `src/heart/cli/commands/run.py`
- `src/heart/cli/commands/update_driver.py`
