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
    "%s/bin/pip install --no-build-isolation -e experimental/peripheral_sidecar" % venv_dir,
    "%s/bin/pip install --no-build-isolation -e experimental/isolated_rendering" % venv_dir,
]
setup_script = "\n".join(setup_script_lines)

local_resource(
    "setup-env",
    update_cmd="bash -lc '%s'" % setup_script,
    deps=[
        "pyproject.toml",
        "README.md",
        "Makefile",
        "experimental/peripheral_sidecar/pyproject.toml",
        "experimental/isolated_rendering/pyproject.toml",
    ],
    trigger_mode=TRIGGER_MODE_AUTO,
)

x11_flag = ""
if cfg.get("x11_forward"):
    x11_flag = " --x11-forward"

low_power_flag = ""
if not cfg.get("add_low_power_mode"):
    low_power_flag = " --no-add-low-power-mode"

isolated_render_socket = "/tmp/heart_matrix.sock"

run_cmd = "%s/bin/totem run --configuration %s%s%s" % (
    venv_dir,
    cfg.get("configuration"),
    x11_flag,
    low_power_flag,
)

isolated_render_cmd = "%s/bin/isolated-render run --unix-socket %s --fps 120" % (
    venv_dir,
    isolated_render_socket,
)

local_resource(
    "isolated-rendering",
    serve_cmd="bash -lc '%s'" % isolated_render_cmd,
    deps=[
        "experimental/isolated_rendering/src",
        "experimental/isolated_rendering/pyproject.toml",
    ],
    resource_deps=["setup-env"],
)

docker_compose("experimental/mqtt_broker/docker-compose.yml")

configure_resource("mqtt", resource_deps=["setup-env"])

peripheral_sidecar_env = {
    "HEART_MQTT_HOST": "localhost",
    "HEART_MQTT_PORT": "1883",
}

peripheral_sidecar_cmd = "%s/bin/heart-peripheral-sidecar" % venv_dir

local_resource(
    "peripheral-sidecar",
    serve_cmd="bash -lc '%s'" % peripheral_sidecar_cmd,
    deps=[
        "experimental/peripheral_sidecar/src",
        "experimental/peripheral_sidecar/pyproject.toml",
    ],
    env=peripheral_sidecar_env,
    resource_deps=["setup-env", "mqtt"],
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
    env={
        "USE_ISOLATED_RENDERER": "true",
        "ISOLATED_RENDER_SOCKET": isolated_render_socket,
    },
    resource_deps=["setup-env", "isolated-rendering"],
)

local_resource(
    "tests",
    cmd="bash -lc '%s/bin/python -m pytest'" % venv_dir,
    deps=["src", "test"],
    resource_deps=["setup-env"],
    trigger_mode=TRIGGER_MODE_MANUAL,
)
