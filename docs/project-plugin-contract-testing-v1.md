# Curator V2 project-plugin contract testing, version 1

`curatormd_v2.testing.assert_goal_started_event_contract` is a reusable
assertion helper for a consumer repository's producer/backend tests. The module
ships with the Curator V2 backend package and depends only on the package's
public event and plugin contracts.

A consumer test can pass its configured project plugin and a representative
producer event:

```python
from curatormd_v2.testing import assert_goal_started_event_contract


def test_producer_goal_started_contract(project_plugin, goal_started_event):
    evidence = assert_goal_started_event_contract(
        project_plugin,
        goal_started_event,
        expected_project_id="example-project",
    )
    assert evidence.event_id == goal_started_event.event_id
```

The helper checks that the event survives canonical JSON serialization,
processes successfully, returns the same durable receipt on exact replay,
persists the supplied `goal.started` fields inside the expected project, and
retains zero event-payload bytes. It returns only bounded identifiers, the
payload hash, and byte totals.

The helper does not create the consumer plugin, prove that a producer routes
all events to it, verify repository allowlists or checklist ownership, or prove
Hermes/runtime delivery. Consumer suites must keep those checks alongside the
shared assertion. This repository exercises the helper against the reference
plugin in `tests/test_project_plugin.py`; no consumer repository has run this
helper as part of this change.
