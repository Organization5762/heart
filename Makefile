start:
	@python3 src/heart/display/loop.py

format:
	@@pip install --upgrade docformatter[tomli] isort black mdformat
	@black src
	@isort src
	@docformatter -i -r --config ./pyproject.toml --black .
	@mdformat .