PYTHON_SOURCES = src tests
DOCS_SOURCES = docs
.PHONY: pi_install format check test

format:
	@uvx isort $(PYTHON_SOURCES)
	@uvx ruff check --fix
	@uvx docformatter -i -r --config ./pyproject.toml $(DOCS_SOURCES)
	@uvx mdformat $(DOCS_SOURCES)

check:
	@uvx ruff check $(PYTHON_SOURCES)
	@uvx isort --check-only $(PYTHON_SOURCES)
	@uvx docformatter --check -r --config ./pyproject.toml $(DOCS_SOURCES)
	@uvx mdformat --check $(DOCS_SOURCES)

test:
	@uv run pytest

pi_install:
	@sudo bash src/heart/manage/install_rgb_matrix.sh
	@sudo uv pip install --system -e . --break-system-packages
