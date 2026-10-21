# Curator V2 CI policy

The required GitHub Actions workflow is `.github/workflows/ci.yml`. It is a
verification gate only: it does not deploy, publish packages, connect to
consumer repositories, or access production credentials.

## Blocking checks

- A separate packaging job builds the wheel, installs it into a clean Python
  environment, exercises the installed stdio launcher against a temporary
  consumer repository/config and runs all installed operational CLI
  entrypoints, including the attended local SDE reviewer. The storage CLI smoke
  takes and restores an integrity-checked snapshot to a new path, then verifies
  the restored row. These checks do not
  add the source tree to `PYTHONPATH`; they verify the built distribution
  rather than an editable checkout. They remain fixture-consumer checks, not
  installation in a production repository or Hermes identity proof.
- Unit tests run with the locked dependency graph on Python 3.12, 3.13, and
  3.14, matching the declared `>=3.12,<4` interpreter range for the current
  supported release line.
- Pyright runs in strict mode over `src/` and `tests/`.
- Pylint treats descriptive `test_*` names as documentation for individual test
  methods; production functions and non-test helpers still require docstrings.
- Pylint errors (`E` and fatal `F` classes) block CI. Existing convention,
  refactor, and warning-class findings are not represented as resolved by this
  focused gate; repository-wide Pylint cleanup remains a separate open plan
  item.
- Bandit scans the shipped `src/curatormd_v2` package. A finding blocks CI and
  must be fixed or addressed through a reviewed, narrowly scoped suppression
  with rationale and regression coverage.
- `uv audit --locked --preview-features audit-command` checks the complete
  `uv.lock` graph, including optional and development groups, for known
  vulnerabilities and adverse package statuses. The [uv audit command][uv-audit]
  is currently experimental ([Astral announcement][uv-audit-announcement]); CI
  pins uv exactly so behavior changes require a reviewed tool upgrade. An
  unfixed known vulnerability blocks CI. The owner must update to a
  non-vulnerable release or record a time-bounded exception with affected
  package/version, advisory, exposure rationale, compensating control, owner,
  and expiry; do not add a blanket ignore.

The lockfile is authoritative in CI: `uv sync --locked` fails if project
metadata and `uv.lock` disagree. Python quality/security tool versions and the
uv executable version are exact-pinned. GitHub Actions are pinned to reviewed
commit SHAs; a version update must review upstream changes and rerun the full
workflow. The workflow has read-only repository permissions and checkout does
not persist its token.

## Reviewed tool pins

| Tool | Pin | Purpose |
| --- | --- | --- |
| uv | `0.12.18` | Locked dependency resolution and execution |
| Pyright | `1.1.414` | Strict static typing |
| Pylint | `4.1.3` | Blocking error/fatal diagnostics |
| Bandit | `1.9.4` | Python source security rules |
| uv audit | `0.12.18` | Full lockfile vulnerability/adverse-status scan |

Package pins are declared in `pyproject.toml` and fully resolved in `uv.lock`.
The workflow references `actions/checkout` v7.0.0 at
`9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0`, `actions/setup-python` v6.3.0 at
`ece7cb06caefa5fff74198d8649806c4678c61a1`, and `astral-sh/setup-uv` v9.0.0 at
`c771a70e6277c0a99b617c7a806ffedaca235ff9`.

## Local reproduction

```sh
uv sync --locked --group test --group quality
uv run --locked --group test python -m unittest discover -s tests -v
uv run --locked --group quality pyright
uv run --locked --group quality pylint --errors-only src/curatormd_v2 tests
uv run --locked --group quality bandit -q -r src/curatormd_v2
uv audit --locked --preview-features audit-command
```

[uv-audit]: https://docs.astral.sh/uv/reference/cli/#uv-audit
[uv-audit-announcement]: https://astral.sh/blog/uv-audit

Dependency auditing requires access to the vulnerability database. Network or
database unavailability is a failed check, not evidence that dependencies are
safe. Do not convert scanner outages or unresolved findings into a passing
status by disabling the job.
