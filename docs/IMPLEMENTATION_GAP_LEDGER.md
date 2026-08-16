# Pleiades Implementation Gap Ledger

**Checkpoint:** 2026-07-20

This file prevents architecture decisions, discovered defects, and proposed improvements from remaining only in chat sessions. It distinguishes:

- **implemented** — executable code or contract exists on a branch;
- **tracked** — a dedicated issue or pull request owns the work;
- **validation pending** — code exists but has not been proven on the intended live estate;
- **research backlog** — preserved, but not yet an implementation commitment.

An open draft branch is not merged or deployed.

## Existing GitHub coverage

| Area | Durable location |
|---|---|
| Defensive trust-plane hardening | PR #2, issue #3 |
| MODOS/PDK authority spine and convergent-mind contracts | PR #5, issue #6 |
| Capability admission, expiry, revocation, receipts, and principal binding gaps | issues #8, #11, #13–#15, #18 |
| Durable event/heartbeat continuity | issues #16, #17, #25 |
| Cross-platform authenticated observation ingress | PR #20, issue #19 |
| Ecology checkpoint | PR #21 |
| Immutable Factory promotion-review eligibility | PR #22 |
| Cross-repository modernization program | issue #4 |

## Implemented on `autonomy/extended-work-orders-v1`

### Executable contracts

- `WorkOrder` and `WorkOrderStage` schemas;
- exact expiring `StageApproval` schema;
- authority-free `EvidenceRecord` schema;
- restore-tested `CheckpointRecord` schema;
- idempotent/reconcilable `ActionReceipt` schema;
- bounded `CapabilityDefinition` registry schema;
- semantic connector/work-order boundary document;
- 17 positive and adversarial fixture cases;
- semantic validation for canonical mutation, approval boundaries, sovereign effects, isolation, restore claims, uncertain effects, arbitrary shell access, and direct self-promotion.

### First runtime slice

`modos/work-order-controller/` now implements and tests:

- SQLite WAL persistence with full synchronous durability;
- immutable capability-version registration;
- exact request-body idempotency and conflict detection;
- registered-operation and bounded-risk admission;
- rejection of arbitrary-shell and external-sovereign authority;
- canonical-write, checkpoint, approval, and isolation gates;
- explicit legal lifecycle transitions with idempotent operation tokens;
- durable cancellation, restart recovery, and append-only transition history;
- evidence-backed action receipts;
- mandatory reconciliation for uncertain effects.

GitHub Actions validates the contract wave, the shared MODOS contracts, and the controller smoke tests. This slice does not execute commands, hold credentials, create Ghosts, mutate canon, schedule live work, or constitute a deployment receipt.

## Runtime work now durably tracked

| Obligation | State | Issue |
|---|---|---|
| Program umbrella and first vertical slice | partial implementation | #27 |
| Restart-safe durable controller | persistence/admission slice implemented; scheduling and execution remain | #28 |
| Semantic GPT Autonomy Gateway | tracked | #29 |
| Capability registry and Forge admission | bounded registry/admission slice implemented; PDK integration remains | #31 |
| Ghost lifecycle and unified branch identity | tracked | #32 |
| Evidence, checkpoint, receipt, and rollback fabric | receipt contract/runtime slice implemented; recovery fabric remains | #33 |
| Atlas/shared-workspace/learning-spine integration | tracked | #35 |
| Bounded cognitive coprocessor and service learning joints | tracked | #36 |
| Counterfactual Ghost replay improvement chamber | tracked | #37 |

## Preserved architectural obligations

- Models and agents are differentiated organs of one persistent `mindId`; Agent Computers retain continuity while models remain replaceable.
- Risky work runs in Ghosts. One branch identity spans code, filesystems, data, ontology, infrastructure, telemetry, agents, and evidence.
- Branches never mutate canon directly. Promotion binds exact evidence, artifacts, state, approval, canary, and rollback.
- Every resident service emits observations, decisions, evidence, outcomes, corrections, and provenance into the learning spine.
- Transformation never launders trust or authority. External instructions remain data and cannot flow directly into execution.
- The host kernel stays deterministic and sovereign; the cognitive coprocessor may observe, retrieve, coordinate, and propose only through typed capabilities.
- Counterfactual replay may run many cheap candidate trajectories, but may only produce promotion-review candidates—not self-promote.

## Cross-repository audit targets

Later implementation audits must cover `pleiades-container`, `pleiades-factory`, `pleiades-factory-stack`, `pleiades-termux`, `pleiades-windows`, `undergrowth`, `understory`, and admitted RYZ/AeSH/distro work. No repository visibility change is authorized by this ledger.

## Completion rule

A note is safely preserved when GitHub contains executable code or schema with tests, an architecture document with explicit invariants, a dedicated issue with acceptance criteria, or a pull request that honestly separates implemented, validated, and untested behavior.

A task is implemented only when code exists and relevant automated or live validation evidence has been recorded. Tracking prevents loss; it does not manufacture completion.
