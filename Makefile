PYTHON_SOURCES = src scripts test
DEV_INSTALL_STAMP = .dev_install.stamp

.PHONY: pi_install format lint check test clean-dev-install ensure-dev-install

dev_install: $(DEV_INSTALL_STAMP)

$(DEV_INSTALL_STAMP):
	@uv pip install --system -e ".[dev]"
	@uvx pre-commit install --hook-type pre-commit --hook-type pre-push
	@touch $(DEV_INSTALL_STAMP)

clean-dev-install:
	@rm -f $(DEV_INSTALL_STAMP)

pi_install:
	@sudo bash src/heart/manage/install_rgb_matrix.sh
	@sudo uv pip install --system -e . --break-system-packages

format: ensure-dev-install
	@uvx ruff check $(PYTHON_SOURCES) --fix
	@uvx isort $(PYTHON_SOURCES)
	@uvx black $(PYTHON_SOURCES)
	@uvx docformatter -i -r --config ./pyproject.toml --black $(PYTHON_SOURCES)
	@uvx mdformat .

lint: ensure-dev-install
	@uvx ruff check $(PYTHON_SOURCES)

check: lint
	@uvx isort --check-only $(PYTHON_SOURCES)
	@uvx black --check $(PYTHON_SOURCES)
	@uvx docformatter --check -r --config ./pyproject.toml --black $(PYTHON_SOURCES)
	@uvx mdformat --check .

test: ensure-dev-install
	@uvx pytest test

ensure-dev-install:
	@$(MAKE) --no-print-directory dev_install \
	|| (echo "Warning: dev_install failed; continuing without reinstalling dev dependencies." && true)
