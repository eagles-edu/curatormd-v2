# Curator V2 project plugin boundary, version 1

The backend and the repository adapter have separate owners. The Curator V2
global service/store can be shared, but each consumer repository supplies and
owns its `.curatormd-v2.toml` file. The backend repository must not copy a
consumer's source, config, state, inbox, or canonical persistence records.

The strict TOML reader and reference plugin are implemented in
`curatormd_v2.project_config` and `curatormd_v2.project_plugin`. The public
`PROJECT_PLUGIN_API_VERSION` constant is the compatibility value plugins pin
in their repository config; startup fails closed on mismatch. A sample
consumer file is provided at [`examples/curatormd-v2.toml`](examples/curatormd-v2.toml).

## Config contract

```toml
schema_version = 1
backend_api_version = 1
project_id = "example-project"

[scope]
read_paths = ["src", "tests", "docs"]

[checklists]
implementation = "docs/implementation-checklist.md"

[evidence]
adapters = []

[actions]
adapters = []

[staging]
root = ".curatormd-v2/staging"

[persistence]
targets = ["persistence/HISTORY.md"]
```

- Config is bounded to 16 KiB, strict UTF-8 TOML, schema version 1, and rejects
  unknown/missing keys. `backend_api_version` must exactly match the supported
  plugin/backend contract version (currently 1). It must be at the root of a
  Git worktree, have the same owner as the repository root, and not be
  group/world writable; it is opened without following a final symlink and read
  with a fixed byte cap. Recognizable secrets and personal-data patterns in
  config values are rejected without echoing their contents. It
  cannot declare database locations, credentials, arbitrary commands, host
  cleanup, or code to execute.
- When copying the example into a repository, set owner-only permissions with
  `chmod 600 .curatormd-v2.toml`; startup rejects group- or world-writable
  policy files.
- `project_id` is a bounded identifier and is used to bind the plugin service
  to project-scoped goal queries and event processing. It is not authentication.
- `scope.read_paths` and checklist bindings must resolve to existing paths
  within the repository. Checklist IDs must be explicitly mapped and their
  paths must be within read scope.
- Repository inspection is read-only. The optional `actions.adapters` list is
  empty by default; every non-empty adapter ID must also be registered by the
  trusted host at load time. This configuration check does not execute or
  authorize an adapter: no action-execution API is currently exposed by the
  reference plugin, and arbitrary commands or code remain unsupported.
- `evidence.adapters` must be empty or drawn from an adapter registry supplied
  by the host. A name in config does not itself install or trust an adapter.
- `staging.root` must be an existing, non-symlink repository subdirectory.
  The configured purger still deletes only explicitly inventoried regular
  files whose approved hash matches.
- Persistence targets must be Markdown paths beneath existing repository
  directories. `ProjectPlugin.persist_goal(goal_id, target)` requires the
  caller to select one configured target explicitly, revalidates the target,
  and atomically upserts one bounded, deterministic per-goal bullet block.
  Each generated block carries a SHA-256 checksum over its marker-delimited
  contents. This detects accidental/manual edits inside a managed block; it is
  not an authenticity signature against a writer who can recompute the hash.
  Stale checksummed blocks can be advanced from SQLite, exact legacy blocks are
  upgraded only when they match the current projection, and stale legacy or
  checksum-mismatched blocks fail closed without replacement. Unrelated Markdown
  is preserved. Projection does not run automatically on every event or approve SDEs. If
  a receipt has an explicit approve/reject decision and complete artifact
  inventory,
  the plugin records the written target/hash and only then releases that
  receipt's purge gate; failures remain retryable and visible. The current
  library does not authenticate reviewer identity; the review UI/API and its
  authenticated host adapter remain open.

## Reference plugin surface

The `project_storage_usage` read scans at most 10,000 staging-tree entries
using no-follow directory descriptors and metadata only; it never opens file
contents or returns artifact paths. Regular-file byte totals exclude symlinks
and special files. If an entry is skipped, the root changes, permissions fail,
or the scan reaches its bound, the response marks the inventory incomplete and
returns a bounded error code. A completed traversal is a best-effort measurement,
not an immutable snapshot while files are concurrently changing. This
observation is not a purge manifest and never authorizes deletion.
The repository config may additionally set `staging.max_project_bytes` and/or
`staging.max_project_files` as consumer-owned budgets. When either is set, new
staging fails closed if the bounded project scan is incomplete, and writes stop
before crossing the configured limit. `project_storage_usage` reports the
configured limits alongside observed totals and Prometheus metrics. Budgets are
admission controls, not retention rules: existing artifacts are not
automatically deleted, and age-based retention still requires a separate
owner-approved policy.
Staging usage additionally attributes regular-file counts and observed bytes to
the fixed classes `raw-chat`, `cue`, `import`, `scratch`, `generated`,
`duplicate`, or `other`. Attribution uses the path segment immediately beneath
the goal ID; files outside that layout are `other`. Partial scans report only
observed totals and carry `inventory_complete = false`; they are not capacity
certification. Authorized API/MCP storage reads and Prometheus metrics expose
the same bounded class names, never file paths or contents.

The reviewer-only `artifact_inventory_discover(goal_id)` operation returns
exact absolute paths and SHA-256 digests for regular files beneath that goal's
directory, `<staging.root>/<goal_id>/`. Producer adapters must place a goal's
temporary artifacts there; aggregate usage/health scans still cover the full
project staging root. This prevents one goal's review receipt from adopting or
purging another goal's files. A missing goal directory is a complete empty
manifest; a symlink or inaccessible scope is incomplete and cannot authorize
purge. The scanner streams contents in 1 MiB chunks, hashes at most 8 GiB and
500 artifacts per pass, rejects symlinks/special files, detects file changes
during hashing, and marks skipped or over-limit scans incomplete. The returned
packet explicitly carries `scope_goal_id`; the host must show the manifest to
the reviewer. When a caller declares the manifest complete at decision time or
later, the plugin rescans that goal directory and requires an exact current
path/hash match before the backend releases the purge gate; the reviewer
supplies any hold annotation separately and the purger still independently
rechecks each hash before unlinking. A reviewer may mark an
exact manifest entry `legal` or `operational` to retain it. Held entries remain
visible as `held`, are excluded from all retry selectors, and keep the receipt
pending. Hold placement records the SDE reviewer when chosen at decision time;
holds first added while finalizing an incomplete inventory record the
authenticated inventory reviewer. An unchanged hold preserves its original
placement attribution. A hold has no automatic expiry. The plugin exposes an exact
`release_artifact_hold(receipt_id, path, rationale)` operation; the trusted host
must first authorize the dedicated project `retention_hold_release` action, and
the plugin's `ReviewAuthorizer` must authenticate the reviewer. Release actor,
timestamp, and bounded single-line rationale are persisted before eligible
purge resumes. Exact retries are idempotent; a changed actor or rationale
conflicts. The original hold class remains in the audit record. This covers
only the configured tree, not temporary material a producer stored elsewhere.

The local producer surface is `ProjectPlugin.stage_artifact(goal_id,
artifact_class, artifact_id, source)`. It accepts a binary stream, validates
opaque path components and the six temporary classes (`raw-chat`, `cue`,
`import`, `scratch`, `generated`, `duplicate`), and atomically publishes a
no-clobber `0600` file under `<staging.root>/<goal-id>/<class>/`. Partial files
are removed on failure; callers receive only the path and SHA-256, never the
artifact contents. Hard technical ceilings are 64 MiB per file, 256 MiB and
500 files per goal. Writes fail closed if the existing goal inventory is
incomplete. These ceilings are safety bounds, not retention budgets: V2 does
not infer an age policy and does not automatically delete artifacts based on
age or capacity. The supported producer APIs are this local plugin method and
the stdin command below; source-specific integrations and a complete producer
audit remain release gates.
The package also exposes `curatormd-v2-stage` for a local producer process that
cannot import the Python plugin directly. It accepts the project root, global
database, existing goal ID, one of the six artifact classes, and a bounded opaque
artifact ID; bytes are read only from stdin, never from a caller-selected file
path. For example:

```sh
producer-command | curatormd-v2-stage \
  --project-root /path/to/consumer \
  --database /path/to/private/curator-v2.sqlite3 \
  --goal-id goal-123 --artifact-class import --artifact-id import-456
```

The command delegates to the same repository config and plugin validation,
including existing-goal binding, complete-inventory checks, staging locks,
no-clobber publication, and byte/file budgets. Success returns only the staged
path and SHA-256; failure diagnostics do not echo stdin or exception details.
This is a local IPC adapter subject to the operating-system account's trust; it
does not authenticate a remote producer, create a goal or fact, infer SDE
significance, approve review, persist canonical Markdown, or run the purge
scheduler. Each source producer still needs an explicit integration and audit
showing it sends the right temporary material and goal association.
Plugin-managed writes, inventory/finalization, canonical-persistence-triggered
purge, hold release, and pending-purge retry take an exclusive advisory lock on
the configured staging directory. This serializes those operations among
cooperating local plugin instances and prevents a V2 writer's partial file from
being adopted by a concurrent review scan. Direct filesystem writers can
bypass this lock; network-filesystem lock semantics and external producer
coordination are not certified and remain deployment gates.

`ProjectPlugin.bind(config, store, evidence_verifier, review_authorizer)`
creates a service scoped to the configured project and staging root. The review
authorizer must be constructed by the trusted host from its authenticated
request context; the default rejects review decisions. The plugin exposes a
bounded review queue and candidate detail containing only the goal and selected
facts. Its `sde_assess` method accepts up to 32 unique selected facts from the
same goal; routine progress returns no candidate, while other materiality
requires independently verified passing evidence and creates only a pending
proposal. The authenticated API requires project `write` scope for assessment;
review approval remains a separate action. The plugin also provides
project-scoped event processing, goal status/list/children,
checklist ID lookup, configured read-path resolution, goal start from an exact
bound checklist item, explicit user-request intake, accepted child-subtask
intake, and an explicitly invoked scoped Markdown projection. Every goal-intake
adapter requires caller-supplied success criteria and stores them unchanged;
empty criteria are rejected rather than generated from problem text. These
intake adapters create `planned` goals by default. Execution begins only after a
revision-checked `goal_activate` event records an explicit acceptance reason;
an optional caller-provided `next_action` is preserved on the initial goal card
and shown in the bounded report; absent actions remain explicitly unrecorded.
planned goals cannot record implementation or verification facts or finish. A
child is created only when the caller explicitly invokes the child-start adapter
and links to its same-project parent. Goal starts can also link same-project
dependencies. A parent
remains open until its child goals finish; a child remains open while its
dependencies are unfinished. Checklist goal
start requires the exact selected source line; the adapter verifies that line
in the configured file, hashes the bounded file bytes as a `sha256:` source
revision, and stores only that line plus the revision with the goal. Later
source edits do not rewrite the captured snapshot. Event-based checklist starts
are revalidated through the same configured binding before acceptance, and an
already processed event retry remains idempotent after later checklist edits.
The adapter does not infer success criteria or modify source files. Its
read-only `reconcile_goal(goal_id, target)` compares the deterministic SQLite
goal block against the configured Markdown target and returns `synced`,
`missing`, `divergent`, or `malformed` plus hashes. It never chooses a source of
truth or repairs conflicts; callers must keep conflicting state visible until
an owner-approved recovery policy exists. If Markdown replacement succeeds but
the subsequent receipt update is interrupted, rerunning `persist_goal` safely
replays the block, commits the receipt, and only then releases the purge gate;
this recovery boundary is failure-injection tested. Criteria amendments are explicit,
project-scoped events with expected-revision checks; the backend retains each
criteria version and requires fresh evidence after an amendment. A successful canonical projection is
the required precondition for the reviewed receipt's purge attempt. Cross-store
reconciliation, automatic event-to-persist ordering, and plugin installation
lifecycle remain open.

The host must authenticate the caller and select the correct config before
binding the plugin. A project config or project ID is not an authorization
credential. The backend implements a durable project registry and exact
subject/project/action grants; it does not establish the host identity or prove
that a consumer's claimed repository/config fingerprints are trustworthy.
Remaining work is trusted identity and fingerprint binding, trusted evidence
adapter construction, source-producer integrations and their artifact audits,
an approved release/upgrade/rollback lifecycle, and real consumer-runtime
isolation. Local fixture and consumer-checkout probes do not close those
deployment gates. Canonical Markdown projection and purge are deliberately
ordered through a durable receipt gate, not an atomic cross-store transaction;
reconciliation and owner-directed recovery remain necessary if either store
fails between steps.
