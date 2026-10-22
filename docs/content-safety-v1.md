# Durable-content safety gate, version 1

The V2 domain rejects recognized sensitive strings before they enter goal,
fact, review, or lifecycle-event storage. The gate is reject-only: it never
rewrites or redacts input, because silent transformation could change what an
evidence statement means. Errors identify only the field and detection
category; they never echo the rejected value. The caller must remove sensitive
content or replace it with an approved non-sensitive reference, then resubmit.

## Current high-confidence patterns

- Private-key PEM markers.
- Common credential assignments such as `api_key=`, `token=`, and
  `password=`; credentials embedded in URL user-info; JWT-shaped values; and
  common provider-token prefixes, including GitLab PAT (`glpat-`), Stripe
  secret (`sk_live_` / `sk_test_`), and restricted (`rk_live_` / `rk_test_`)
  keys, GitHub fine-grained PAT (`github_pat_`), and stateless GitHub App
  installation tokens (`ghs_`).
- Email addresses, syntactically valid US SSN-shaped strings, and phone numbers
  explicitly labeled `phone`, `mobile`, `cell`, or `telephone`.

Validation runs in domain/event constructors and event identifiers, including
source event IDs retained in goal reports, and direct in-process calls that
bypass JSON ingress. Strict version-1 event schemas, required fields,
unknown-field rejection, event byte caps, and typed domain models provide the
structural validation layer. API JSON ingress parses and validates the complete
event before an inbox receipt is written. Regression tests assert sensitive
payloads are absent from both event inbox and goal tables after rejection.
Purge failures store only a fixed failure code, not raw exception text. The
SQLite v16 migration replaces prior failed-target exception strings with
`legacy_failure_detail_redacted` while retaining the failed/retryable state.

## Limits and operator rule

Pattern detection cannot prove that arbitrary free text contains no secret or
personal data. It may miss unknown credential formats, names, unlabelled phone
numbers, non-US identifiers, encoded data, or data split across fields; it may
also reject a legitimate string that resembles a sensitive value. GitLab
documents `glpat-` as the default personal/project/group token prefix, with a
20-character token body; administrators can configure a custom PAT prefix,
which this default scanner does not infer. See the [GitLab token prefix
reference](https://docs.gitlab.com/security/tokens/) and [custom prefix
settings](https://docs.gitlab.com/administration/settings/account_and_limit_settings/).
GitHub documents `github_pat_` for fine-grained personal access tokens and
reports that stateless installation tokens retain the `ghs_` prefix while
growing to approximately 520 characters with a JWT body. The detector matches
the prefix and bounded token-like body without requiring a fixed length. See
[GitHub token formats](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-authentication-to-github)
and the [stateless installation-token rollout](https://github.blog/changelog/2026-10-02-stateless-github-app-installation-tokens-rolled-out/).
The error does not disclose the matched text. Do not interpret a clean scan
as a privacy certification or as proof that logs, backups, traces, or upstream
transport are safe. The preliminary scope-bounded register is in
[`threat-model-v1.md`](threat-model-v1.md). It does not close the broader
threat-model, jurisdiction-specific rules, deployment-owner review, or
independent-validation release gates.

Evidence meaning is preserved by rejection, not by redaction: V2 does not
attempt to sanitize a statement and then treat the modified wording as proof.
