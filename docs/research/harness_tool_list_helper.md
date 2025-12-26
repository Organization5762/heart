# Harness tool list helper for build and harness checks

## Materials

- `scripts/harness_tools.txt`
- `scripts/list_harness_tools.sh`
- `scripts/check_harness.sh`
- `Makefile`
- `docs/library/tooling_and_configuration.md`

## Note

The build and harness helpers each parsed the tool list independently, which made
inline comments and whitespace handling inconsistent between `make install` and
`scripts/check_harness.sh`. This update adds a shared helper script to normalize
tool list parsing, and the harness check now warns if the list contains duplicate
entries. These guardrails reduce drift between build steps and harness checks
without changing the tool inventory itself.
