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
  common provider-token prefixes.
- Email addresses, syntactically valid US SSN-shaped strings, and phone numbers
  explicitly labeled `phone`, `mobile`, `cell`, or `telephone`.

Validation runs in domain/event constructors and event identifiers, including
source event IDs retained in goal reports, and direct in-process calls that
bypass JSON ingress. Strict version-1 event schemas, required fields,
unknown-field rejection, event byte caps, and typed domain models provide the
structural validation layer. API JSON ingress parses and validates the complete
event before an inbox receipt is written. Regression tests assert sensitive
payloads are absent from both event inbox and goal tables after rejection.

## Limits and operator rule

Pattern detection cannot prove that arbitrary free text contains no secret or
personal data. It may miss unknown credential formats, names, unlabelled phone
numbers, non-US identifiers, encoded data, or data split across fields; it may
also reject a legitimate string that resembles a sensitive value. The error
does not disclose the matched text. Do not interpret a clean scan as a privacy
certification or as proof that logs, backups, traces, or upstream transport are
safe. The preliminary scope-bounded register is in
[`threat-model-v1.md`](threat-model-v1.md). It does not close the broader
threat-model, jurisdiction-specific rules, deployment-owner review, or
independent-validation release gates.

Evidence meaning is preserved by rejection, not by redaction: V2 does not
attempt to sanitize a statement and then treat the modified wording as proof.
