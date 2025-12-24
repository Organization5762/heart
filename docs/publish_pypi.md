# Publish the package to PyPI

Use the repository publish script when you need to upload a release build to PyPI
or TestPyPI. The script builds the package with `scripts/build_package.sh` and
uploads the resulting artifacts with `twine` via `uv tool run`.

## Materials

- A PyPI API token or an existing `~/.pypirc` configuration.
- `uv` installed locally.
- Access to the Heart repository checkout.

## Publish to PyPI

1. Export credentials for PyPI (or configure `~/.pypirc`):

   ```bash
   export PYPI_TOKEN="<token>"
   ```

1. Run the publish script:

   ```bash
   scripts/publish_pypi.sh
   ```

## Publish to TestPyPI

1. Export a TestPyPI token and repository URL:

   ```bash
   export PYPI_TOKEN="<test-token>"
   export PYPI_REPOSITORY_URL="https://test.pypi.org/legacy/"
   ```

1. Run the publish script:

   ```bash
   scripts/publish_pypi.sh
   ```

## Environment variables

| Variable | Description |
| --- | --- |
| `PYPI_TOKEN` | Token used when authenticating as `__token__`. |
| `PYPI_REPOSITORY_URL` | Override the repository URL (for example, TestPyPI). |
| `PYPI_REPOSITORY` | Named repository in `~/.pypirc` to target. |
| `DIST_DIR` | Override the `dist/` directory path. |
| `TWINE_USERNAME` | Custom username for `twine` when not using a token. |
| `TWINE_PASSWORD` | Custom password for `twine` when not using a token. |

## Notes

- The script expects build artifacts at `dist/*.whl` and `dist/*.tar.gz`.
- Keep tokens out of shell history by using a password manager or a scoped
  environment file.
