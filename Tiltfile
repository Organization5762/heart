venv_dir = ".tilt-venv"
required_python = "3.11.2"

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

python_candidates = [
    "$PYENV_ROOT/versions/%s/bin/python" % required_python,
    "$HOME/.pyenv/versions/%s/bin/python" % required_python,
    "python%s" % required_python[:4],
    "python3",
]

python_probe_lines = [
    "python_bin=",
    "for candidate in \\",
]
for candidate in python_candidates[:-1]:
    python_probe_lines.append('    "%s" \\' % candidate)
python_probe_lines.append('    "%s"' % python_candidates[-1])
python_probe_lines.extend([
    "do",
    "  resolved=$(eval echo $candidate)",
    "  if [ -x \"$resolved\" ]; then",
    "    python_bin=$resolved",
    "    break",
    "  fi",
    "done",
    "if [ -z \"$python_bin\" ]; then",
    "  echo 'Unable to find Python %s (tried pyenv and system interpreters)' >&2" % required_python,
    "  exit 1",
    "fi",
])

setup_script_lines = [
    "set -euo pipefail",
] + python_probe_lines + [
    'if [ ! -d "%s" ]; then' % venv_dir,
    '  "$python_bin" -m venv %s' % venv_dir,
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
)

local_resource(
    "tests",
    cmd="bash -lc '%s/bin/python -m pytest'" % venv_dir,
    deps=["src", "test"],
    resource_deps=["setup-env"],
    trigger_mode=TRIGGER_MODE_MANUAL,
)
