# Curator V2

Fresh implementation scaffold for the goal-ledger CuratorMD design. The
existing CuratorMD repository remains separate; this repository does not copy
its runtime state, inbox, transcripts, or project records.

## Proposed ownership

- This repository: global event/goal/fact backend and reusable contracts.
- Each consumer repository: its own CuratorMD plugin and repository-specific
  configuration.
- Hermes Core: runtime, global event routing, and Host Steward. Host Steward
  is outside CuratorMD's ownership boundary.

## Architecture sources

- [`docs/curator-v2-plan.md`](docs/curator-v2-plan.md) — lifecycle, behavior,
  tests, and cutover constraints.
- [`docs/diagrams/inkscape-curator-v2-hermes-core.svg`](docs/diagrams/inkscape-curator-v2-hermes-core.svg)
  — detailed bounded-system landscape.

## Development

Python 3.12+ is the initial implementation language. Run the standard-library
test suite from the repository root with:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
```

This is an architecture and package scaffold, not a functioning Curator
service yet.
