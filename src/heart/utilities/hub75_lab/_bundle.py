"""Authoritative deployment logic for the Heart-owned RP1 HUB75 Linux bundle."""

from __future__ import annotations

import argparse
import filecmp
import json
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, final

REPO_ROOT = Path(__file__).resolve().parents[4]
BUNDLE_ROOT = REPO_ROOT / "rp1" / "linux"
MANIFEST_PATH = BUNDLE_ROOT / "manifest.json"
DEFAULT_REMOTE_DIR = "/home/michael/rp1-pio"
DEFAULT_REMOTE_MODULE_DIR = "/tmp/rp1-hub75-module"
REMOTE_HELPER_SOURCES = (
    "rp1_core1_launch_mem.c",
    "rp1_mmio_poke32.c",
    "rp1_mmio_read32.c",
    "rp1_sram_counter.c",
    "rp1_sram_dump.c",
    "rp1_sram_poke32.c",
    "rp1_sram_read32.c",
)


@final
@dataclass(frozen=True)
class Bundle:
    files_dir: Path
    files: tuple[Path, ...]
    boot_preflight: dict[str, Any]


def load_bundle() -> Bundle:
    manifest = json.loads(MANIFEST_PATH.read_text())
    files_dir = BUNDLE_ROOT / manifest["linux_root_files_dir"]
    files = tuple(Path(path) for path in manifest["files"])
    return Bundle(
        files_dir=files_dir,
        files=files,
        boot_preflight=manifest["boot_preflight"],
    )


def ensure_bundle_files_exist(bundle: Bundle) -> None:
    missing = [path for path in bundle.files if not (bundle.files_dir / path).is_file()]
    if missing:
        formatted = "\n".join(f"  {path}" for path in missing)
        raise SystemExit(f"manifest references missing bundle files:\n{formatted}")


def command_list(args: argparse.Namespace) -> int:
    bundle = load_bundle()
    ensure_bundle_files_exist(bundle)
    for path in bundle.files:
        print(path)
    return 0


def command_apply(args: argparse.Namespace) -> int:
    bundle = load_bundle()
    ensure_bundle_files_exist(bundle)
    linux_root = args.linux.resolve()
    copied = 0

    for rel_path in bundle.files:
        source = bundle.files_dir / rel_path
        target = linux_root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if args.dry_run:
            action = "update" if target.exists() else "create"
            print(f"{action} {target}")
            continue
        shutil.copy2(source, target)
        copied += 1

    if not args.dry_run:
        print(f"applied {copied} files to {linux_root}")
    return 0


def command_diff(args: argparse.Namespace) -> int:
    bundle = load_bundle()
    ensure_bundle_files_exist(bundle)
    linux_root = args.linux.resolve()
    different: list[Path] = []
    missing: list[Path] = []

    for rel_path in bundle.files:
        source = bundle.files_dir / rel_path
        target = linux_root / rel_path
        if not target.exists():
            missing.append(rel_path)
        elif not filecmp.cmp(source, target, shallow=False):
            different.append(rel_path)

    for rel_path in missing:
        print(f"missing {rel_path}")
    for rel_path in different:
        print(f"different {rel_path}")
    if missing or different:
        return 1
    print("bundle matches linux checkout")
    return 0


def command_deploy_target(args: argparse.Namespace) -> int:
    bundle = load_bundle()
    ensure_bundle_files_exist(bundle)
    host = normalize_host(args.host)
    remote_dir = args.remote_dir
    remote_module_dir = args.remote_module_dir

    if args.local_bootstrap_dir:
        remote_bundle_root = f"{args.local_bootstrap_dir.rstrip('/')}/rp1/linux/files"
        remote_script = (
            f"set -eu\n"
            f"rm -rf {shell_quote(remote_dir)}\n"
            f"mkdir -p {shell_quote(remote_dir)}\n"
            f"cp -R {shell_quote(remote_bundle_root)}/tools/testing/selftests/drivers/rp1-pio/. "
            f"{shell_quote(remote_dir)}/\n"
        )
        remote_run(host, remote_script)
    else:
        remote_run(
            host,
            f"rm -rf {shell_quote(remote_dir)} && mkdir -p {shell_quote(remote_dir)}",
        )
        rsync_bundle_selftests(host, remote_dir)

    remote_run(host, build_remote_helper_script(remote_dir))
    deploy_remote_module(host, remote_dir, remote_module_dir)
    return command_preflight(argparse.Namespace(host=args.host, remote_dir=remote_dir))


def normalize_host(host: str) -> str:
    return host if "@" in host else f"michael@{host}"


def remote_run(host: str, script: str) -> None:
    subprocess.run(
        ["ssh", host, "sh", "-lc", script],
        check=True,
    )


def rsync_bundle_selftests(host: str, remote_dir: str) -> None:
    source = (
        BUNDLE_ROOT
        / "files"
        / "tools"
        / "testing"
        / "selftests"
        / "drivers"
        / "rp1-pio"
    )
    subprocess.run(
        ["rsync", "-az", f"{source}/", f"{host}:{remote_dir}/"],
        check=True,
    )


def build_remote_helper_script(remote_dir: str) -> str:
    helper_build_lines = "\n".join(
        f"cc -O2 -Wall -Wextra {shell_quote(source)} -o {shell_quote(source[:-2])}"
        for source in REMOTE_HELPER_SOURCES
    )
    return f"""
set -eu
cd {shell_quote(remote_dir)}

{helper_build_lines}
chmod +x rp1_core1_build_payloads.sh rp1_hub75_run_candidate.sh
./rp1_core1_build_payloads.sh --all
"""


def deploy_remote_module(host: str, remote_dir: str, remote_module_dir: str) -> None:
    script = f"""
set -eu
rm -rf {shell_quote(remote_module_dir)}
mkdir -p {shell_quote(remote_module_dir)}/include/uapi/misc
cp {shell_quote(remote_dir)}/rp1_hub75_module/Makefile {shell_quote(remote_module_dir)}/Makefile
"""
    remote_run(host, script)

    # The selftest directory only contains helper/module Makefile content. Copy
    # the canonical driver sources from the bundle so standalone deploys do not
    # depend on Linux source-tree relative paths existing on the target.
    driver_source = BUNDLE_ROOT / "files" / "drivers" / "misc" / "rp1-hub75.c"
    header_source = (
        BUNDLE_ROOT / "files" / "include" / "uapi" / "misc" / "rp1_hub75_if.h"
    )
    subprocess.run(
        ["scp", str(driver_source), f"{host}:{remote_module_dir}/rp1-hub75.c"],
        check=True,
    )
    subprocess.run(
        [
            "scp",
            str(header_source),
            f"{host}:{remote_module_dir}/include/uapi/misc/rp1_hub75_if.h",
        ],
        check=True,
    )
    remote_run(host, build_remote_module_script(remote_module_dir))


def build_remote_module_script(remote_module_dir: str) -> str:
    return f"""
set -eu
cd {shell_quote(remote_module_dir)}
test -d /lib/modules/$(uname -r)/build
make
sudo mkdir -p /lib/modules/$(uname -r)/extra
sudo install -m 0644 rp1-hub75.ko /lib/modules/$(uname -r)/extra/rp1-hub75.ko
printf 'rp1-hub75\\n' | sudo tee /etc/modules-load.d/rp1-hub75.conf >/dev/null
sudo depmod -a
if grep -q '^rp1_hub75 ' /proc/modules; then
  sudo modprobe -r rp1-hub75
fi
sudo modprobe rp1-hub75
ls -l /dev/rp1-hub75
"""


def remote_read32(host: str, remote_dir: str, offset: str) -> str:
    normalized_host = normalize_host(host)
    command = (
        f"cd {shell_quote(remote_dir)} && sudo ./rp1_sram_read32 {shell_quote(offset)}"
    )
    result = subprocess.run(
        ["ssh", normalized_host, command],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip().splitlines()[-1]


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def command_preflight(args: argparse.Namespace) -> int:
    bundle = load_bundle()
    checks = bundle.boot_preflight
    rows: list[tuple[str, str, str, str]] = []

    dev_status = remote_test(args.host, "[ -e /dev/rp1-hub75 ]")
    helper_status = remote_test(
        args.host,
        f"[ -x {shell_quote(args.remote_dir)}/rp1_sram_read32 ]",
    )
    rows.append(
        (
            "/dev/rp1-hub75",
            "present",
            "present" if dev_status else "missing",
            verdict(dev_status),
        )
    )
    rows.append(
        (
            "rp1_sram_read32",
            "executable",
            "executable" if helper_status else "missing",
            verdict(helper_status),
        )
    )

    if not helper_status:
        print_table(rows)
        return 1

    feature = checks["firmware_feature_table"]
    observed_feature = [
        remote_read32(
            args.host, args.remote_dir, hex(int(feature["address"], 16) + i * 4)
        )
        for i in range(4)
    ]
    expected_feature = [word.lower() for word in feature["known_launchable_words"]]
    feature_ok = [word.lower() for word in observed_feature] == expected_feature
    rows.append(
        (
            "firmware table 0x5928",
            ", ".join(expected_feature),
            ", ".join(observed_feature),
            verdict(feature_ok),
        )
    )

    for key, label in (
        ("legacy_hook_5fc", "hook 0x5fc"),
        ("vector_hook_12c", "hook 0x12c"),
    ):
        check = checks[key]
        observed = remote_read32(args.host, args.remote_dir, check["address"])
        expected = check["known_launchable_word"].lower()
        rows.append((label, expected, observed, verdict(observed.lower() == expected)))

    print_table(rows)
    return 0 if all(row[3] == "pass" for row in rows) else 1


def remote_test(host: str, expression: str) -> bool:
    normalized_host = normalize_host(host)
    result = subprocess.run(
        ["ssh", normalized_host, expression],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def verdict(ok: bool) -> str:
    return "pass" if ok else "fail"


def print_table(rows: list[tuple[str, str, str, str]]) -> None:
    print("| Check | Expected | Observed | Verdict |")
    print("|---|---|---|---|")
    for check, expected, observed, row_verdict in rows:
        print(f"| {check} | `{expected}` | `{observed}` | {row_verdict} |")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(required=True)

    list_parser = subparsers.add_parser("list", help="list bundled Linux files")
    list_parser.set_defaults(func=command_list)

    apply_parser = subparsers.add_parser(
        "apply", help="copy bundle files into a Linux checkout"
    )
    apply_parser.add_argument("--linux", type=Path, required=True)
    apply_parser.add_argument("--dry-run", action="store_true")
    apply_parser.set_defaults(func=command_apply)

    diff_parser = subparsers.add_parser(
        "diff", help="check whether a Linux checkout matches the bundle"
    )
    diff_parser.add_argument("--linux", type=Path, required=True)
    diff_parser.set_defaults(func=command_diff)

    deploy_parser = subparsers.add_parser(
        "deploy-target", help="deploy and build the bundle on a totem"
    )
    deploy_parser.add_argument("--host", required=True)
    deploy_parser.add_argument("--remote-dir", default=DEFAULT_REMOTE_DIR)
    deploy_parser.add_argument("--remote-module-dir", default=DEFAULT_REMOTE_MODULE_DIR)
    deploy_parser.add_argument(
        "--local-bootstrap-dir",
        help="remote directory that already contains rp1/linux/files from this checkout",
    )
    deploy_parser.set_defaults(func=command_deploy_target)

    preflight_parser = subparsers.add_parser(
        "preflight", help="classify RP1 boot state on a totem"
    )
    preflight_parser.add_argument("--host", required=True)
    preflight_parser.add_argument("--remote-dir", default="/home/michael/rp1-pio")
    preflight_parser.set_defaults(func=command_preflight)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = args.func(args)
    if not isinstance(result, int):
        raise TypeError(f"bundle command returned non-integer status: {result!r}")
    return result


if __name__ == "__main__":
    sys.exit(main())
