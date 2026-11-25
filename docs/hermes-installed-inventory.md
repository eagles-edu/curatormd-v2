# Hermes installed inventory + disk footprint

Generated: 2026-11-14 12:28:55 +07

Listed tools directories total: **2398.1 MiB** allocated. Listed environment directories total: **1898.7 MiB** allocated. These are directory-scan estimates and may overlap via hard links.
Disk figures are allocated bytes (st_blocks), shown in MiB; directory totals deduplicate hard links within each item. Python distribution sizes use files recorded for each distribution; shared files may be attributed to more than one package. No per-item execution counts are persisted; atime is recency only, not frequency. Do not manually delete managed installs or environments.

## Tools

| Installed item | Disk MiB | Last access (atime) | Use | Cullability opinion |
|---|---:|---|---|---|
| `.reclaim-07ad65ce3b5d46809f4ff47c1b73558d` | 84.8 | 2026-11-13 15:49 | Reclaim/staging data | Candidate for Hermes-managed GC only; confirm unreferenced/live-use state. |
| `.reclaim-37d1e6587c844736882e9ab475641477` | 134.7 | 2026-11-13 15:49 | Reclaim/staging data | Candidate for Hermes-managed GC only; confirm unreferenced/live-use state. |
| `agent-browser-0.26.0-linux-x64` | 10.8 | 2026-11-14 04:58 | Browser automation | Keep if browser automation is used; check PM refs before removal. |
| `chromium-1208` | 363.2 | 2026-11-13 22:57 | Browser binary | Keep if browser automation is used; verify paired browser/tool references first. |
| `cua-driver-0.21.0-linux-x64` | 86.4 | 2026-11-13 15:51 | Computer-use input driver | Keep if computer-use is enabled. |
| `ffmpeg-9.0.1-linux-x64` | 437.5 | 2026-11-13 14:11 | Audio/video processing | Keep if audio/video/voice features are used. |
| `just-1.59.0-linux-x64` | 6.4 | 2026-11-13 19:27 | Command runner | Optional; likely removable only if no scripts invoke it. |
| `node-26.12.1-linux-x64` | 225.0 | 2026-11-14 12:17 | JavaScript runtime | Duplicate version: review older version only after checking PM references/live processes. |
| `node-26.7.0-linux-x64` | 222.3 | 2026-11-14 12:07 | JavaScript runtime | Duplicate version: review older version only after checking PM references/live processes. |
| `npm-12.0.2-linux-x64` | 16.9 | 2026-11-13 15:49 | Node package manager | Keep if Node workflows need it; may be redundant if pnpm is sole manager. |
| `pnpm-12.15.0-linux-x64` | 60.1 | 2026-11-14 04:34 | Node package manager | Optional if no JS projects/tools depend on it. |
| `python-3.14.7+20260901-linux-x64` | 396.6 | 2026-11-14 12:08 | Python runtime | Duplicate version: retain the runtime referenced by Hermes; managed GC only. |
| `python-3.14.9+20261021-linux-x64` | 257.9 | 2026-11-14 12:06 | Python runtime | Duplicate version: retain the runtime referenced by Hermes; managed GC only. |
| `ripgrep-15.2.0-linux-x64` | 5.5 | 2026-11-13 15:49 | Fast text search | Optional only if no tools/scripts depend on `rg`. |
| `uv-0.12.3-linux-x64` | 53.7 | 2026-11-14 12:08 | Python package/environment manager | Duplicate version: review older version only after checking PM references/live processes. |
| `uv-0.13.5-linux-x64` | 36.2 | 2026-11-14 12:06 | Python package/environment manager | Duplicate version: review older version only after checking PM references/live processes. |

Tool-tree subtotal (listed directories): **2398.1 MiB**. This sums directory allocations and may double-count shared inodes across directories.

## Python environments

### `10b814a3f5b84461900cb56c713626f1` — 888.7 MiB total; 129 distributions

Opinion: treat the entire env as a unit. Do not uninstall individual dependencies or delete the directory manually; first establish whether the install manager/lease still references it, then use its supported GC path.

| Distribution | Version | Attributed MiB | Cullability opinion |
|---|---:|---:|---|
| `agent-client-protocol` | 0.9.0 | 0.37 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `aiohappyeyeballs` | 2.7.1 | 0.07 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `aiohttp` | 3.14.5 | 6.84 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `aiosignal` | 1.4.0 | 0.04 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `annotated-doc` | 0.0.5 | 0.04 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `annotated-types` | 0.8.0 | 0.05 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `anyio` | 4.15.1 | 0.62 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `attrs` | 26.1.0 | 0.32 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `av` | 18.1.0 | 101.79 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `boto3` | 1.43.115 | 1.07 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `botocore` | 1.43.115 | 25.13 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `browser-harness` | 0.1.13 | 0.40 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `cdp-use` | 1.4.5 | 2.01 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `certifi` | 2026.10.19 | 0.27 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `cffi` | 2.1.1 | 0.77 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `charset-normalizer` | 3.5.2 | 0.78 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `click` | 8.5.0 | 0.48 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `croniter` | 6.2.4 | 0.27 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `cryptography` | 50.0.2 | 14.62 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `ctranslate2` | 4.8.3 | 136.02 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `defusedxml` | 0.7.1 | 0.11 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `distro` | 1.9.0 | 0.10 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `edge-tts` | 7.3.1 | 0.17 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `fastapi` | 0.133.1 | 0.84 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `faster-whisper` | 1.2.1 | 1.36 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `fetch-use` | 0.4.0 | 0.04 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `filelock` | 4.2.6 | 0.62 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `fire` | 0.7.1 | 0.47 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `firecrawl-anydoc` | 0.2.4 | 8.02 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `flatbuffers` | 25.12.19 | 0.12 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `frozenlist` | 1.8.0 | 0.78 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `fsspec` | 2026.9.0 | 0.91 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `google-api-core` | 2.42.0 | 0.88 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `google-api-python-client` | 2.201.0 | 108.29 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `google-auth` | 2.62.0 | 1.08 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `google-auth-httplib2` | 0.4.4 | 0.04 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `google-auth-oauthlib` | 1.5.0 | 0.09 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `google-cloud-pubsub` | 2.43.0 | 2.02 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `googleapis-common-protos` | 1.75.5 | 1.12 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `grpc-google-iam-v1` | 0.14.5 | 0.14 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `grpcio` | 1.84.0 | 17.23 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `grpcio-status` | 1.84.0 | 0.07 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `h11` | 0.16.0 | 0.15 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `hermes-agent` | 0.0.0 | 0.11 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `hf-xet` | 1.7.0 | 11.06 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `httpcore` | 1.0.9 | 0.36 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `httpcore2` | 2.15.1 | 0.36 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `httplib2` | 0.32.0 | 0.25 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `httptools` | 0.8.0 | 1.60 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `httpx` | 0.28.1 | 0.35 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `httpx2` | 2.15.1 | 0.47 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `huggingface_hub` | 1.33.0 | 3.57 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `idna` | 3.20 | 0.37 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `Jinja2` | 3.1.6 | 0.54 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `jiter` | 0.17.0 | 0.79 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `jmespath` | 1.1.0 | 0.11 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `jsonschema` | 4.26.0 | 0.55 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `jsonschema-specifications` | 2025.9.1 | 0.12 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `Markdown` | 3.11.2 | 0.43 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `markdown-it-py` | 4.2.0 | 0.41 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `MarkupSafe` | 3.0.4 | 0.10 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `mcp` | 2.3.0 | 1.46 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `mcp-types` | 2.3.0 | 0.37 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `mdurl` | 0.1.2 | 0.05 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `multidict` | 6.9.1 | 1.17 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `nemo-relay` | 0.11.0 | 27.03 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `numpy` | 2.5.4 | 56.01 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `oauthlib` | 4.0.0 | 0.69 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `onnxruntime` | 1.31.0 | 62.23 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `openai` | 2.54.0 | 10.36 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `opentelemetry-api` | 1.45.1 | 0.27 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `opentelemetry-sdk` | 1.45.1 | 0.65 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `opentelemetry-semantic-conventions` | 0.66b1 | 1.04 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `packaging` | 26.3 | 0.54 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `pathspec` | 1.1.1 | 0.24 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `pillow` | 13.0.0 | 19.75 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `pillow_heif` | 1.8.1 | 26.09 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `prompt_toolkit` | 3.0.53 | 1.66 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `propcache` | 0.5.4 | 0.81 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `proto-plus` | 1.29.0 | 0.20 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `protobuf` | 6.33.6 | 1.38 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `psutil` | 7.2.2 | 0.53 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `ptyprocess` | 0.7.0 | 0.06 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `pyasn1` | 0.6.5 | 0.47 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `pyasn1_modules` | 0.4.2 | 1.02 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `pycparser` | 3.11 | 0.24 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `pydantic` | 2.14.1 | 2.12 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `pydantic_core` | 2.50.1 | 5.00 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `Pygments` | 2.21.0 | 5.06 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `PyJWT` | 2.15.1 | 0.16 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `pyparsing` | 3.3.3 | 0.51 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `python-dateutil` | 2.9.0.post0 | 0.50 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `python-dotenv` | 1.2.4 | 0.11 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `python-multipart` | 0.0.32 | 0.14 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `PyYAML` | 6.0.3 | 2.77 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `referencing` | 0.37.0 | 0.16 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `requests` | 2.34.2 | 0.29 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `requests-oauthlib` | 2.0.0 | 0.12 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `resvg_py` | 0.5.0 | 2.97 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `rich` | 14.3.4 | 1.41 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `rpds-py` | 2026.9.1 | 1.05 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `ruamel.yaml` | 0.18.16 | 0.62 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `ruamel.yaml.clib` | 0.2.15 | 2.62 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `s3transfer` | 0.19.3 | 0.38 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `six` | 1.17.0 | 0.06 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `sniffio` | 1.3.1 | 0.05 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `snowballstemmer` | 3.1.1 | 0.84 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `socksio` | 1.0.0 | 0.06 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `sounddevice` | 0.5.6 | 0.15 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `sse-starlette` | 3.5.0 | 0.07 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `starlette` | 1.9.0 | 0.36 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `tabulate` | 0.10.0 | 0.17 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `tenacity` | 9.2.1 | 0.14 | Optional-looking dependency; verify project/import references before removing (prefer env rebuild). |
| `termcolor` | 3.3.0 | 0.04 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `tokenizers` | 0.23.3 | 11.24 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `tomli_w` | 1.2.0 | 0.04 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `tqdm` | 4.70.1 | 0.33 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `truststore` | 0.10.5 | 0.09 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `typing-inspection` | 0.4.4 | 0.07 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `typing_extensions` | 4.16.0 | 0.19 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `uritemplate` | 4.2.0 | 0.06 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `urllib3` | 2.8.0 | 0.53 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `uvicorn` | 0.54.0 | 0.40 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `uvloop` | 0.23.0 | 15.60 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `watchfiles` | 1.3.0 | 1.24 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `wcwidth` | 0.9.2 | 3.50 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `websockets` | 15.0.1 | 0.73 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `yarl` | 1.25.1 | 0.40 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `youtube-transcript-api` | 1.2.4 | 2.18 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |

### `6d13d213dc3542939482d102ba8b1603` — 1010.0 MiB total; 133 distributions

Opinion: treat the entire env as a unit. Do not uninstall individual dependencies or delete the directory manually; first establish whether the install manager/lease still references it, then use its supported GC path.

| Distribution | Version | Attributed MiB | Cullability opinion |
|---|---:|---:|---|
| `agent-client-protocol` | 0.9.0 | 0.37 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `aiohappyeyeballs` | 2.7.1 | 0.07 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `aiohttp` | 3.14.5 | 6.84 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `aiosignal` | 1.4.0 | 0.04 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `annotated-doc` | 0.0.5 | 0.04 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `annotated-types` | 0.8.0 | 0.05 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `anyio` | 4.15.1 | 0.62 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `attrs` | 26.1.0 | 0.32 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `av` | 18.1.0 | 101.79 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `boto3` | 1.43.115 | 1.07 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `botocore` | 1.43.115 | 25.13 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `browser-harness` | 0.1.13 | 0.40 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `cdp-use` | 1.4.5 | 2.01 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `certifi` | 2026.10.19 | 0.27 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `cffi` | 2.1.1 | 0.77 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `charset-normalizer` | 3.5.2 | 0.78 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `click` | 8.5.0 | 0.48 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `croniter` | 6.2.4 | 0.27 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `cryptography` | 50.0.2 | 14.62 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `ctranslate2` | 4.8.3 | 136.02 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `defusedxml` | 0.7.1 | 0.11 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `distro` | 1.9.0 | 0.10 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `edge-tts` | 7.3.1 | 0.17 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `fastapi` | 0.133.1 | 0.84 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `faster-whisper` | 1.2.1 | 1.36 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `fetch-use` | 0.4.0 | 0.04 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `filelock` | 4.2.6 | 0.62 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `fire` | 0.7.1 | 0.47 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `firecrawl-anydoc` | 0.2.4 | 8.02 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `flatbuffers` | 25.12.19 | 0.12 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `frozenlist` | 1.8.0 | 0.78 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `fsspec` | 2026.9.0 | 0.91 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `google-api-core` | 2.42.0 | 0.88 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `google-api-python-client` | 2.201.0 | 108.29 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `google-auth` | 2.62.0 | 1.08 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `google-auth-httplib2` | 0.4.4 | 0.04 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `google-auth-oauthlib` | 1.5.0 | 0.09 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `google-cloud-pubsub` | 2.43.0 | 2.02 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `googleapis-common-protos` | 1.75.5 | 1.12 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `grpc-google-iam-v1` | 0.14.5 | 0.14 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `grpcio` | 1.84.0 | 17.23 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `grpcio-status` | 1.84.0 | 0.07 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `h11` | 0.16.0 | 0.15 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `hermes-agent` | 0.0.0 | 0.11 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `hf-xet` | 1.7.0 | 11.06 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `httpcore` | 1.0.9 | 0.36 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `httpcore2` | 2.15.1 | 0.36 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `httplib2` | 0.32.0 | 0.25 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `httptools` | 0.8.0 | 1.60 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `httpx` | 0.28.1 | 0.35 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `httpx2` | 2.15.1 | 0.47 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `huggingface_hub` | 1.33.0 | 3.57 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `idna` | 3.20 | 0.37 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `Jinja2` | 3.1.6 | 0.54 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `jiter` | 0.17.0 | 0.79 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `jmespath` | 1.1.0 | 0.11 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `jsonschema` | 4.26.0 | 0.55 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `jsonschema-specifications` | 2025.9.1 | 0.12 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `lark-oapi` | 1.7.5 | 47.68 | Optional-looking dependency; verify project/import references before removing (prefer env rebuild). |
| `Markdown` | 3.11.2 | 0.43 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `markdown-it-py` | 4.2.0 | 0.41 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `MarkupSafe` | 3.0.4 | 0.10 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `mcp` | 2.3.0 | 1.46 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `mcp-types` | 2.3.0 | 0.37 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `mdurl` | 0.1.2 | 0.05 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `multidict` | 6.9.1 | 1.17 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `nemo-relay` | 0.11.0 | 27.03 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `numpy` | 2.5.4 | 56.01 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `oauthlib` | 4.0.0 | 0.69 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `onnxruntime` | 1.31.0 | 62.23 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `openai` | 2.54.0 | 10.36 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `opentelemetry-api` | 1.45.1 | 0.27 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `opentelemetry-sdk` | 1.45.1 | 0.65 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `opentelemetry-semantic-conventions` | 0.66b1 | 1.04 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `packaging` | 26.3 | 0.54 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `pathspec` | 1.1.1 | 0.24 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `pillow` | 13.0.0 | 19.75 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `pillow_heif` | 1.8.1 | 26.09 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `prompt_toolkit` | 3.0.53 | 1.66 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `propcache` | 0.5.4 | 0.81 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `proto-plus` | 1.29.0 | 0.20 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `protobuf` | 6.33.6 | 1.38 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `psutil` | 7.2.2 | 0.53 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `ptyprocess` | 0.7.0 | 0.06 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `pyasn1` | 0.6.5 | 0.47 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `pyasn1_modules` | 0.4.2 | 1.02 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `pycparser` | 3.11 | 0.24 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `pycryptodome` | 3.24.1 | 6.83 | Optional-looking dependency; verify project/import references before removing (prefer env rebuild). |
| `pydantic` | 2.14.1 | 2.12 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `pydantic_core` | 2.50.1 | 5.00 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `Pygments` | 2.21.0 | 5.06 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `PyJWT` | 2.15.1 | 0.16 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `pyparsing` | 3.3.3 | 0.51 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `pypng` | 0.20220715.0 | 0.20 | Optional-looking dependency; verify project/import references before removing (prefer env rebuild). |
| `python-dateutil` | 2.9.0.post0 | 0.50 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `python-dotenv` | 1.2.4 | 0.11 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `python-multipart` | 0.0.32 | 0.14 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `PyYAML` | 6.0.3 | 2.77 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `qrcode` | 7.4.2 | 0.23 | Optional-looking dependency; verify project/import references before removing (prefer env rebuild). |
| `referencing` | 0.37.0 | 0.16 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `requests` | 2.34.2 | 0.29 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `requests-oauthlib` | 2.0.0 | 0.12 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `requests-toolbelt` | 1.0.0 | 0.23 | Optional-looking dependency; verify project/import references before removing (prefer env rebuild). |
| `resvg_py` | 0.5.0 | 2.97 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `rich` | 14.3.4 | 1.41 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `rpds-py` | 2026.9.1 | 1.05 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `ruamel.yaml` | 0.18.16 | 0.62 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `ruamel.yaml.clib` | 0.2.15 | 2.62 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `s3transfer` | 0.19.3 | 0.38 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `six` | 1.17.0 | 0.06 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `sniffio` | 1.3.1 | 0.05 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `snowballstemmer` | 3.1.1 | 0.84 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `socksio` | 1.0.0 | 0.06 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `sounddevice` | 0.5.6 | 0.15 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `sse-starlette` | 3.5.0 | 0.07 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `starlette` | 1.9.0 | 0.36 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `tabulate` | 0.10.0 | 0.17 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `termcolor` | 3.3.0 | 0.04 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `tokenizers` | 0.23.3 | 11.24 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `tomli_w` | 1.2.0 | 0.04 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `tqdm` | 4.70.1 | 0.33 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `truststore` | 0.10.5 | 0.09 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `typing-inspection` | 0.4.4 | 0.07 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `typing_extensions` | 4.16.0 | 0.19 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `uritemplate` | 4.2.0 | 0.06 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `urllib3` | 2.8.0 | 0.53 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `uvicorn` | 0.54.0 | 0.40 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `uvloop` | 0.23.0 | 15.60 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `watchfiles` | 1.3.0 | 1.24 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `wcwidth` | 0.9.2 | 3.50 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `websockets` | 15.0.1 | 0.73 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `yarl` | 1.25.1 | 0.40 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
| `youtube-transcript-api` | 1.2.4 | 2.18 | Keep as environment dependency; only remove by rebuilding env after confirming feature is unused. |
