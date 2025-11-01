PYTHON_SOURCES = src scripts test
DEV_INSTALL_STAMP = .dev_install.stamp

.PHONY: pi_install format lint check test clean-dev-install

dev_install: $(DEV_INSTALL_STAMP)

$(DEV_INSTALL_STAMP):
	@pip install -e ".[dev]"
	@pre-commit install --hook-type pre-commit --hook-type pre-push
	@touch $(DEV_INSTALL_STAMP)

clean-dev-install:
	@rm -f $(DEV_INSTALL_STAMP)

pi_install:
	@sudo bash src/heart/manage/install_rgb_matrix.sh
	@sudo pip install -e . --break-system-packages

format: $(DEV_INSTALL_STAMP)
	@ruff check $(PYTHON_SOURCES) --fix
	@isort $(PYTHON_SOURCES)
	@black $(PYTHON_SOURCES)
	@docformatter -i -r --config ./pyproject.toml --black $(PYTHON_SOURCES)
	@mdformat .

lint: $(DEV_INSTALL_STAMP)
	@ruff check $(PYTHON_SOURCES)

check: lint
	@isort --check-only $(PYTHON_SOURCES)
	@black --check $(PYTHON_SOURCES)
	@docformatter --check -r --config ./pyproject.toml --black $(PYTHON_SOURCES)
	@mdformat --check .

test: $(DEV_INSTALL_STAMP)
	@pytest test
