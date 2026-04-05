import os
import sys

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import typer

_app: typer.Typer | None = None


def _build_flowtoy_only_app() -> typer.Typer:
    app = typer.Typer()

    from heart.cli.commands.flowtoy import app as flowtoy_app

    app.add_typer(flowtoy_app, name="flowtoy")
    return app


def _build_full_app() -> typer.Typer:
    app = typer.Typer()

    from heart.cli.commands.bench_device import bench_device_command
    from heart.cli.commands.flowtoy import app as flowtoy_app
    from heart.cli.commands.rubiks_connected_x import \
        app as rubiks_connected_x_app
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

    from heart.cli.commands.rubiks_connected_x import \
        app as rubiks_connected_x_app

    app.add_typer(rubiks_connected_x_app, name="rubiks-connected-x")
    return app


def _get_app() -> typer.Typer:
    global _app
    if _app is None:
        _app = _build_full_app()
    return _app


def __getattr__(name: str) -> object:
    if name == "app":
        return _get_app()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "flowtoy":
        _build_flowtoy_only_app()()
        return

    if len(sys.argv) > 1 and sys.argv[1] == "rubiks-connected-x":
        _build_rubiks_connected_x_only_app()()
        return

    if len(sys.argv) > 1 and sys.argv[1] == "update-driver":
        app = typer.Typer()
        from heart.cli.commands.update_driver import update_driver_command

        app.command(name="update-driver")(update_driver_command)
        app()
        return

    if len(sys.argv) > 1 and sys.argv[1] == "bench-device":
        app = typer.Typer()
        from heart.cli.commands.bench_device import bench_device_command

        app.command(name="bench-device")(bench_device_command)
        app()
        return

    if len(sys.argv) > 1 and sys.argv[1] == "run":
        app = typer.Typer()
        from heart.cli.commands.run import run_command

        app.command(name="run")(run_command)
        app()
        return

    _get_app()()


if __name__ == "__main__":
    main()
