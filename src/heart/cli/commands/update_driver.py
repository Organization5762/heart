from typing import Annotated

import typer
from heart_device_manager.driver_update.modes import UpdateMode
from heart_device_manager.update import UpdateError
from heart_device_manager.update import main as update_driver_main

from heart.utilities.logging import get_logger

logger = get_logger(__name__)


def update_driver_command(
    name: Annotated[str, typer.Option("--name")],
    mode: Annotated[UpdateMode, typer.Option("--mode")] = UpdateMode.AUTO,
) -> None:
    try:
        update_driver_main(device_driver_name=name, mode=mode)
    except UpdateError as error:
        logger.exception("Driver update failed")
        raise typer.Exit(code=1) from error
