format:
	@pip install -e ".[dev]"
	@black src
	@isort src
	@docformatter -i -r --config ./pyproject.toml --black .
	@mdformat .

test:
	@pip install -e ".[dev]"
	@pytest test