dev_install:
	@pip install -e ".[dev]"

format: dev_install
	@black src
	@isort src
	@docformatter -i -r --config ./pyproject.toml --black .
	@mdformat .

test: dev_install
	@pytest test