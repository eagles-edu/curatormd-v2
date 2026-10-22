# Local Curator V2 service probes

Curator V2 can optionally load one local service probe from a separate
host-owned JSON file. This file is not part of the consuming repository's
`.curatormd-v2.toml`; consumer config cannot select evidence commands,
subjects, or verifier policy.

The host config must be an absolute path to a regular file owned by the
effective OS account running Curator, with no group/world permissions, no
symlink at the final path, one hard link, and at most 16 KiB. Keep it outside
the consumer repository and set mode `0600`:

```sh
chmod 600 /absolute/path/to/curator-evidence.json
```

Example schema:

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
reject-all when the option is omitted. This local alpha path does not establish
deployment identity, production service authentication, or live runtime
readiness.
