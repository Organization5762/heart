from typing import Annotated

import typer

from heart.manage.update import UpdateError
from heart.manage.update import main as update_driver_main
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


def update_driver_command(name: Annotated[str, typer.Option("--name")]) -> None:
    try:
        update_driver_main(device_driver_name=name)
    except UpdateError as error:
        logger.error("Driver update failed: %s", error)
        raise typer.Exit(code=1) from error
