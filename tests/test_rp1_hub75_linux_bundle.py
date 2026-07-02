"""Tests for the RP1 HUB75 Linux bundle helper."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "rp1_hub75_linux_bundle.py"
)
SPEC = importlib.util.spec_from_file_location("rp1_hub75_linux_bundle", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
rp1_hub75_linux_bundle = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = rp1_hub75_linux_bundle
SPEC.loader.exec_module(rp1_hub75_linux_bundle)


def test_normalize_host_adds_default_totem_user() -> None:
    assert (
        rp1_hub75_linux_bundle.normalize_host("totem3.local") == "michael@totem3.local"
    )
    assert (
        rp1_hub75_linux_bundle.normalize_host("michael@totem3.local")
        == "michael@totem3.local"
    )


def test_remote_helper_build_script_only_compiles_required_c_helpers() -> None:
    script = rp1_hub75_linux_bundle.build_remote_helper_script("/home/michael/rp1-pio")

    assert "rp1_sram_read32.c" in script
    assert "rp1_core1_launch_mem.c" in script
    assert "for source in *.c" not in script
    assert "./rp1_core1_build_payloads.sh --all" in script


def test_module_deploy_script_persists_module_load_config() -> None:
    script = rp1_hub75_linux_bundle.build_remote_module_script("/tmp/rp1-hub75-module")

    assert "/etc/modules-load.d/rp1-hub75.conf" in script
    assert "sudo modprobe rp1-hub75" in script
