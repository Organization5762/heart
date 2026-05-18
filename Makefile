PYTHON_SOURCES = packages src tests
DOCS_SOURCES = docs
TOOL_LIST_FILE = scripts/harness_tools.txt
TOOLS := $(shell scripts/list_harness_tools.sh $(TOOL_LIST_FILE))
BUILD_ARGS ?=
RUN_CONFIGURATION ?= lib_2025
FORWARD_TO_BEATS_APP ?= 0
BEATS_WEBSOCKET_BIND_HOST ?= 0.0.0.0
SEMGREP_CONFIG ?= semgrep.yml
SEMGREP_TARGETS ?= src
SEMGREP_ARGS ?= --config $(SEMGREP_CONFIG) --metrics=off --disable-version-check
SEMGREP_EXTRA_ARGS ?=
DEBUG_PANEL_ROWS ?= 64
DEBUG_PANEL_COLS ?= 64
DEBUG_CHAIN_LENGTH ?= 1
DEBUG_PARALLEL ?= 1
PIO_BENCH_CHAIN_LENGTH ?= 1
PIO_BENCH_FRAME_COUNT ?= 64
PIO_BENCH_ITERATIONS ?= 5
PIO_BENCH_PANEL_COLS ?= 64
PIO_BENCH_PANEL_ROWS ?= 64
PIO_BENCH_PARALLEL ?= 1
PIO_BENCH_PIPELINE_DEPTH ?= 2
PIO_BENCH_PWM_BITS ?= 11
PIO_BENCH_SCAN_CLOCK_DIVIDER ?= 1.0
PIO_BENCH_SCAN_LSB_DWELL_TICKS ?= 2
PYTHON ?= $(shell command -v python3 2>/dev/null || command -v python 2>/dev/null)
.PHONY: install bootstrap-native debug-matrix-pinctrl test-matrix-pinctrl pi_install format check semgrep test build check-harness build-info doctor focus focus-watch dev-session fractal run debug-gamepad

bootstrap-native:
	@bash scripts/bootstrap_native_runtime.sh

debug-matrix-pinctrl:
	@uv run python -m heart.device.rgb_display.debug \
		--panel-rows $(DEBUG_PANEL_ROWS) \
		--panel-cols $(DEBUG_PANEL_COLS) \
		--chain-length $(DEBUG_CHAIN_LENGTH) \
		--parallel $(DEBUG_PARALLEL)

test-matrix-pinctrl:
	@HEART_RUN_PI5_PINCTRL_TESTS=1 uv run pytest -n0 tests/device/test_rgb_display_pinctrl_debug.py

install:
	@set -e; \
	if command -v uv >/dev/null 2>&1; then \
		UV_CMD="$$(command -v uv)"; \
	elif [ -n "$(PYTHON)" ]; then \
		echo "uv not found; installing it with $(PYTHON) -m pip --user uv"; \
		"$(PYTHON)" -m pip install --user uv; \
		if command -v uv >/dev/null 2>&1; then \
			UV_CMD="$$(command -v uv)"; \
		else \
			UV_CMD="$(PYTHON) -m uv"; \
		fi; \
	else \
		echo "Error: uv is required and no Python interpreter was found to bootstrap it." >&2; \
		exit 1; \
	fi; \
	echo "Using uv via: $$UV_CMD"; \
	eval "$$UV_CMD sync --all-extras --group dev"; \
	if [ -s "$(TOOL_LIST_FILE)" ]; then \
		for tool in $(TOOLS); do eval "$$UV_CMD tool install $$tool"; done; \
	else \
		echo "Warning: $(TOOL_LIST_FILE) is missing or empty; skipping uv tool installs." >&2; \
	fi

format:
	@uvx isort $(PYTHON_SOURCES)
	@uvx ruff check --fix $(PYTHON_SOURCES)
	@if [ -d "$(DOCS_SOURCES)" ]; then \
		uvx docformatter -i -r --config ./pyproject.toml $(DOCS_SOURCES); \
		uvx mdformat $(DOCS_SOURCES); \
	fi
	# @uv run mypy --config-file pyproject.toml

check:
	@uvx ruff check $(PYTHON_SOURCES)
	@uvx isort --check-only $(PYTHON_SOURCES)
	@if [ -d "$(DOCS_SOURCES)" ]; then \
		uvx docformatter --check -r --config ./pyproject.toml $(DOCS_SOURCES); \
		uvx mdformat --check $(DOCS_SOURCES); \
	fi
	# @uv run mypy --config-file pyproject.toml
	@uv run semgrep ci $(SEMGREP_ARGS) $(SEMGREP_EXTRA_ARGS)

semgrep:
	@uv run semgrep ci $(SEMGREP_ARGS) $(SEMGREP_EXTRA_ARGS)

test:
	@uv run pytest

build: check-harness
	@bash scripts/build_package.sh

build-info:
	@bash scripts/show_build_profile.sh

check-harness:
	@bash scripts/check_harness.sh

doctor:
	@uv run python scripts/devex_snapshot.py

focus:
	@uv run python scripts/devex_focus.py

focus-watch:
	@uv run python scripts/devex_focus.py --watch

dev-session:
	@uv run python scripts/devex_session.py

fractal:
	@UV_CACHE_DIR=.uv-cache uv run python -c "from heart.renderers.three_fractal.renderer import main; main()"

run:
	@FORWARD_TO_BEATS_APP=$(FORWARD_TO_BEATS_APP) BEATS_WEBSOCKET_BIND_HOST=$(BEATS_WEBSOCKET_BIND_HOST) uv run totem run --configuration $(RUN_CONFIGURATION)

debug-gamepad:
	@UV_CACHE_DIR=.uv-cache uv run python scripts/debug/gamepad_probe.py

pi_install:
	@sudo bash packages/heart-device-manager/src/heart_device_manager/install_rgb_matrix.sh
	@sudo uv pip install --system -e '.[native]' --break-system-packages
