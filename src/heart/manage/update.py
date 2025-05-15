import os
import subprocess
import sys
import time
from pathlib import Path

import toml

import heart
import heart.firmware_io
from heart import firmware_io

MEDIA_DIRECTORY = "/media/michael"
CIRCUIT_PY_COMMON_LIBS_UNZIPPED_NAME = "adafruit-circuitpython-bundle-9.x-mpy-20250412"
CIRCUIT_PY_COMMON_LIBS = f"https://github.com/adafruit/Adafruit_CircuitPython_Bundle/releases/download/20250412/{CIRCUIT_PY_COMMON_LIBS_UNZIPPED_NAME}.zip"
CIRCUIT_PY_COMMON_LIBS_CHECKSUM = (
    "6d49c73c352da31d5292508ff9b3eca2803372c1d2acca7175b64be2ff2bc450"
)


def load_driver_libs(libs: list[str], destination: str) -> None:
    os.makedirs(destination, exist_ok=True)
    subprocess.run(["rm", "-rf", destination], check=True)
    # Our local lib
    copy_file(
        os.path.dirname(firmware_io.__file__),
        os.path.join(destination, *firmware_io.__package__.split(".")),
    )

    if not libs:
        print("Skipping loading driver libs as no libs were requested.")
        return

    print(f"Loading the following libs: {libs}")
    zip_location = download_file(
        CIRCUIT_PY_COMMON_LIBS, CIRCUIT_PY_COMMON_LIBS_CHECKSUM
    )
    unzipped_location = zip_location.replace(".zip", "")
    # Lib in this case just comes from the downloaded file, which is separate from the `destination` which is also lib
    lib_path = os.path.join(unzipped_location, "lib")

    if not os.path.exists(lib_path):
        subprocess.run(
            ["unzip", zip_location], check=True, cwd=os.path.dirname(unzipped_location)
        )
    else:
        print(f"Skipping unzipping {zip_location} because {lib_path} exists")

    for lib in libs:
        copy_file(os.path.join(lib_path, lib), os.path.join(destination, lib))


def download_file(url: str, checksum: str) -> str:
    try:
        destination = os.path.join("/tmp", url.split("/")[-1])
        if not os.path.exists(destination):
            print(f"Starting download: {url}")
            subprocess.run(["wget", url, "-O", destination], check=True)
            print(f"Finished download: {destination}")

        # Check the checksum
        checksum_result = subprocess.run(
            ["sha256sum", destination], capture_output=True, text=True, check=True
        )
        file_checksum = checksum_result.stdout.split()[0]
        print(f"Checksum for {destination}: {file_checksum}")

        if file_checksum != checksum:
            print(
                f"Error: Checksum mismatch for {destination}. Expected {checksum}, but got {file_checksum}. The downloaded file may be corrupted or tampered with."
            )
            sys.exit(1)
        print("Checksum matches expectations.")
        return destination
    except subprocess.CalledProcessError:
        print(f"Error: Failed to download {url}")
        sys.exit(1)


def copy_file(source: str, destination: str) -> None:
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    try:
        print(f"Before copying: {source} to {destination}")
        if os.path.isdir(source):
            subprocess.run(["cp", "-rf", source, destination], check=True)
        else:
            subprocess.run(["cp", "-f", source, destination], check=True)
        print(f"After copying: {source} to {destination}")
    except subprocess.CalledProcessError:
        print(f"Error: Failed to copy {source} to {destination}")
        sys.exit(1)


def main(device_driver_name: str) -> None:
    base_path = str(Path(heart.__file__).resolve().parents[2] / "drivers")
    code_path = os.path.join(base_path, device_driver_name)
    if not os.path.isdir(code_path):
        print(
            f"Error: The path {code_path} does not exist. This is where we expect the driver code to exist."
        )
        sys.exit(1)

    ###
    # Load a bunch of env vars the driver declares
    ###
    d = toml.load(os.path.join(code_path, "settings.toml"))

    URL: str = d["CIRCUIT_PY_UF2_URL"]
    CHECKSUM: str = d["CIRCUIT_PY_UF2_CHECKSUM"]
    DRIVER_LIBS: list[str] = [
        lib for lib in d["CIRCUIT_PY_DRIVER_LIBS"].split(",") if lib
    ]
    # TODO: This doesn't support if you have multiple of the
    # same type of device you're trying to flash at the same time
    DEVICE_BOOT_NAME: str = d["CIRCUIT_PY_BOOT_NAME"]
    VALID_BOARD_IDS: list[str] = [
        board_id for board_id in d["VALID_BOARD_IDS"].split(",") if board_id
    ]

    ###
    # If the device is not a CIRCUIT_PY device yet, load the UF2 so that it is converted
    ###
    UF2_DESTINATION = os.path.join(MEDIA_DIRECTORY, DEVICE_BOOT_NAME)
    if os.path.isdir(UF2_DESTINATION):
        downloaded_file_path = download_file(URL, CHECKSUM)
        copy_file(downloaded_file_path, UF2_DESTINATION)
        time.sleep(10)
    else:
        print(
            "Skipping CircuitPython UF2 installation as no device is in boot mode currently"
        )

    ###
    # For all the CIRCUITPY devices, try to find whether this specific driver should be loaded onto them
    ###
    for mount_point in os.listdir(MEDIA_DIRECTORY):
        if "CIRCUITPY" in mount_point:
            media_location = os.path.join(MEDIA_DIRECTORY, mount_point)
            boot_out_path = os.path.join(media_location, "boot_out.txt")

            if os.path.exists(boot_out_path):
                with open(boot_out_path, "r") as file:
                    content = file.read()
                    board_id_line = next(
                        (line for line in content.splitlines() if "Board ID:" in line),
                        None,
                    )

                if board_id_line:
                    board_id = board_id_line.split("Board ID:")[1].strip()
                else:
                    raise ValueError(
                        f"Unable to find Board ID identifier in {boot_out_path}"
                    )

                if board_id not in VALID_BOARD_IDS:
                    print(
                        f"Skipping: The board ID {board_id} is not in the list of valid board IDs: {VALID_BOARD_IDS}"
                    )
                    continue

                for file_name in ["boot.py", "code.py", "settings.toml"]:
                    copy_file(
                        os.path.join(code_path, file_name),
                        os.path.join(media_location, file_name),
                    )

                load_driver_libs(
                    libs=DRIVER_LIBS,
                    destination=os.path.join(os.path.join(media_location, "lib")),
                )
            else:
                print(f"{boot_out_path} is missing, skipping...")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Error: DEVICE_DRIVER_NAME is not set. Please supply it as the first argument."
        )
        sys.exit(1)

    if not sys.argv[1]:
        print(
            "Error: DEVICE_DRIVER_NAME is not set. Please supply it as the first argument."
        )
        sys.exit(1)
    main(sys.argv[1])
