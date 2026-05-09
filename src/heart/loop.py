import os
import sys

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import typer


def _build_flowtoy_only_app() -> typer.Typer:
    app = typer.Typer()

    from heart.cli.commands.flowtoy import app as flowtoy_app

    app.add_typer(flowtoy_app, name="flowtoy")
    return app


def _build_full_app() -> typer.Typer:
    app = typer.Typer()

    from heart.cli.commands.bench_device import bench_device_command
    from heart.cli.commands.flowtoy import app as flowtoy_app
    from heart.cli.commands.rubiks_connected_x import app as rubiks_connected_x_app
    from heart.cli.commands.run import run_command
    from heart.cli.commands.update_driver import update_driver_command

    app.command(name="run")(run_command)
    app.command(name="update-driver")(update_driver_command)
    app.command(name="bench-device")(bench_device_command)
    app.add_typer(flowtoy_app, name="flowtoy")
    app.add_typer(rubiks_connected_x_app, name="rubiks-connected-x")
    return app


def _build_rubiks_connected_x_only_app() -> typer.Typer:
    app = typer.Typer()

    from heart.cli.commands.rubiks_connected_x import app as rubiks_connected_x_app

    app.add_typer(rubiks_connected_x_app, name="rubiks-connected-x")
    return app


app = _build_full_app()


def _run_isolated_app(app: typer.Typer) -> None:
    sys.argv = [sys.argv[0], *sys.argv[2:]]
    app()


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "flowtoy":
        _run_isolated_app(_build_flowtoy_only_app())
        return

    if len(sys.argv) > 1 and sys.argv[1] == "rubiks-connected-x":
        _run_isolated_app(_build_rubiks_connected_x_only_app())
        return

    if len(sys.argv) > 1 and sys.argv[1] == "update-driver":
        command_app = typer.Typer()
        from heart.cli.commands.update_driver import update_driver_command

        command_app.command()(update_driver_command)
        _run_isolated_app(command_app)
        return

    if len(sys.argv) > 1 and sys.argv[1] == "bench-device":
        command_app = typer.Typer()
        from heart.cli.commands.bench_device import bench_device_command

        command_app.command()(bench_device_command)
        _run_isolated_app(command_app)
        return

    app()


if __name__ == "__main__":
    main()
