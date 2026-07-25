#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import multiprocessing
import os
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any

from manyfold.architecture import ProcessCredentialState, ProcessCredentialStatus

from heart.runtime.manyfold_signer import ManyfoldSignerConfig, ManyfoldSignerRuntime

_CLUSTER_ID = "heart-qualification"
_AUTHORITY_ID = "qualification-authority"
_MACHINE_ID = "qualification-machine"
_SIGNER_LIFETIME_SECONDS = 6
_PROCESS_RESPONSE_TIMEOUT_SECONDS = 10.0
_STATE_POLL_TIMEOUT_SECONDS = 2.0


def run_qualification(
    signer_executable: Path,
    enrollment_executable: Path,
) -> dict[str, Any]:
    """Exercise bootstrap, rejection, outage, restart, renewal, and expiry."""
    commands: list[list[str]] = []
    # macOS limits AF_UNIX paths to 104 bytes; keep the real socket paths short.
    with tempfile.TemporaryDirectory(prefix="hmsq-") as root:
        root_path = Path(root)
        authority_state_directory = root_path / "a"
        authority_socket_path = root_path / "ar" / "s"
        state_directory = root_path / "m"
        socket_path = root_path / "r" / "s"
        token_file = root_path / "t"
        durable_key_paths: tuple[Path, ...]
        initialize_command = [
            str(enrollment_executable),
            "initialize",
            "--state-dir",
            str(authority_state_directory),
            "--cluster-id",
            _CLUSTER_ID,
            "--node-id",
            _AUTHORITY_ID,
            "--server-name",
            "localhost",
        ]
        commands.append(initialize_command)
        initialization = subprocess.run(
            initialize_command,
            check=True,
            capture_output=True,
            text=True,
        )
        enrollment_token = json.loads(initialization.stdout)["enrollment_token"]
        token_file.write_text(f"{enrollment_token}\n", encoding="ascii")
        token_file.chmod(0o600)

        authority_signer_command = _signer_command(
            signer_executable,
            state_directory=authority_state_directory,
            socket_path=authority_socket_path,
            allowed_uid=os.getuid(),
        )
        commands.append(authority_signer_command)
        authority_signer = _start_signer(
            authority_signer_command,
            authority_socket_path,
        )
        enroll_command = [
            str(enrollment_executable),
            "enroll",
            "--authority-socket",
            str(authority_socket_path),
            "--state-dir",
            str(state_directory),
            "--node-id",
            _MACHINE_ID,
            "--server-name",
            "localhost",
            "--token-file",
            str(token_file),
        ]
        commands.append(enroll_command)
        try:
            subprocess.run(
                enroll_command,
                check=True,
                capture_output=True,
                text=True,
            )
            token_file.unlink()
        finally:
            _stop_signer(authority_signer)

        durable_key_paths = (
            *authority_state_directory.rglob("*.key"),
            *state_directory.rglob("*.key"),
        )
        if not durable_key_paths:
            raise RuntimeError("enrollment created no durable private-key files")

        signer_command = _signer_command(
            signer_executable,
            state_directory=state_directory,
            socket_path=socket_path,
            allowed_uid=os.getuid(),
        )
        commands.append(signer_command)
        signer = _start_signer(signer_command, socket_path)
        ipc_permissions = {
            "state_directory_mode": _mode(state_directory),
            "socket_parent_mode": _mode(socket_path.parent),
            "socket_mode": _mode(socket_path),
        }
        try:
            bootstrap = _run_two_bootstrap_clients(
                socket_path,
                durable_key_paths,
            )
            restart_renewal = _run_restart_renewal(
                signer=signer,
                signer_command=signer_command,
                socket_path=socket_path,
                durable_key_paths=durable_key_paths,
            )
            signer = restart_renewal.pop("_signer")
        finally:
            _stop_signer(signer)

        unauthorized_command = _signer_command(
            signer_executable,
            state_directory=state_directory,
            socket_path=socket_path,
            allowed_uid=os.getuid() + 1,
        )
        commands.append(unauthorized_command)
        unauthorized_signer = _start_signer(
            unauthorized_command,
            socket_path,
        )
        try:
            unauthorized = _run_one_shot_client(
                socket_path,
                durable_key_paths,
            )
        finally:
            _stop_signer(unauthorized_signer)

        unavailable = _run_one_shot_client(
            socket_path,
            durable_key_paths,
        )

        artifact = {
            "protocol": "heart.manyfold-signer-qualification",
            "version": 1,
            "commands": commands,
            "durable_private_key_files": [
                (
                    f"authority/{path.relative_to(authority_state_directory)}"
                    if path.is_relative_to(authority_state_directory)
                    else f"machine/{path.relative_to(state_directory)}"
                )
                for path in durable_key_paths
            ],
            "enrollment_token_file_removed": not token_file.exists(),
            "ipc_permissions": ipc_permissions,
            "bootstrap": bootstrap,
            "restart_renewal": restart_renewal,
            "unauthorized": unauthorized,
            "unavailable_bootstrap": unavailable,
        }
        _validate_artifact(artifact)
        return artifact


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--signer-executable",
        type=Path,
        default=_default_signer_executable(),
    )
    parser.add_argument(
        "--enrollment-executable",
        type=Path,
        default=_default_enrollment_executable(),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("manyfold-signer-qualification.json"),
    )
    arguments = parser.parse_args()
    artifact = run_qualification(
        arguments.signer_executable,
        arguments.enrollment_executable,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    with arguments.output.open("w", encoding="utf-8") as output:
        json.dump(artifact, output, indent=2, sort_keys=True)
        output.write("\n")
    print(f"wrote qualification artifact: {arguments.output}")


def _run_two_bootstrap_clients(
    socket_path: Path,
    durable_key_paths: tuple[Path, ...],
) -> dict[str, Any]:
    context = multiprocessing.get_context("spawn")
    processes: list[multiprocessing.Process] = []
    receivers: list[Connection] = []
    for index in range(2):
        receiver, sender = context.Pipe(duplex=False)
        process = context.Process(
            target=_one_shot_worker,
            args=(
                sender,
                _client_config(socket_path),
                durable_key_paths,
            ),
        )
        process.start()
        sender.close()
        processes.append(process)
        receivers.append(receiver)
    results = [
        _receive(receiver, "bootstrap client")
        for receiver in receivers
    ]
    for receiver in receivers:
        receiver.close()
    for process in processes:
        process.join(timeout=10.0)
        if process.exitcode != 0:
            raise RuntimeError(f"bootstrap client exited with code {process.exitcode}")
    return {
        "client_processes": len(results),
        "states": [result["state"] for result in results],
        "serial_numbers": [result["serial_number"] for result in results],
        "durable_private_key_opened_by_clients": any(
            result["durable_private_key_opened"] for result in results
        ),
        "durable_private_key_open_matches": sorted(
            {
                path
                for result in results
                for path in result["durable_private_key_open_matches"]
            }
        ),
    }


def _run_restart_renewal(
    *,
    signer: subprocess.Popen[str],
    signer_command: list[str],
    socket_path: Path,
    durable_key_paths: tuple[Path, ...],
) -> dict[str, Any]:
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=True)
    process = context.Process(
        target=_persistent_worker,
        args=(
            sender,
            _client_config(socket_path),
            durable_key_paths,
        ),
    )
    process.start()
    sender.close()
    initial = _receive(receiver, "restart client bootstrap")

    _stop_signer(signer)
    _wait_until_expiry_window(initial, seconds_before_expiry=1.5)
    during_outage = _poll_until_state(
        receiver,
        ProcessCredentialState.RENEWAL_FAILED,
    )

    restarted_signer = _start_signer(signer_command, socket_path)
    after_restart = _poll_until_state(
        receiver,
        ProcessCredentialState.READY,
    )

    _stop_signer(restarted_signer)
    _wait_until_expiry_window(after_restart, seconds_before_expiry=-0.1)
    after_expiry = _poll_until_state(
        receiver,
        ProcessCredentialState.EXPIRED,
    )
    receiver.send("close")
    closed = _receive(receiver, "restart client shutdown")
    receiver.close()
    process.join(timeout=10.0)
    if process.exitcode != 0:
        raise RuntimeError(f"restart client exited with code {process.exitcode}")
    return {
        "initial": initial,
        "during_outage": during_outage,
        "after_restart": after_restart,
        "after_expiry": after_expiry,
        "closed": closed,
        "_signer": restarted_signer,
    }


def _poll_until_state(
    connection: Connection,
    expected_state: ProcessCredentialState,
) -> dict[str, Any]:
    deadline = time.monotonic() + _STATE_POLL_TIMEOUT_SECONDS
    while True:
        connection.send("poll")
        remaining_seconds = deadline - time.monotonic()
        if remaining_seconds <= 0:
            raise TimeoutError(
                f"client did not reach {expected_state.value} before timeout"
            )
        status = _receive(
            connection,
            f"client state {expected_state.value}",
            timeout_seconds=remaining_seconds,
        )
        if status["state"] == expected_state.value:
            return status
        time.sleep(0.05)


def _receive(
    connection: Connection,
    operation: str,
    *,
    timeout_seconds: float = _PROCESS_RESPONSE_TIMEOUT_SECONDS,
) -> Any:
    if not connection.poll(timeout_seconds):
        raise TimeoutError(f"{operation} did not respond before timeout")
    return connection.recv()


def _wait_until_expiry_window(
    status: dict[str, Any],
    *,
    seconds_before_expiry: float,
) -> None:
    expires_at = status["expires_at"]
    if not isinstance(expires_at, str):
        raise RuntimeError(f"credential has no expiry timestamp: {status}")
    expiry = dt.datetime.fromisoformat(expires_at).timestamp()
    delay = expiry - time.time() - seconds_before_expiry
    if delay > 0:
        time.sleep(delay)


def _run_one_shot_client(
    socket_path: Path,
    durable_key_paths: tuple[Path, ...],
) -> dict[str, Any]:
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(
        target=_one_shot_worker,
        args=(
            sender,
            _client_config(socket_path),
            durable_key_paths,
        ),
    )
    process.start()
    sender.close()
    result = _receive(receiver, "one-shot client")
    receiver.close()
    process.join(timeout=10.0)
    if process.exitcode != 0:
        raise RuntimeError(f"client exited with code {process.exitcode}")
    return result


def _one_shot_worker(
    sender: Connection,
    config: ManyfoldSignerConfig,
    durable_key_paths: tuple[Path, ...],
) -> None:
    opened_paths: set[str] = set()
    normalized_durable_key_paths = {str(path.resolve()) for path in durable_key_paths}

    def audit_hook(event: str, arguments: tuple[object, ...]) -> None:
        if event != "open" or not arguments:
            return
        try:
            opened_paths.add(str(Path(os.fspath(arguments[0])).resolve()))
        except TypeError:
            return

    sys.addaudithook(audit_hook)
    runtime = ManyfoldSignerRuntime(config)
    try:
        status = runtime.start()
        result = _status_row(status)
    except Exception as error:
        credential_status = runtime.status()
        result = {
            "state": "rejected",
            "credential_state": (
                None if credential_status is None else credential_status.state.value
            ),
            "error_type": type(error).__name__,
        }
    finally:
        runtime.close()
    open_matches = sorted(normalized_durable_key_paths & opened_paths)
    result["durable_private_key_opened"] = bool(open_matches)
    result["durable_private_key_open_matches"] = open_matches
    sender.send(result)
    sender.close()


def _persistent_worker(
    connection: Connection,
    config: ManyfoldSignerConfig,
    durable_key_paths: tuple[Path, ...],
) -> None:
    opened_paths: set[str] = set()
    normalized_durable_key_paths = {str(path.resolve()) for path in durable_key_paths}

    def audit_hook(event: str, arguments: tuple[object, ...]) -> None:
        if event != "open" or not arguments:
            return
        try:
            opened_paths.add(str(Path(os.fspath(arguments[0])).resolve()))
        except TypeError:
            return

    sys.addaudithook(audit_hook)
    runtime = ManyfoldSignerRuntime(config)
    connection.send(_status_row(runtime.start()))
    while True:
        command = connection.recv()
        if command == "poll":
            connection.send(_status_row(runtime.poll()))
            continue
        if command == "close":
            runtime.close()
            open_matches = sorted(normalized_durable_key_paths & opened_paths)
            connection.send(
                {
                    "state": ProcessCredentialState.CLOSED.value,
                    "durable_private_key_opened": bool(open_matches),
                    "durable_private_key_open_matches": open_matches,
                }
            )
            break
        raise RuntimeError(f"unknown qualification command: {command}")
    connection.close()


def _client_config(
    socket_path: Path,
) -> ManyfoldSignerConfig:
    return ManyfoldSignerConfig(
        enabled=True,
        socket_path=socket_path,
        cluster_id=_CLUSTER_ID,
        node_id=_MACHINE_ID,
        poll_interval_seconds=60.0,
        retry_max_attempts=1,
        retry_delay_seconds=0.05,
    )


def _status_row(
    status: ProcessCredentialStatus | None,
) -> dict[str, Any]:
    if status is None:
        raise RuntimeError("qualification signer runtime is disabled")
    return {
        "state": status.state.value,
        "generation": status.generation,
        "serial_number": status.serial_number,
        "is_usable": status.is_usable,
        "expires_at": (
            None if status.expires_at is None else status.expires_at.isoformat()
        ),
    }


def _mode(path: Path) -> str:
    return f"{stat.S_IMODE(path.stat().st_mode):04o}"


def _signer_command(
    signer_executable: Path,
    *,
    state_directory: Path,
    socket_path: Path,
    allowed_uid: int,
) -> list[str]:
    return [
        str(signer_executable),
        "start",
        "--state-dir",
        str(state_directory),
        "--socket",
        str(socket_path),
        "--allowed-uid",
        str(allowed_uid),
        "--credential-ttl-seconds",
        str(_SIGNER_LIFETIME_SECONDS),
    ]


def _start_signer(
    command: list[str],
    socket_path: Path,
) -> subprocess.Popen[str]:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 5.0
    while not _socket_accepts_connections(socket_path):
        return_code = process.poll()
        if return_code is not None:
            stdout, stderr = process.communicate()
            raise RuntimeError(
                "signer exited before readiness "
                f"code={return_code} stdout={stdout!r} stderr={stderr!r}"
            )
        if time.monotonic() >= deadline:
            _stop_signer(process)
            raise TimeoutError("signer socket did not become ready")
        time.sleep(0.01)
    return process


def _socket_accepts_connections(socket_path: Path) -> bool:
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        connection.settimeout(0.1)
        connection.connect(str(socket_path))
    except OSError:
        return False
    finally:
        connection.close()
    return True


def _stop_signer(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        process.communicate()
        return
    process.terminate()
    try:
        process.communicate(timeout=5.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate(timeout=5.0)


def _validate_artifact(artifact: dict[str, Any]) -> None:
    if not artifact["enrollment_token_file_removed"]:
        raise RuntimeError("one-time enrollment token file was retained")
    if any(
        argument == "--token"
        for command in artifact["commands"]
        for argument in command
    ):
        raise RuntimeError("enrollment bearer token was placed in argv")

    expected_modes = {
        "state_directory_mode": "0700",
        "socket_parent_mode": "0700",
        "socket_mode": "0600",
    }
    if artifact["ipc_permissions"] != expected_modes:
        raise RuntimeError(
            f"signer IPC permissions are not owner-only: {artifact['ipc_permissions']}"
        )

    bootstrap = artifact["bootstrap"]
    if bootstrap["states"] != [ProcessCredentialState.READY.value] * 2:
        raise RuntimeError(f"bootstrap did not reach readiness: {bootstrap}")
    if len(set(bootstrap["serial_numbers"])) != 2:
        raise RuntimeError("bootstrap clients did not receive distinct credentials")
    if bootstrap["durable_private_key_opened_by_clients"]:
        raise RuntimeError("a Heart bootstrap process opened the durable machine key")
    if bootstrap["durable_private_key_open_matches"]:
        raise RuntimeError("bootstrap durable-key audit matches are not empty")

    restart = artifact["restart_renewal"]
    expected_states = {
        "initial": ProcessCredentialState.READY.value,
        "during_outage": ProcessCredentialState.RENEWAL_FAILED.value,
        "after_restart": ProcessCredentialState.READY.value,
        "after_expiry": ProcessCredentialState.EXPIRED.value,
        "closed": ProcessCredentialState.CLOSED.value,
    }
    for phase, expected_state in expected_states.items():
        if restart[phase]["state"] != expected_state:
            raise RuntimeError(
                f"restart phase {phase} did not reach {expected_state}: "
                f"{restart[phase]}"
            )
    if restart["initial"]["serial_number"] == restart["after_restart"]["serial_number"]:
        raise RuntimeError("signer restart did not renew the process credential")
    if not restart["during_outage"]["is_usable"]:
        raise RuntimeError("signer outage discarded an unexpired credential")
    if restart["after_expiry"]["is_usable"]:
        raise RuntimeError("expired process credential remained usable")
    if restart["closed"]["durable_private_key_opened"]:
        raise RuntimeError("the restart Heart process opened the durable machine key")
    if restart["closed"]["durable_private_key_open_matches"]:
        raise RuntimeError("restart durable-key audit matches are not empty")

    for name in ("unauthorized", "unavailable_bootstrap"):
        result = artifact[name]
        if result["state"] != "rejected":
            raise RuntimeError(f"{name} unexpectedly acquired a credential: {result}")
        if result["credential_state"] != ProcessCredentialState.UNAVAILABLE.value:
            raise RuntimeError(
                f"{name} did not report unavailable lifecycle state: {result}"
            )
        if result["durable_private_key_opened"]:
            raise RuntimeError(f"{name} opened the durable machine key")
        if result["durable_private_key_open_matches"]:
            raise RuntimeError(f"{name} durable-key audit matches are not empty")


def _default_signer_executable() -> Path:
    executable = shutil.which("manyfold-machine-signer")
    if executable is None:
        return Path("manyfold-machine-signer")
    return Path(executable)


def _default_enrollment_executable() -> Path:
    executable = shutil.which("manyfold-enrollment")
    if executable is None:
        return Path("manyfold-enrollment")
    return Path(executable)


if __name__ == "__main__":
    main()
