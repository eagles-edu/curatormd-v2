# Curator V2 content-safety threat model

## Decision and boundary

Curator V2 rejects selected high-confidence strings before durable goal,
evidence, fact, review, and event writes. It never edits or redacts a value.
The error names the field and detector category, not the matched text. The
caller must remove sensitive material or replace it with a permitted reference.

This is a narrow text-pattern gate. It is not a general data-loss-prevention
service, a scanner for arbitrary files, or proof that a clean value is safe.
The implementation validates already-decoded string fields. Event JSON is
bounded to 16 KiB before it is admitted; project configuration is scanned
recursively through its decoded string keys and values. Evidence locators and
attestation strings are validated, but the external evidence they point to is
not downloaded or scanned by this gate.

## Current detections

The implementation in `src/curatormd_v2/content_safety.py` rejects:

- PEM private-key markers, credentials in URL user-info, and common
  credential assignments such as `api_key=`, `token=`, `password=`, or
  `secret=`.
- Recognized token forms for common providers, JWT-shaped strings, and
  credential prefixes including `sk_`, `rk_`, `sk-`, GitHub, AWS, Slack,
  Google API, and default GitLab PAT forms.
- Password assignments labeled `pwd=` and base64url-like ACME DNS challenge
  values of at least 32 characters when labeled `TXT value:`, `TXT record:`, or
  `DNS challenge:`. Ordinary `_acme-challenge` record names are not matched.
- Email-like values, US SSN-shaped values, and phone-like values when labeled
  `phone`, `mobile`, `cell`, or `telephone`.

The exact expression set is code-defined and may change. A passing scan means
only that none of those current expressions matched the validated strings.
The versioned synthetic local-alpha regression corpus is
[`tests/fixtures/content-safety-v2-local-alpha.json`](../tests/fixtures/content-safety-v2-local-alpha.json):
ten rejected examples across the current patterns and three benign neighbors.
The corpus measures only those examples; it does not estimate coverage of
unknown or transformed inputs.

## False negatives and unsupported formats

The detector can miss unknown or custom provider prefixes; short or unusual
token forms; secrets split across fields; URL-encoded, escaped, encrypted,
compressed, or otherwise transformed values; unlabelled phone numbers; names;
addresses; non-US government identifiers; health, financial, or other
jurisdiction-specific personal data; and content embedded in images, audio,
archives, binaries, or external evidence targets. It does not inspect raw chat,
transcripts, files, process memory, upstream model context, or arbitrary logs.
Those sources must not be sent to canonical facts as a substitute for a
dedicated, approved inspection workflow.

## False positives and impact

Legitimate examples, fixtures, identifiers, or prose can resemble an email,
phone number, SSN, token, or credential assignment. Because the control rejects
instead of redacting, the write fails and the caller must revise the content.
This preserves evidence meaning but can block legitimate work; it does not
silently turn a modified statement into verified evidence. Errors and logs must
not include the matched string.

## Jurisdiction and deployment policy

No jurisdiction-specific classification or legal conclusion is inferred by
this scanner. Before a deployment expands collection beyond the local alpha,
the deployment/data owner must identify applicable jurisdictions, data
classes, lawful basis and retention requirements, approved detector behavior,
and the reviewer responsible for exceptions. Until that decision exists,
unsupported classes stay out of canonical V2 facts and the privacy gate stays
open. Detector additions require tests for both the intended match and nearby
benign text, plus checks that rejected values do not reach API errors, logs,
receipts, database rows, backups, or canonical projections.

## Required validation before wider use

- Maintain a content-free inventory of the supported patterns and known
  exclusions, tied to the detector revision.
- Add positive and benign-neighbor cases for each detector change; test
  encoded, split, oversized, and malformed inputs at the API boundary.
- Verify rejected values are absent from every durable and diagnostic surface
  touched by the affected write path.
- Review false-positive and false-negative impact with the deployment owner;
  do not describe scanner output as privacy certification.
- Keep external evidence scanning, file scanning, jurisdiction decisions,
  production log/trace privacy, and independent security review as separate
  gates until implemented and verified.
