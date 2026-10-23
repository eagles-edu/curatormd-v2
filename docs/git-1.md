# [https://github.com/eagles-edu/curatormd-v2.git]

Here’s a proposed pilot default for review, not an applied policy:

- Identity: Trust only the subject? Hermes Core? supplies from its authenticated context?. Keep that opaque subject? separate from the profile? and project IDs?; treat missing identit?y or auth=none? as denied?. For renew-ssl-coding, leave the human subject unassigned? until you *identify the verified subject to bind*?. Hermes represents authenticated subjects? separately from profile IDs in [session_identity.py (line 281)](/home/eaglesvn/.hermes/hermes-agent/gateway/session_identity.py:281).
(i'M GONNA NEED CLEARER CONTEXT, CURRENTLY THIS IS AKIN TO GIBBERISH)

- Project access: A Hermes Core root-account? operator provisions exact subject?, profile?, project?, and action grants?. No wildcard or self-registration?. For the pilot?, scope grants? to renew-ssl-coding and vhost-manager-alpha.
(i'M GONNA NEED CLEARER CONTEXT, CURRENTLY THIS IS AKIN TO GIBBERISH)

- Roles: Give one verified, owner-selected subject project admin and reviewer rights for the pilot. That reviewer can decide SDEs and release holds. Destructive cleanup still requires an approved decision and complete inventory. Host Steward administration stays with Hermes Core’s root account.
(i'M GONNA NEED CLEARER CONTEXT, CURRENTLY THIS IS AKIN TO GIBBERISH)

- Retention: Set a seven-day maximum for raw chat/transcript, cue, import, scratch, generated intermediate, and duplicate artifacts. (ONCE THEIR RECORDED, THEN REVIEWED, THE RECORDS SHOULD BE MARKED FOR EXPIRY ASAP AND PURGED PROMPTLY) After expiry, mark them eligible and require human approval of the exact inventory before deletion; (NO RECORDED SDE BECOMES THE RECORD) a scheduler may retry already-approved purges, but cannot authorize new ones. A hUNAPPROVED SDE ITEM pauses expiry until an authorized reviewer APPROVES OR REJECTS IT; AUTHORIZED REVIEW & DISPOSITION releases a hold automatically.

The current renew-ssl-coding subject and the owner-selected reviewer still need exact values from you. Approve this draft or tell me what to change; I’ll keep the identity and retention gates open until then. The Curator V2 goal remains active.
