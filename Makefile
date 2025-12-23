PYTHON_SOURCES = src tests
DOCS_SOURCES = docs
TOOL_LIST_FILE = scripts/harness_tools.txt
TOOLS := $(shell scripts/list_harness_tools.sh $(TOOL_LIST_FILE))
BUILD_ARGS ?=
.PHONY: install pi_install format check test build check-harness

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
	@uv run mypy --config-file pyproject.toml

check:
	@uvx ruff check $(PYTHON_SOURCES)
	@uvx isort --check-only $(PYTHON_SOURCES)
	@uvx docformatter --check -r --config ./pyproject.toml $(DOCS_SOURCES)
	@uvx mdformat --check $(DOCS_SOURCES)
	@uv run mypy --config-file pyproject.toml

test:
	@uv run pytest

build: check-harness
	@uv build $(BUILD_ARGS)

check-harness:
	@bash scripts/check_harness.sh

pi_install:
	@sudo bash src/heart/manage/install_rgb_matrix.sh
	@sudo uv pip install --system -e . --break-system-packages
