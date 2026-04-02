PYTHON_SOURCES = packages src tests
DOCS_SOURCES = docs
TOOL_LIST_FILE = scripts/harness_tools.txt
TOOLS := $(shell scripts/list_harness_tools.sh $(TOOL_LIST_FILE))
BUILD_ARGS ?=
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
.PHONY: install bootstrap-native debug-matrix-pinctrl test-matrix-pinctrl pi_install format check semgrep test build check-harness build-info doctor focus focus-watch dev-session

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
	@uv sync --all-extras --group dev
	@if [ -s "$(TOOL_LIST_FILE)" ]; then \
		for tool in $(TOOLS); do uv tool install $$tool; done; \
	else \
		echo "Warning: $(TOOL_LIST_FILE) is missing or empty; skipping uv tool installs." >&2; \
	fi

format:
	@uvx isort $(PYTHON_SOURCES)
	@uvx ruff check --fix $(PYTHON_SOURCES)
	@uvx docformatter -i -r --config ./pyproject.toml $(DOCS_SOURCES)
	@uvx mdformat $(DOCS_SOURCES)
	# @uv run mypy --config-file pyproject.toml

check:
	@uvx ruff check $(PYTHON_SOURCES)
	@uvx isort --check-only $(PYTHON_SOURCES)
	@uvx docformatter --check -r --config ./pyproject.toml $(DOCS_SOURCES)
	@uvx mdformat --check $(DOCS_SOURCES)
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

pi_install:
	@sudo bash packages/heart-device-manager/src/heart_device_manager/install_rgb_matrix.sh
	@sudo uv pip install --system -e '.[native]' --break-system-packages
