venv_dir = ".tilt-venv"
python_bin = "python3"

config.define_string(
    "configuration",
    default="full_screen_test",
    description="Configuration passed to `totem run`",
)
config.define_bool(
    "x11_forward",
    default=False,
    description="Enable X11 forwarding when running on a Pi",
)
config.define_bool(
    "add_low_power_mode",
    default=True,
    description="Include the low power mode when launching totem",
)

cfg = config.parse()

setup_script_lines = [
    "set -euo pipefail",
    'if [ ! -d "%s" ]; then' % venv_dir,
    '  %s -m venv %s' % (python_bin, venv_dir),
    "fi",
    "%s/bin/python -m ensurepip --upgrade" % venv_dir,
    "%s/bin/pip install --no-build-isolation -e .[dev]" % venv_dir,
]
setup_script = "\n".join(setup_script_lines)

local_resource(
    "setup-env",
    update_cmd="bash -lc '%s'" % setup_script,
    deps=[
        "pyproject.toml",
        "README.md",
        "Makefile",
    ],
    trigger_mode=TRIGGER_MODE_AUTO,
    env={"PYENV_VERSION": "system"},
)

x11_flag = ""
if cfg.get("x11_forward"):
    x11_flag = " --x11-forward"

low_power_flag = ""
if not cfg.get("add_low_power_mode"):
    low_power_flag = " --no-add-low-power-mode"

run_cmd = "%s/bin/totem run --configuration %s%s%s" % (
    venv_dir,
    cfg.get("configuration"),
    x11_flag,
    low_power_flag,
)

local_resource(
    "totem",
    serve_cmd="bash -lc '%s'" % run_cmd,
    deps=[
        "src",
        "drivers",
        "experimental",
        "scripts",
        "pyproject.toml",
    ],
    resource_deps=["setup-env"],
    env={"PYENV_VERSION": "system"},
)

local_resource(
    "tests",
    cmd="bash -lc '%s/bin/python -m pytest'" % venv_dir,
    deps=["src", "test"],
    resource_deps=["setup-env"],
    trigger_mode=TRIGGER_MODE_MANUAL,
    env={"PYENV_VERSION": "system"},
)
