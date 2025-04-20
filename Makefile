dev_install:
	@pip install -e ".[dev]"
	@pre-commit install --hook-type pre-push

format: dev_install
	@black src
	@isort src
	@docformatter -i -r --config ./pyproject.toml --black .
	@mdformat .

check: dev_install
	@black --check src
	@isort --check-only src
	@docformatter --check -r --config ./pyproject.toml --black .
	@mdformat --check .

test: dev_install
	@pytest test