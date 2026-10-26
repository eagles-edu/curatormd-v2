# Local Curator V2 evidence sources

Curator V2 can optionally load local service probes, browser proofs, repository
diffs, and exact-commit test runners from a separate host-owned JSON file. This
file is not part of the consuming repository's `.curatormd-v2.toml`; consumer
config cannot select evidence commands, URLs, subjects, or verifier policy.

The host config must be an absolute path to a regular file owned by the
effective OS account running Curator, with no group/world permissions, no
symlink at the final path, one hard link, and at most 16 KiB. Keep it outside
the consumer repository and set mode `0600`:

```sh
chmod 600 /absolute/path/to/curator-evidence.json
```

Example service-probe schema:

```json
{
  "schema_version": 1,
  "project_id": "vhost-manager-alpha",
  "probe": {
    "adapter_id": "vhost-readiness-local",
    "probe_id": "readiness",
    "source_subject": "local-probe:eaglesvn",
    "command": [
      "/usr/bin/curl",
      "--fail",
      "--silent",
      "--max-time",
      "5",
      "https://service.example/healthz"
    ],
    "working_directory": "/absolute/path/to/trusted/working-directory",
    "max_output_bytes": 65536,
    "timeout_seconds": 10
  }
}
```

Capture the configured probe without printing its output:

```sh
curatormd-v2-evidence service-probe \
  --project-root /absolute/path/to/consumer \
  --host-config /absolute/path/to/curator-evidence.json
```

The command emits only `service_probe`, `service-probe:<probe_id>`, the SHA-256
of bounded stdout, and `passed`. The configured verifier reruns the exact probe
and accepts the reference only when the digest still matches; raw probe output
is not returned or persisted.

Add a browser proof to the same file, or configure it by itself:

```json
{
  "schema_version": 1,
  "project_id": "vhost-manager-alpha",
  "browser_proof": {
    "adapter_id": "vhost-home-local",
    "proof_id": "vhost-home",
    "url": "http://127.0.0.1:4310/",
    "executable": "/usr/bin/google-chrome",
    "max_output_bytes": 1048576,
    "timeout_seconds": 20
  }
}
```

Repository evidence can also be enabled in that host file:

```json
{
  "schema_version": 1,
  "project_id": "vhost-manager-alpha",
  "repository_diff": {
    "adapter_id": "vhost-commit-diff",
    "source_subject": "local-git:eaglesvn",
    "repository_root": "/home/eaglesvn/dockerz/renew_ssl",
    "max_diff_bytes": 33554432,
    "timeout_seconds": 30
  },
  "repository_test": {
    "adapter_id": "vhost-unit-tests",
    "runner_id": "vhost-unit-tests",
    "source_subject": "local-git:eaglesvn",
    "repository_root": "/home/eaglesvn/dockerz/renew_ssl",
    "command": ["uv", "run", "--locked", "python", "-m", "unittest", "discover", "-s", "tests"],
    "max_output_bytes": 4194304,
    "timeout_seconds": 300
  }
}
```

For the approved single-user local alpha, an attended human confirmation can
be enabled in the same owner-only host file:

```json
{
  "schema_version": 1,
  "project_id": "vhost-manager-alpha",
  "human_observation": {
    "adapter_id": "vhost-local-reviewer",
    "receipt_directory": "/home/eaglesvn/.local/state/curatormd-v2/human-observations/vhost-manager-alpha",
    "validity_seconds": 900
  }
}
```

Create the receipt directory as the Curator process owner with mode `0700`.
The source subject is derived from the Curator process's effective OS UID; it
cannot be selected in the consumer config or a request. Capture requires a
terminal on both stdin and stderr and a one-time exact confirmation challenge:

```sh
install -d -m 700 /home/eaglesvn/.local/state/curatormd-v2/human-observations/vhost-manager-alpha
curatormd-v2-evidence human-observation \
  --project-root /absolute/path/to/consumer \
  --host-config /absolute/path/to/curator-evidence.json \
  --goal-id GOAL_ID --criterion-id CRITERION_ID
```

The receipt stores only the project, goal and criterion IDs, local UID subject,
passed outcome, and observation/expiry times. It does not store the prompt,
terminal input, chat, or source content. Each reference is scoped to exactly
one goal criterion and expires within 15 minutes. Removing its exact receipt
file revokes it; missing, changed, expired, or cross-scope receipts fail
verification. This authenticates only the attended local OS account for the
single-user development alpha. It does not prove a Hermes human identity,
deployment trust root, or remote review authority, so the deployment trust and
identity gates remain open.

Repository roots must be absolute Git worktree roots. The diff resolver accepts
only full commit IDs and hashes the binary diff without returning its contents.
The test runner checks out the exact commit into a temporary directory, invokes
the configured argument array without a shell, and hashes bounded combined
output without retaining it. Use the host-owned capture commands to produce the
corresponding references:

```sh
curatormd-v2-evidence repository-diff \
  --project-root /absolute/path/to/consumer \
  --host-config /absolute/path/to/curator-evidence.json \
  --base FULL_BASE_COMMIT --head FULL_HEAD_COMMIT

curatormd-v2-evidence repository-test \
  --project-root /absolute/path/to/consumer \
  --host-config /absolute/path/to/curator-evidence.json \
  --runner vhost-unit-tests --commit FULL_COMMIT
```

The diff locator is `git-diff:<base>..<head>`; the test locator is
`git-test:<runner-id>:<commit>`. The printed object contains only the evidence
kind, locator, digest, and pass outcome. Verification reruns the configured
test command and requires the same digest.

Browser URLs must be credential-free `http` or `https` loopback URLs without
query strings or fragments. Chrome runs as the Curator process owner with a
fresh temporary profile, a 30-second maximum timeout, and a 1 MiB maximum DOM
output. The resolver streams the DOM into a SHA-256 digest and returns only an
opaque locator, digest, and outcome; it does not save or print page content.
Capture a reference for the configured project with:

```sh
curatormd-v2-evidence browser \
  --project-root /absolute/path/to/consumer \
  --host-config /absolute/path/to/curator-evidence.json
```

The capture command prints one compact JSON `EvidenceRef`. The corresponding
host verifier rerenders the exact configured URL and requires the DOM digest
to match; a changed page fails verification. The attested subject is the
launching OS UID. Chrome's temporary profile does not contain a signed-in
session, so this path does not establish authenticated web identity or prove
content requiring an existing browser login.

Configure the local stdio launcher with the host file path:

```sh
curatormd-v2-mcp \
  --project-root /absolute/path/to/consumer \
  --database /absolute/path/to/private/curator.sqlite3 \
  --profile-id renew-ssl-coding \
  --evidence-config /absolute/path/to/curator-evidence.json
```

The project ID in the file must exactly match the bound consumer project. The
probe command is a fixed argv executed without a shell, with closed stdin,
discarded stderr, a minimal environment, a maximum 30-second runtime, and no
more than 64 KiB of stdout. Only the stdout digest is retained. A zero exit
with nonempty output is required. `EvidenceRef.sha256` must match the digest
observed by the probe. The evidence locator must be exactly
`service-probe:<probe_id>`.

Treat this file as executable host configuration: each command runs with the
same OS account as the Curator process. Only place commands here that the
operator explicitly trusts.

Repository subjects use the `local-git:` namespace. This records a local host
assertion about the worktree and runner; it does not authenticate a Git hosting
provider, hosted CI runner, or human author. Keep provider credentials, trust
roots, and deployed rotation/revocation evidence as separate release gates.

`source_subject` must use the `local-probe:` namespace. It is a configured
local host assertion; it is not a Hermes-authenticated person, remote service
identity, credential, revocation source, or production trust root. Do not put
credentials in command arguments. The verifier rejects malformed, duplicate,
oversized, cross-project, or broadly readable configuration and remains
reject-all when the option is omitted. The browser's local UID assertion and
loopback restriction are also host-local controls, not authenticated browser
identity or a deployment trust root. These local alpha paths do not establish
deployment identity, production service authentication, or live runtime
readiness.
