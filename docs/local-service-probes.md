# Local Curator V2 evidence sources

Curator V2 can optionally load local service probes, browser proofs, or both
from a separate host-owned JSON file. This file is not part of the consuming
repository's `.curatormd-v2.toml`; consumer config cannot select evidence
commands, URLs, subjects, or verifier policy.

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
