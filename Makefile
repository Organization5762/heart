PYTHON_SOURCES = src scripts test

.PHONY: dev_install pi_install format lint check test

dev_install:
	@pip install -e ".[dev]"
	@pre-commit install --hook-type pre-push

pi_install:
	@sudo bash src/heart/manage/install_rgb_matrix.sh
	@sudo pip install -e . --break-system-packages

format: dev_install
	@ruff check $(PYTHON_SOURCES) --fix
	@isort $(PYTHON_SOURCES)
	@black $(PYTHON_SOURCES)
	@docformatter -i -r --config ./pyproject.toml --black $(PYTHON_SOURCES)
	@mdformat .

lint:
	@ruff check $(PYTHON_SOURCES)

check: lint
	@isort --check-only $(PYTHON_SOURCES)
	@black --check $(PYTHON_SOURCES)
	@docformatter --check -r --config ./pyproject.toml --black $(PYTHON_SOURCES)
	@mdformat --check .

test: dev_install
	@pytest test
