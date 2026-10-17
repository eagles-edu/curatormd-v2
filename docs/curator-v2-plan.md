# Curator V2: goal-ledger intelligence, not transcript curation

## Summary

The missing primary object is a **goal**, created from a user request, a checklist item, or an explicit agent subtask. V2 continuously records compact, evidence-backed lifecycle facts against that goal. A real SDE is a derived durable outcome—not the unit of capture.

```mermaid
flowchart TB
  subgraph Intake["1. Goal intake"]
    U[User request] --> GI[Goal intake]
    CL[Checklist item] --> GI
    ST[Agent-proposed subtask] --> GI
    GI --> GC[Goal card]
    GC --> GS[State: planned or active]
  end

  subgraph GoalCard["Goal card: durable, compact"]
    P[Problem / task statement]
    SC[Success criteria]
    OW[Owner and linked checklist ID]
    STS[State: active, complete, open, blocked, deferred]
    NA[Next action or explicit open gate]
  end

  GC --> GoalCard

  subgraph Work["2. Structured work events"]
    I[Intent / remediation plan]
    CH[Changed fact\ncode, config, service, decision]
    VE[Verification evidence\ncommand, browser, probe, review]
    OG[Open gate\nwhat remains and why]
    CO[Completion claim]
  end

  GS --> I
  I --> CH
  CH --> VE
  VE --> CO
  VE --> OG

  subgraph Ledger["3. Fact ledger: bullet records, no prose dump"]
    FB1["- Implemented: fact + changed component"]
    FB2["- Verified: exact check/probe + result"]
    FB3["- Open: unmet success criterion + reason"]
    FB4["- Next: concrete follow-up / checklist link"]
  end

  CH --> FB1
  VE --> FB2
  OG --> FB3
  CO --> FB4

  subgraph Assessment["4. Significance and truth gate"]
    DG[Deduplicate against existing facts]
    EG[Evidence gate\nclaim is not proof]
    SG{Material durable change,\nrecovery, decision,\nor verified lesson?}
    DG --> EG --> SG
  end

  Ledger --> DG

  subgraph Decision["5. Decision and cleanup"]
    NSDE[Ordinary goal update\nretain compact facts only]
    SDE[Candidate SDE card\nselected bullets only]
    HC{Human confirms?}
    REC[Audit receipt\nIDs, hashes, decision, purge result]
    PURGE[Purge all raw cue,\nthread, scratch and import artifacts]
  end

  SG -->|No| NSDE
  SG -->|Yes| SDE
  SDE --> HC
  HC -->|Approve| REC
  HC -->|Reject| REC
  REC --> PURGE
  NSDE --> REC

  subgraph Views["6. Truthful status"]
    DASH[Goal dashboard]
    TODO[Open goals / checklist gates]
    DONE[Completed goals]
    PEND[Purge-pending failures]
  end

  Ledger --> DASH
  FB3 --> TODO
  FB2 --> DONE
  PURGE --> PEND

  subgraph Steward["Separate host steward: approval-gated"]
    DI[Disk inventory] --> GR[Growth attribution]
    GR --> CP[Managed cleanup proposal]
    CP --> HA[Human approval]
    HA --> MC[Managed cleanup]
    MC --> SV[Verify free space and service health]
  end
```

## Core behavior

- At task start, V2 records: **problem**, **success criteria**, linked checklist item, and initial state.
- During work, agents emit compact typed facts rather than preserving full chats: intent, change, verification, open gate, completion, and cleanup.
- At task finish, V2 records one of:
  - **Completed:** every success criterion has direct evidence.
  - **Open/deferred:** completed facts, remaining criteria, blocker, and next action.
  - **Blocked:** exact failed dependency plus recovery path.
- A significance gate derives an SDE only when evidence supports a durable implementation, decision, recovery, or lesson. Routine progress remains a goal update.
- Every durable record is short bullets, separating observed facts from planned or unverified claims.
- After approval or rejection, V2 retains the compact goal facts and an audit receipt, then removes all transient artifacts. Failed deletion is visible as `purge_pending`, never hidden behind green health.

## Token and disk discipline

- No raw transcript store, cue queue, scratch archive, or paragraph synthesis pipeline.
- One bounded goal card plus deduplicated fact bullets; new events merge into the existing goal rather than creating duplicate records.
- Evidence references carry hashes, path/command identifiers, and outcomes—not command output or chat history.
- Status reports show: active goals, completed goals, explicit open gates, SDE candidates, and failed purges.
- The separate Host Steward reports disk growth and proposes managed cleanup; it performs no deletion without approval.

## Interfaces and tests

- `goal.start`, `goal.fact`, `goal.finish`, `goal.defer`, `goal.status`
- `sde.assess`, `sde.confirm`, `artifact.purge_status`
- `steward.inventory`, `steward.propose_cleanup`, `steward.execute_cleanup`

Tests must prove that:
- a checklist task preserves its original success criteria through completion;
- an incomplete task stays open with a concrete next action;
- unsupported agent claims cannot close a goal;
- ordinary updates do not become SDEs;
- confirmed/rejected SDEs purge transient artifacts while preserving bullet facts and receipts;
- an interrupted purge is retried and visibly reported;
- no host cleanup happens without explicit approval.

## Cutover

Freeze V1 read-only, preserve existing canonical Markdown, inventory its runtime artifacts, create purge receipts, then remove obsolete V1 sources in an auditable pass. Do not import V1’s raw transcripts into V2.
