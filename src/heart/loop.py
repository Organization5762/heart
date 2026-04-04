import os

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import typer

from heart.cli.commands.bench_device import bench_device_command
from heart.cli.commands.check_health import check_health_command
from heart.cli.commands.flowtoy import app as flowtoy_app
from heart.cli.commands.run import run_command
from heart.cli.commands.run_beats import run_beats_command
from heart.cli.commands.update_driver import update_driver_command

app = typer.Typer()

app.command(name="run")(run_command)
app.command(name="run-beats")(run_beats_command)
app.command(name="update-driver")(update_driver_command)
app.command(name="bench-device")(bench_device_command)
app.command(name="check-health")(check_health_command)
app.add_typer(flowtoy_app, name="flowtoy")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
