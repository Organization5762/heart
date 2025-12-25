"""Download helpers for driver updates."""

import hashlib
import subprocess
from pathlib import Path

from heart.manage.driver_update.exceptions import UpdateError
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


def _sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(url: str, checksum: str, *, destination_dir: Path | None = None) -> Path:
    try:
        target_dir = destination_dir or Path("/tmp")
        target_dir.mkdir(parents=True, exist_ok=True)
        destination = target_dir / Path(url).name
        if destination.exists():
            existing_checksum = _sha256sum(destination)
            if existing_checksum != checksum:
                logger.warning(
                    "Removing %s; checksum %s did not match %s.",
                    destination,
                    existing_checksum,
                    checksum,
                )
                destination.unlink()

        if not destination.exists():
            logger.info("Starting download: %s", url)
            if Configuration.is_pi():
                subprocess.run(["wget", url, "-O", str(destination)], check=True)
            else:
                subprocess.run(
                    ["curl", "-fL", url, "-o", str(destination)], check=True
                )
            logger.info("Finished download: %s", destination)

        downloaded_checksum = _sha256sum(destination)
        logger.info("Checksum for %s: %s", destination, downloaded_checksum)
        if downloaded_checksum != checksum:
            message = (
                f"Checksum mismatch for {destination}. "
                f"Expected {checksum}, but got {downloaded_checksum}."
            )
            logger.error(message)
            raise UpdateError(message)
        logger.info("Checksum matches expectations.")
        return destination
    except subprocess.CalledProcessError:
        message = f"Failed to download {url}"
        logger.error(message)
        raise UpdateError(message) from None
