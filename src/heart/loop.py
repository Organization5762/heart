import os

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import typer

from heart.cli.commands.bench_device import bench_device_command
from heart.cli.commands.run import run_command
from heart.cli.commands.update_driver import update_driver_command

app = typer.Typer()

app.command(name="run")(run_command)
app.command(name="update-driver")(update_driver_command)
app.command(name="bench-device")(bench_device_command)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
