"""Regression coverage for the consolidated HUB75 laboratory."""

from __future__ import annotations

import csv
import importlib.util
import json
import re
import stat
import subprocess
from pathlib import Path

import pytest

from heart.utilities.hub75_lab._backends import (GpioBackend,
                                                 _select_gpio_backend)
from heart.utilities.hub75_lab.capture import (
    COMPLETE_SIMILARITY_COLOR_WEIGHT, COMPLETE_SIMILARITY_CONTROL_WEIGHT,
    COMPLETE_SIMILARITY_PASS_THRESHOLD, DEFAULT_CAPTURE_SIGNAL_MAP,
    CapturePreflight, CaptureReport, _analyze_capture_data,
    _analyze_capture_with_saleae_module, _saleae_support_available,
    build_probe_toggle_command, capture_report_payload, create_probe_proof,
    score_complete_similarity)
from heart.utilities.hub75_lab.cli import _parse_signal_map
from heart.utilities.hub75_lab.cli import main as hub75_lab_main
from heart.utilities.hub75_lab.experiments import (APPLIED_SETTING_NAMES,
                                                   ExperimentSettings,
                                                   build_experiment_command,
                                                   list_experiments)
from heart.utilities.hub75_lab.memory import validate_sram_buffer
from heart.utilities.hub75_logic_score import score_hub75_capture_files

REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_PATH = REPO_ROOT / "docs" / "hub75_script_inventory.json"
LEGACY_SCRIPT_PATTERN = (
    "rg --files scripts | rg -i '(hub75|rp1|pio|saleae|logic)' | sort"
)
REPLACED_PATHS = {
    "scripts/hub75_color_cycle.py",
    "scripts/hub75_gpio_smoke.py",
    "scripts/hub75_gradient_cycle.py",
    "scripts/hub75_score_capture.py",
    "scripts/hub75_single_line.py",
    "scripts/hub75_virtual_image_from_logic.py",
}
INTENTIONAL_RETIRED_REFERENCE_PATHS = {
    "docs/HUB75_LAB.md",
    "docs/hub75_kernel_commit_log.md",
    "docs/hub75_kernel_tuning_log.md",
    "docs/hub75_script_inventory.json",
    "tests/utilities/test_hub75_lab.py",
}
LAB_DOC = REPO_ROOT / "docs" / "HUB75_LAB.md"


class TestHub75ScriptInventory:
    """Keep the exact 27-script audit machine-checkable after consolidation."""

    def test_inventory_has_unique_paths_and_expected_classification_counts(
        self,
    ) -> None:
        inventory = json.loads(INVENTORY_PATH.read_text())
        entries = inventory["entries"]
        paths = [entry["path"] for entry in entries]

        assert inventory["inventory_count"] == 27
        assert len(entries) == 27
        assert len(paths) == len(set(paths))
        assert _counts(entries, "classification") == {
            "active": 10,
            "one-off": 9,
            "superseded": 8,
        }
        assert _counts(entries, "disposition") == {
            "delete": 17,
            "replace": 6,
            "retain": 4,
        }

    def test_every_recovery_ref_resolves_to_the_exact_source(self) -> None:
        inventory = json.loads(INVENTORY_PATH.read_text())

        for entry in inventory["entries"]:
            prefix, revision, path = entry["recovery_ref"].split(":", maxsplit=2)
            assert prefix == "git"
            assert len(revision) == 40
            assert path == entry["path"]
            subprocess.run(
                ["git", "cat-file", "-e", f"{revision}:{path}"],
                cwd=REPO_ROOT,
                check=True,
            )

    def test_inventory_matches_the_preconsolidation_script_search(self) -> None:
        inventory = json.loads(INVENTORY_PATH.read_text())
        recovery_commit = inventory["recovery_commit"]
        result = subprocess.run(
            [
                "git",
                "ls-tree",
                "-r",
                "--name-only",
                recovery_commit,
                "scripts",
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        recovered_paths = {
            path
            for path in result.stdout.splitlines()
            if any(token in path.lower() for token in ("hub75", "rp1", "pio", "saleae", "logic"))
        }
        assert recovered_paths == {
            entry["path"] for entry in inventory["entries"]
        }
        assert "rg --files scripts" in LEGACY_SCRIPT_PATTERN

    def test_postconsolidation_script_surface_has_only_retained_paths(
        self,
    ) -> None:
        inventory = json.loads(INVENTORY_PATH.read_text())
        retained_paths = {
            entry["path"]
            for entry in inventory["entries"]
            if entry["disposition"] == "retain"
        }
        retired_paths = {
            entry["path"]
            for entry in inventory["entries"]
            if entry["disposition"] in {"replace", "delete"}
        }
        current_paths = {
            path.relative_to(REPO_ROOT).as_posix()
            for path in (REPO_ROOT / "scripts").rglob("*")
            if path.is_file()
            and path.suffix in {".c", ".py", ".sh"}
            and "__pycache__" not in path.parts
            and any(
                token in path.name.lower()
                for token in ("hub75", "rp1", "pio", "saleae", "logic")
            )
        }

        assert len(retired_paths) == 23
        assert all(not (REPO_ROOT / path).exists() for path in retired_paths)
        assert all((REPO_ROOT / path).is_file() for path in retained_paths)
        assert current_paths == retained_paths | {"scripts/hub75_experiment.py"}

    def test_live_inventory_conclusion_refs_resolve(self) -> None:
        inventory = json.loads(INVENTORY_PATH.read_text())

        for entry in inventory["entries"]:
            reference = entry["conclusion_ref"]
            if reference.startswith("git:"):
                continue
            relative_path, separator, anchor = reference.partition("#")
            document = REPO_ROOT / relative_path
            assert document.is_file(), reference
            if not separator:
                continue
            heading_anchors = {
                _markdown_heading_anchor(line.lstrip("#").strip())
                for line in document.read_text().splitlines()
                if line.startswith("#")
            }
            assert anchor in heading_anchors, reference

    def test_retired_paths_have_no_unlabeled_live_references(self) -> None:
        inventory = json.loads(INVENTORY_PATH.read_text())
        retired_basenames = {
            Path(entry["path"]).name
            for entry in inventory["entries"]
            if entry["disposition"] in {"replace", "delete"}
        }
        tracked = subprocess.run(
            ["git", "ls-files", "docs", "rp1", "scripts", "src", "tests"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        stale_references: list[str] = []
        for relative_path in tracked.stdout.splitlines():
            if relative_path in INTENTIONAL_RETIRED_REFERENCE_PATHS:
                continue
            path = REPO_ROOT / relative_path
            if not path.is_file():
                continue
            try:
                contents = path.read_text()
            except UnicodeDecodeError:
                continue
            for basename in retired_basenames:
                if basename in contents:
                    stale_references.append(f"{relative_path}: {basename}")

        assert stale_references == []

    def test_historical_logs_label_retired_commands_and_route_current_work(
        self,
    ) -> None:
        for relative_path in (
            "docs/hub75_kernel_commit_log.md",
            "docs/hub75_kernel_tuning_log.md",
        ):
            contents = (REPO_ROOT / relative_path).read_text()
            normalized = " ".join(
                line.removeprefix("> ").strip()
                for line in contents.splitlines()
            )
            assert "historical evidence only and must not be rerun" in normalized
            assert "docs/hub75_script_inventory.json" in contents
            assert "docs/HUB75_LAB.md" in contents

        tuning_log = (
            REPO_ROOT / "docs" / "hub75_kernel_tuning_log.md"
        ).read_text()
        next_directions = tuning_log.split("#### Concrete next directions", maxsplit=1)[
            1
        ].split("#### Validation", maxsplit=1)[0]
        assert "HUB75_LAB.md#trusted-logic2-capture-and-scoring" in next_directions
        assert "scripts/hub75_score_capture.py" not in next_directions


class TestHub75SramValidation:
    """Enforce the half-open RP1 SRAM layout from the safety note."""

    def test_documented_small_payload_can_use_safe_16k_tail(self) -> None:
        layout = validate_sram_buffer(
            payload_size=7_716,
            source_offset=0xA000,
            source_size=0x4000,
            required_alignment=0x1000,
        )

        assert layout.payload_end == 0x9E24
        assert layout.source_end == 0xE000

    def test_documented_large_payload_only_leaves_a_small_tail(self) -> None:
        layout = validate_sram_buffer(
            payload_size=19_720,
            source_offset=0xD000,
            source_size=0x2000,
            required_alignment=0x1000,
        )

        assert layout.payload_end == 0xCD08
        assert layout.source_end == 0xF000

    @pytest.mark.parametrize(
        ("payload_size", "source_offset", "source_size"),
        (
            (7_716, 0xC000, 0x4000),
            (7_716, 0x4000, 0x1000),
            (7_716, 0xA000, 0x6000),
            (7_716, 0x9F00, 0x6100),
            (7_716, 0xC000, 90_112),
            (19_720, 0xC000, 0x4000),
        ),
    )
    def test_unsafe_and_impossible_sources_are_rejected(
        self,
        payload_size: int,
        source_offset: int,
        source_size: int,
    ) -> None:
        with pytest.raises(ValueError):
            validate_sram_buffer(
                payload_size=payload_size,
                source_offset=source_offset,
                source_size=source_size,
            )

    def test_alignment_and_negative_offsets_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="not aligned"):
            validate_sram_buffer(
                payload_size=7_716,
                source_offset=0xA001,
                source_size=0x100,
                required_alignment=0x1000,
            )
        with pytest.raises(ValueError, match="inside"):
            validate_sram_buffer(
                payload_size=7_716,
                source_offset=-4,
                source_size=0x100,
            )

    def test_tight_24k_tail_may_end_exactly_at_mailbox_boundary(self) -> None:
        layout = validate_sram_buffer(
            payload_size=7_716,
            source_offset=0x9F00,
            source_size=0x6000,
        )

        assert layout.source_end == 0xFF00


class TestHub75ExperimentCatalog:
    """Keep the retained runner independent from the six replaced scripts."""

    def test_runtime_catalog_uses_package_backends_and_retained_shell_paths(
        self,
    ) -> None:
        experiments = list_experiments()

        for experiment in experiments:
            if experiment.implementation.startswith("heart."):
                assert importlib.util.find_spec(experiment.implementation) is not None
            else:
                assert (REPO_ROOT / experiment.implementation).is_file()
            assert experiment.implementation not in REPLACED_PATHS

    def test_known_good_plan_is_self_contained_and_reports_hash_policy(self) -> None:
        command = build_experiment_command(
            repo_root=REPO_ROOT,
            name="totem3-known-good-blue",
            settings=ExperimentSettings(strict_hashes=False),
        )

        assert command.argv[0].endswith("rp1_hub75_reproduce_totem_blue.sh")
        assert "rp1_hub75_color_loop" not in " ".join(command.argv)
        assert command.environment["RP1_HUB75_STRICT_HASHES"] == "0"
        assert "payload hash is enforced" in command.safety_evidence[-1]
        assert "module srcversion and SHA-256" in command.safety_evidence[-1]
        assert command.applied_settings == {
            "target": "michael@totem3.local",
            "seconds": 5.0,
            "strict_hashes": False,
        }
        assert command.fixed_invariants["transport_geometry"] == "256x64 A B C D"

    def test_direct_plan_requires_fresh_b800_prestarter(self) -> None:
        command = build_experiment_command(
            repo_root=REPO_ROOT,
            name="regular-p0p1-direct",
            settings=ExperimentSettings(),
        )
        direct_script = (REPO_ROOT / command.argv[0]).read_text()
        prestart_index = direct_script.index("RP1_HUB75_PRE_START_COMMAND")
        runner_index = direct_script.rindex("./rp1_hub75_run_candidate.sh")

        assert command.environment["RP1_HUB75_FRAME_SLOT_OFFSET"] == "0xb800"
        assert prestart_index < runner_index
        assert "before START_MAGIC" in command.safety_evidence[-1]

    @pytest.mark.parametrize(
        "settings",
        (
            ExperimentSettings(seconds=0),
            ExperimentSettings(rows=63),
            ExperimentSettings(pwm_bits=12),
            ExperimentSettings(red=256),
            ExperimentSettings(intensities="32,bad"),
            ExperimentSettings(candidate=""),
            ExperimentSettings(candidate="valid'; touch /tmp/injected; '"),
            ExperimentSettings(hardware_mapping="unknown"),
            ExperimentSettings(led_rgb_sequence="XYZ"),
            ExperimentSettings(gpio_diagnostic_mode="blink"),
            ExperimentSettings(gpio_diagnostic_mode="oe-toggle"),
        ),
    )
    def test_invalid_settings_fail_before_command_planning(
        self,
        settings: ExperimentSettings,
    ) -> None:
        with pytest.raises(ValueError):
            build_experiment_command(
                repo_root=REPO_ROOT,
                name="runtime-color-cycle",
                settings=settings,
            )

    def test_known_good_rejects_noncanonical_ignored_geometry(self) -> None:
        with pytest.raises(ValueError, match="does not accept"):
            build_experiment_command(
                repo_root=REPO_ROOT,
                name="totem3-known-good-blue",
                settings=ExperimentSettings(rows=32, hardware_mapping="adafruit-hat"),
            )

    def test_runtime_rejects_noncanonical_remote_scanner_settings(self) -> None:
        with pytest.raises(ValueError, match="does not accept"):
            build_experiment_command(
                repo_root=REPO_ROOT,
                name="runtime-gradient",
                settings=ExperimentSettings(target="totem4.local"),
            )

    def test_list_json_names_each_experiment_applied_parameter(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        assert hub75_lab_main(["list", "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)

        assert {
            entry["name"]: tuple(entry["applied_parameters"])
            for entry in payload
        } == APPLIED_SETTING_NAMES

    def test_runner_help_preserves_hash_policy_and_forbids_oe_toggle(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        with pytest.raises(SystemExit, match="0"):
            hub75_lab_main(["run", "--help"])
        help_text = " ".join(capsys.readouterr().out.split())

        assert "Additionally enforce known-good module srcversion and SHA-256." in (
            help_text
        )
        assert "oe-toggle" not in help_text

    def test_lgpio_construction_failure_falls_back_to_rpi_gpio(self) -> None:
        fallback_backend = GpioBackend()
        attempts: list[str] = []

        def fail_lgpio() -> GpioBackend:
            attempts.append("lgpio")
            raise RuntimeError("gpiochip0 is unavailable")

        def use_rpi_gpio() -> GpioBackend:
            attempts.append("RPi.GPIO")
            return fallback_backend

        assert _select_gpio_backend(fail_lgpio, use_rpi_gpio) is fallback_backend
        assert attempts == ["lgpio", "RPi.GPIO"]

    def test_public_cli_scripts_remain_directly_executable(self) -> None:
        for relative_path in (
            "scripts/hub75_experiment.py",
            "scripts/rp1_hub75_linux_bundle.py",
        ):
            mode = (REPO_ROOT / relative_path).stat().st_mode
            assert mode & stat.S_IXUSR

    def test_command_matrix_covers_every_retained_experiment_and_bundle_action(
        self,
    ) -> None:
        documentation = LAB_DOC.read_text()

        for experiment in list_experiments():
            assert f"run {experiment.name}" in documentation
        for action in ("list", "apply", "diff", "deploy-target", "preflight"):
            assert f"bundle {action}" in documentation
        normalized_documentation = " ".join(documentation.split())
        assert "does not start a Logic2 acquisition" in normalized_documentation
        assert "n_temporal_planes=0" in documentation
        for policy_text in (
            "75%",
            "25%",
            "at least `0.90`",
            "Higher better",
            "`edges_per_lat_interval`",
            "maxima remain visible diagnostics, but are not score features",
        ):
            assert policy_text in normalized_documentation


class TestHub75CaptureEvidence:
    """Make capture trust depend on traceable host, control, OE, and color evidence."""

    def test_trusted_red_capture_reports_color_and_active_low_oe_duty(
        self,
        tmp_path: Path,
    ) -> None:
        capture_path = tmp_path / "red.csv"
        _write_capture(capture_path, red_activity=True)

        report = _analyze_trusted_capture(
            capture_path,
            evidence_root=tmp_path / "proof",
            expected_active_colors=("R1", "R2"),
        )
        payload = capture_report_payload(report)

        assert report.is_trusted is True
        assert len(report.capture_sha256) == 64
        assert payload["capture_sha256"] == report.capture_sha256
        assert payload["color_evidence_complete"] is True
        assert payload["color_pattern_valid"] is True
        assert payload["color_signal_evidence"]["G1"]["edge_count"] == 0
        assert (
            payload["color_signal_evidence"]["R1"]["edges_per_lat_interval"]
            == pytest.approx(1.0)
        )
        assert payload["oe_active_low_duty"]["active_fraction"] > 0
        assert payload["oe_active_low_duty"]["blank_fraction"] > 0
        assert payload["oe_active_low_duty"]["max_blank_ns"] is not None
        assert payload["clock"]["edge_count"] > 0
        assert payload["clock"]["max_period_ns"] is not None
        assert payload["latch"]["rise_count"] > 0
        assert payload["address_max_edge_interval_ns"]["A"] is not None

    def test_black_capture_can_be_trusted_with_static_low_color_evidence(
        self,
        tmp_path: Path,
    ) -> None:
        capture_path = tmp_path / "black.csv"
        _write_capture(capture_path, red_activity=False)

        report = _analyze_trusted_capture(
            capture_path,
            evidence_root=tmp_path / "proof",
            expected_active_colors=(),
        )

        assert report.is_trusted is True
        assert report.color_pattern_valid is True

    def test_silent_capture_fails_closed_but_remains_diagnosable(
        self,
        tmp_path: Path,
    ) -> None:
        capture_path = tmp_path / "silent.csv"
        _write_flat_capture(capture_path)

        with pytest.raises(ValueError, match="diagnostic-only"):
            _analyze_trusted_capture(
                capture_path,
                evidence_root=tmp_path / "proof",
                expected_active_colors=("R1", "R2"),
            )

        report = _analyze_capture_data(
            capture_path,
            signal_map=DEFAULT_CAPTURE_SIGNAL_MAP,
            cols=4,
            expected_active_colors=("R1", "R2"),
            target_host="totem3.local",
            probe_host="totem3.local",
        )
        assert report.is_trusted is False
        assert report.diagnosis.diagnosis == "electrically_silent"

    def test_pure_csv_analysis_cannot_create_trusted_provenance(
        self,
        tmp_path: Path,
    ) -> None:
        capture_path = tmp_path / "red.csv"
        _write_capture(capture_path, red_activity=True)

        report = _analyze_capture_data(
            capture_path,
            signal_map=DEFAULT_CAPTURE_SIGNAL_MAP,
            cols=4,
            expected_active_colors=("R1", "R2"),
            target_host="totem3.local",
            probe_host="totem3.local",
        )

        assert report.diagnosis.summary.valid_hub75 is True
        assert report.provenance is None
        assert report.is_trusted is False

    def test_probe_proof_hashes_the_source_and_rejects_silence(
        self,
        tmp_path: Path,
    ) -> None:
        capture_path = tmp_path / "probe.csv"
        proof_path = tmp_path / "probe.json"
        execution_path = tmp_path / "execution.json"
        _write_probe_capture(capture_path)
        _write_probe_execution(execution_path)

        create_probe_proof(
            capture_path,
            target_host="michael@totem3.local",
            probe_host="totem3.local",
            proof_signal="CLK",
            signal_map=DEFAULT_CAPTURE_SIGNAL_MAP,
            execution_artifact=execution_path,
            output_path=proof_path,
        )
        proof = json.loads(proof_path.read_text())

        assert proof["observed_edge_count"] == 8
        assert len(proof["capture_sha256"]) == 64
        assert proof["proof_signal"] == "CLK"
        assert proof["median_edge_interval_seconds"] == pytest.approx(0.05)
        assert proof["trust_basis"] == "operator_correlated_host_toggle"

        silent_path = tmp_path / "silent.csv"
        _write_flat_capture(silent_path)
        with pytest.raises(ValueError, match="observed 0 edges"):
            create_probe_proof(
                silent_path,
                target_host="totem3.local",
                probe_host="totem3.local",
                proof_signal="CLK",
                signal_map=DEFAULT_CAPTURE_SIGNAL_MAP,
                execution_artifact=execution_path,
                output_path=proof_path,
            )

    def test_probe_toggle_blanks_both_oe_pins_and_stops_scanner(self) -> None:
        command = build_probe_toggle_command(
            target_host="michael@totem3.local",
            gpio=17,
            toggles=4,
            interval_seconds=0.05,
        )
        remote_command = command[-1]

        assert "pkill -TERM -f '[r]p1_hub75_run_candidate.sh'" in remote_command
        assert "pgrep -f '[r]p1_hub75_run_candidate.sh'" in remote_command
        assert "pinctrl set 18 op dh" in remote_command
        assert "pinctrl set 4 op dh" in remote_command
        assert "pinctrl set 17 op dh" in remote_command
        assert "pinctrl set 17 no pn" in remote_command
        assert "pinctrl set 18 no pn" not in remote_command
        assert "pinctrl set 4 no pn" not in remote_command

    def test_unexpected_green_activity_invalidates_declared_red_pattern(
        self,
        tmp_path: Path,
    ) -> None:
        baseline_path = tmp_path / "baseline.csv"
        candidate_path = tmp_path / "candidate.csv"
        _write_capture(baseline_path, red_activity=True)
        _write_capture(
            candidate_path,
            red_activity=True,
            unexpected_green_activity=True,
        )
        baseline_report = _analyze_trusted_capture(
            baseline_path,
            evidence_root=tmp_path / "baseline-proof",
            expected_active_colors=("R1", "R2"),
        )
        candidate_report = _analyze_trusted_capture(
            candidate_path,
            evidence_root=tmp_path / "candidate-proof",
            expected_active_colors=("R1", "R2"),
            require_trusted=False,
        )
        _baseline, _candidate, legacy = score_hub75_capture_files(
            baseline_path,
            candidate_path,
            signal_map=DEFAULT_CAPTURE_SIGNAL_MAP,
            cols=4,
        )
        complete = score_complete_similarity(
            baseline_report,
            candidate_report,
            legacy,
        )

        assert legacy.total == pytest.approx(1.0)
        assert candidate_report.color_pattern_valid is False
        assert candidate_report.is_trusted is False
        assert complete.color_similarity < 1.0
        assert complete.overall_similarity < legacy.total
        assert complete.verdict == "fail"

    def test_complete_similarity_is_independent_of_capture_cycle_count(
        self,
        tmp_path: Path,
    ) -> None:
        baseline_path = tmp_path / "baseline.csv"
        candidate_path = tmp_path / "candidate.csv"
        _write_capture(
            baseline_path,
            red_activity=True,
            row_pair_count=17,
            vary_address=False,
        )
        _write_capture(
            candidate_path,
            red_activity=True,
            row_pair_count=33,
            red_phase=1,
            benign_tail_samples=1,
            benign_tail_delay_seconds=1e-6,
            vary_address=False,
        )
        baseline_report = _analyze_trusted_capture(
            baseline_path,
            evidence_root=tmp_path / "baseline-proof",
            expected_active_colors=("R1", "R2"),
        )
        candidate_report = _analyze_trusted_capture(
            candidate_path,
            evidence_root=tmp_path / "candidate-proof",
            expected_active_colors=("R1", "R2"),
        )
        baseline_summary, candidate_summary, control = score_hub75_capture_files(
            baseline_path,
            candidate_path,
            signal_map=DEFAULT_CAPTURE_SIGNAL_MAP,
            cols=4,
        )

        complete = score_complete_similarity(
            baseline_report,
            candidate_report,
            control,
        )

        assert baseline_report.color_edge_counts["R1"] != (
            candidate_report.color_edge_counts["R1"]
        )
        assert baseline_report.color_evidence["R1"] is not None
        assert candidate_report.color_evidence["R1"] is not None
        assert baseline_report.color_evidence["R1"].final_level != (
            candidate_report.color_evidence["R1"].final_level
        )
        assert baseline_report.color_evidence[
            "R1"
        ].edges_per_lat_interval == pytest.approx(
            candidate_report.color_evidence["R1"].edges_per_lat_interval
        )
        assert baseline_summary.max_oe_blank_ns != candidate_summary.max_oe_blank_ns
        assert "max_oe_blank_ns" not in control.feature_scores
        assert "max_clk_period_ns" not in control.feature_scores
        assert not any(
            name.startswith("max_address_edge_interval_ns_")
            for name in control.feature_scores
        )
        assert complete.control_timing_address_similarity == pytest.approx(1.0)
        assert complete.color_similarity == pytest.approx(1.0)
        assert complete.overall_similarity == pytest.approx(1.0)
        assert complete.control_timing_address_weight == pytest.approx(0.75)
        assert complete.color_weight == pytest.approx(0.25)
        assert complete.pass_threshold == pytest.approx(0.90)
        assert complete.verdict == "pass"

    def test_latch_fault_rate_uses_complete_intervals_across_windows(
        self,
        tmp_path: Path,
    ) -> None:
        baseline_path = tmp_path / "baseline.csv"
        candidate_path = tmp_path / "candidate.csv"
        _write_capture(
            baseline_path,
            red_activity=True,
            row_pair_count=17,
            latch_while_output_enabled=True,
        )
        _write_capture(
            candidate_path,
            red_activity=True,
            row_pair_count=33,
            latch_while_output_enabled=True,
        )
        baseline, candidate, control = score_hub75_capture_files(
            baseline_path,
            candidate_path,
            signal_map=DEFAULT_CAPTURE_SIGNAL_MAP,
            cols=4,
        )

        assert baseline.lat_while_output_enabled_count == baseline.interval_count
        assert candidate.lat_while_output_enabled_count == candidate.interval_count
        assert control.feature_scores["lat_while_output_enabled_count"] == (
            pytest.approx(1.0)
        )

    def test_extra_expected_color_transitions_reduce_complete_similarity(
        self,
        tmp_path: Path,
    ) -> None:
        baseline_path = tmp_path / "baseline.csv"
        candidate_path = tmp_path / "candidate.csv"
        _write_capture(baseline_path, red_activity=True)
        _write_capture(
            candidate_path,
            red_activity=True,
            extra_red_transitions=True,
        )
        baseline_report = _analyze_trusted_capture(
            baseline_path,
            evidence_root=tmp_path / "baseline-proof",
            expected_active_colors=("R1", "R2"),
        )
        candidate_report = _analyze_trusted_capture(
            candidate_path,
            evidence_root=tmp_path / "candidate-proof",
            expected_active_colors=("R1", "R2"),
        )
        _baseline, _candidate, control = score_hub75_capture_files(
            baseline_path,
            candidate_path,
            signal_map=DEFAULT_CAPTURE_SIGNAL_MAP,
            cols=4,
        )

        complete = score_complete_similarity(
            baseline_report,
            candidate_report,
            control,
        )

        assert baseline_report.is_trusted
        assert candidate_report.is_trusted
        assert complete.color_channel_similarity["R1"] < 1.0
        assert complete.color_channel_similarity["R2"] < 1.0
        assert complete.color_similarity < 1.0
        assert complete.verdict == "fail"

    def test_complete_similarity_policy_is_explicit_and_bounded(self) -> None:
        assert (
            COMPLETE_SIMILARITY_CONTROL_WEIGHT
            + COMPLETE_SIMILARITY_COLOR_WEIGHT
            == pytest.approx(1.0)
        )
        assert COMPLETE_SIMILARITY_CONTROL_WEIGHT == pytest.approx(0.75)
        assert COMPLETE_SIMILARITY_COLOR_WEIGHT == pytest.approx(0.25)
        assert COMPLETE_SIMILARITY_PASS_THRESHOLD == pytest.approx(0.90)

    def test_saleae_support_is_derived_from_the_selected_environment(self) -> None:
        assert _saleae_support_available("json") is True
        assert _saleae_support_available("heart_missing_saleae_support") is False

    def test_capture_preflight_accepts_complete_correlated_evidence(
        self,
        tmp_path: Path,
    ) -> None:
        proof_path, _capture_path, _execution_path = _write_valid_probe_bundle(
            tmp_path
        )
        logic2_application = tmp_path / "Logic.app"
        logic2_application.mkdir()

        CapturePreflight(
            logic2_application=logic2_application,
            logic2_session_ready_attested=True,
            target_host="michael@totem3.local",
            probe_host="totem3.local",
            probe_proof=proof_path,
        )._validate_saleae_module("json")

    def test_capture_preflight_rejects_missing_logic2_application(
        self,
        tmp_path: Path,
    ) -> None:
        with pytest.raises(ValueError, match="application not found"):
            CapturePreflight(
                logic2_application=tmp_path / "missing.app",
                logic2_session_ready_attested=True,
                target_host="totem3.local",
                probe_host="totem3.local",
                probe_proof=tmp_path / "proof.json",
            )._validate_saleae_module("json")

    def test_capture_preflight_rejects_session_ready_false(
        self,
        tmp_path: Path,
    ) -> None:
        logic2_application = tmp_path / "Logic.app"
        logic2_application.mkdir()

        with pytest.raises(ValueError, match="stop or close"):
            CapturePreflight(
                logic2_application=logic2_application,
                logic2_session_ready_attested=False,
                target_host="totem3.local",
                probe_host="totem3.local",
                probe_proof=tmp_path / "proof.json",
            )._validate_saleae_module("json")

    def test_capture_preflight_rejects_missing_saleae_support(
        self,
        tmp_path: Path,
    ) -> None:
        logic2_application = tmp_path / "Logic.app"
        logic2_application.mkdir()

        with pytest.raises(ValueError, match="Saleae automation support"):
            CapturePreflight(
                logic2_application=logic2_application,
                logic2_session_ready_attested=True,
                target_host="totem3.local",
                probe_host="totem3.local",
                probe_proof=tmp_path / "proof.json",
            )._validate_saleae_module("heart_missing_saleae_support")

    def test_capture_preflight_rejects_target_probe_mismatch(
        self,
        tmp_path: Path,
    ) -> None:
        logic2_application = tmp_path / "Logic.app"
        logic2_application.mkdir()

        with pytest.raises(ValueError, match="does not match target host"):
            CapturePreflight(
                logic2_application=logic2_application,
                logic2_session_ready_attested=True,
                target_host="totem3.local",
                probe_host="totem4.local",
                probe_proof=tmp_path / "proof.json",
            )._validate_saleae_module("json")

    def test_capture_preflight_rejects_probe_source_hash_tamper(
        self,
        tmp_path: Path,
    ) -> None:
        proof_path, capture_path, _execution_path = _write_valid_probe_bundle(
            tmp_path
        )
        capture_path.write_text(capture_path.read_text() + "\n")
        logic2_application = tmp_path / "Logic.app"
        logic2_application.mkdir()

        with pytest.raises(ValueError, match="source CSV hash"):
            CapturePreflight(
                logic2_application=logic2_application,
                logic2_session_ready_attested=True,
                target_host="totem3.local",
                probe_host="totem3.local",
                probe_proof=proof_path,
            )._validate_saleae_module("json")

    def test_capture_preflight_rejects_execution_label_mismatch(
        self,
        tmp_path: Path,
    ) -> None:
        proof_path, _capture_path, _execution_path = _write_valid_probe_bundle(
            tmp_path
        )
        proof = json.loads(proof_path.read_text())
        proof["target_host"] = "totem4.local"
        proof["probe_host"] = "totem4.local"
        proof_path.write_text(json.dumps(proof))
        logic2_application = tmp_path / "Logic.app"
        logic2_application.mkdir()

        with pytest.raises(ValueError, match="execution transcript"):
            CapturePreflight(
                logic2_application=logic2_application,
                logic2_session_ready_attested=True,
                target_host="totem4.local",
                probe_host="totem4.local",
                probe_proof=proof_path,
            )._validate_saleae_module("json")

    @pytest.mark.parametrize(
        "override",
        (
            "UNKNOWN=15",
            "CLK=-1",
            "CLK=not-an-integer",
            "R1=6",
        ),
    )
    def test_signal_map_rejects_unknown_invalid_and_duplicate_assignments(
        self,
        override: str,
    ) -> None:
        with pytest.raises(ValueError):
            _parse_signal_map([override])


def _counts(entries: list[dict[str, object]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        value = str(entry[field])
        counts[value] = counts.get(value, 0) + 1
    return counts


def _markdown_heading_anchor(heading: str) -> str:
    normalized = re.sub(r"[^\w -]", "", heading.lower())
    return re.sub(r" +", "-", normalized)


def _write_capture(
    path: Path,
    *,
    red_activity: bool,
    unexpected_green_activity: bool = False,
    extra_red_transitions: bool = False,
    row_pair_count: int = 6,
    red_phase: int = 0,
    benign_tail_samples: int = 0,
    benign_tail_delay_seconds: float = 20e-9,
    latch_while_output_enabled: bool = False,
    vary_address: bool = True,
) -> None:
    state = [0] * 14
    state[DEFAULT_CAPTURE_SIGNAL_MAP["OE"]] = 1
    state[DEFAULT_CAPTURE_SIGNAL_MAP["R1"]] = red_phase
    state[DEFAULT_CAPTURE_SIGNAL_MAP["R2"]] = red_phase
    timestamp = 0.0
    rows: list[tuple[float, list[int]]] = [(timestamp, state.copy())]

    def emit(
        signal: str | None = None,
        value: int = 0,
        *,
        delay_seconds: float = 20e-9,
    ) -> None:
        nonlocal timestamp
        timestamp += delay_seconds
        if signal is not None:
            state[DEFAULT_CAPTURE_SIGNAL_MAP[signal]] = value
        rows.append((timestamp, state.copy()))

    for row_pair in range(row_pair_count):
        emit("OE", 1)
        for bit, signal in enumerate(("A", "B", "C", "D")):
            desired = (row_pair >> bit) & 1 if vary_address else 0
            if state[DEFAULT_CAPTURE_SIGNAL_MAP[signal]] != desired:
                emit(signal, desired)
        if red_activity:
            red_level = (row_pair + red_phase) & 1
            if state[DEFAULT_CAPTURE_SIGNAL_MAP["R1"]] != red_level:
                if unexpected_green_activity:
                    state[DEFAULT_CAPTURE_SIGNAL_MAP["G1"]] = red_level
                    state[DEFAULT_CAPTURE_SIGNAL_MAP["G2"]] = red_level
                emit("R1", red_level)
                emit("R2", red_level)
            if extra_red_transitions:
                emit("R1", red_level ^ 1)
                emit("R2", red_level ^ 1)
                emit("R1", red_level)
                emit("R2", red_level)
        if unexpected_green_activity and not red_activity:
            green_level = row_pair & 1
            if state[DEFAULT_CAPTURE_SIGNAL_MAP["G1"]] != green_level:
                emit("G1", green_level)
                emit("G2", green_level)
        for _column in range(4):
            emit("CLK", 1)
            emit("CLK", 0)
        if latch_while_output_enabled:
            emit("OE", 0)
        emit("LAT", 1)
        emit("LAT", 0)
        if latch_while_output_enabled:
            emit("OE", 1)
        emit("OE", 0)
        emit()
        emit("OE", 1)

    for _ in range(benign_tail_samples):
        emit(delay_seconds=benign_tail_delay_seconds)

    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Time [s]", *[f"Channel {index}" for index in range(14)]])
        for sample_timestamp, sample_state in rows:
            writer.writerow([f"{sample_timestamp:.9f}", *sample_state])


def _write_flat_capture(path: Path) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Time [s]", *[f"Channel {index}" for index in range(14)]])
        writer.writerow(["0.000000000", *([0] * 14)])
        writer.writerow(["0.000000020", *([0] * 14)])


def _write_probe_capture(path: Path) -> None:
    state = [0] * 14
    timestamp = 0.0
    rows = [(timestamp, state.copy())]
    clk_channel = DEFAULT_CAPTURE_SIGNAL_MAP["CLK"]
    for edge_index in range(8):
        timestamp += 0.05
        state[clk_channel] = (edge_index + 1) & 1
        rows.append((timestamp, state.copy()))

    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Time [s]", *[f"Channel {index}" for index in range(14)]])
        for sample_timestamp, sample_state in rows:
            writer.writerow([f"{sample_timestamp:.9f}", *sample_state])


def _write_probe_execution(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "target_host": "michael@totem3.local",
                "proof_signal": "CLK",
                "gpio": 17,
                "toggles": 4,
                "expected_edge_count": 8,
                "interval_seconds": 0.05,
                "command": (
                    "ssh michael@totem3.local \"pkill -TERM -f "
                    "'[r]p1_hub75_run_candidate.sh'; "
                    "pinctrl set 18 op dh; pinctrl set 4 op dh; "
                    "pinctrl set 17 op dh\""
                ),
                "safe_preconditions": [
                    "scanner stopped",
                    "GPIO18 blank high",
                    "GPIO4 blank high",
                ],
                "cleanup": [
                    "GPIO17 restored",
                    "GPIO18 left actively high/blank",
                    "GPIO4 left actively high/blank",
                ],
                "started_at": "2026-07-26T00:00:00+00:00",
                "finished_at": "2026-07-26T00:00:01+00:00",
                "returncode": 0,
            }
        )
    )


def _write_valid_probe_bundle(tmp_path: Path) -> tuple[Path, Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    capture_path = tmp_path / "probe.csv"
    execution_path = tmp_path / "execution.json"
    proof_path = tmp_path / "proof.json"
    _write_probe_capture(capture_path)
    _write_probe_execution(execution_path)
    create_probe_proof(
        capture_path,
        target_host="michael@totem3.local",
        probe_host="totem3.local",
        proof_signal="CLK",
        signal_map=DEFAULT_CAPTURE_SIGNAL_MAP,
        execution_artifact=execution_path,
        output_path=proof_path,
    )
    return proof_path, capture_path, execution_path


def _analyze_trusted_capture(
    capture_path: Path,
    *,
    evidence_root: Path,
    expected_active_colors: tuple[str, ...],
    require_trusted: bool = True,
) -> CaptureReport:
    proof_path, _proof_capture, _execution_path = _write_valid_probe_bundle(
        evidence_root
    )
    logic2_application = evidence_root / "Logic.app"
    logic2_application.mkdir()
    return _analyze_capture_with_saleae_module(
        capture_path,
        preflight=CapturePreflight(
            logic2_application=logic2_application,
            logic2_session_ready_attested=True,
            target_host="michael@totem3.local",
            probe_host="totem3.local",
            probe_proof=proof_path,
        ),
        signal_map=DEFAULT_CAPTURE_SIGNAL_MAP,
        cols=4,
        expected_active_colors=expected_active_colors,
        require_trusted=require_trusted,
        saleae_module_name="json",
    )
