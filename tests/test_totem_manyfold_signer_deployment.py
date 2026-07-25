from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOTEM_DRIVER_DIRECTORY = PROJECT_ROOT / "drivers" / "totem"


def test_supervisor_starts_one_signer_before_heart() -> None:
    supervisor = (
        TOTEM_DRIVER_DIRECTORY / "heart-totem.supervisor.conf"
    ).read_text(encoding="utf-8")

    assert supervisor.count("[program:heart-manyfold-signer]") == 1
    signer_section = supervisor.split("[program:heart-manyfold-signer]", 1)[1]
    signer_section = signer_section.split("[program:", 1)[0]
    assert "priority=15" in signer_section
    assert "autorestart=true" in signer_section


def test_signer_service_has_bounded_resources_and_strict_directories() -> None:
    launcher = (
        TOTEM_DRIVER_DIRECTORY / "heart-supervisor-signer.sh"
    ).read_text(encoding="utf-8")
    service = (TOTEM_DRIVER_DIRECTORY / "manyfold-signer.service").read_text(
        encoding="utf-8"
    )

    assert '--max-clients "${MAX_CLIENTS}"' in launcher
    assert '--max-audit-entries "${MAX_AUDIT_ENTRIES}"' in launcher
    assert 'install -d -m 0700 "${SIGNER_STATE_DIRECTORY}"' in launcher
    assert "RuntimeDirectoryMode=0700" in service
    assert "StateDirectoryMode=0700" in service


def test_totem_environment_exposes_only_the_signer_client_boundary() -> None:
    environment = (TOTEM_DRIVER_DIRECTORY / "totem.env.example").read_text(
        encoding="utf-8"
    )

    assert "HEART_MANYFOLD_SIGNER_ENABLED=1" in environment
    assert "HEART_MANYFOLD_SIGNER_SOCKET=" in environment
    assert "PRIVATE_KEY" not in environment
    assert "machine-key.pem" not in environment


def test_bootstrap_initializes_signer_identity_before_supervisor() -> None:
    bootstrap = (
        TOTEM_DRIVER_DIRECTORY / "bootstrap-supervisord.sh"
    ).read_text(encoding="utf-8")

    assert "sync_heart_environment\ninitialize_manyfold_signer\n" in bootstrap
    assert (
        'run_root "${enrollment_bin}" initialize \\\n'
        '    --state-dir "${state_directory}"'
    ) in bootstrap
    assert '--authority-socket "${authority_socket}"' in bootstrap
    assert '--token-file "${token_file}"' in bootstrap
    assert '--token "${' not in bootstrap
    assert 'run_root rm -f "${token_file}"' in bootstrap
    assert "HEART_MANYFOLD_MACHINE_ID" not in bootstrap
