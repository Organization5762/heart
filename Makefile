dev_install:
	@pip install -e ".[dev]"
	@pre-commit install --hook-type pre-push

pi_install:
	@sudo bash src/heart/manage/install_rgb_matrix.sh
	@sudo pip install -e . --break-system-packages

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