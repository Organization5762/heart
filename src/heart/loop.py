import os

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import typer

from heart.cli.loop_commands import (bench_device_command, run_command,
                                     update_driver_command)

app = typer.Typer()

app.command()(run_command)
app.command()(update_driver_command)
app.command(name="bench-device")(bench_device_command)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
