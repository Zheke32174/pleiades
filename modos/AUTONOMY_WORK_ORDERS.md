# MODOS Durable Work Orders

This document turns the Pleiades Extended Autonomy Envelope into an executable MODOS contract surface.

## Decision

GPT-facing autonomy is a typed supervisory interface over durable work orders. It is not a shell, credential broker, or permanent model session.

Pleiades owns:

- persistence;
- scheduling;
- local execution;
- credentials and workload identity;
- deterministic policy;
- checkpoints and rollback;
- evidence collection;
- audit and learning continuity.

A transient cognitive organ may inspect, commission, supervise, critique, approve within delegated bounds, cancel, request recovery, and resume later.

## Public connector surface

The intended first connector exposes only these semantic verbs:

```text
inspect_ecology
create_work_order
get_work_order
approve_stage
cancel_work_order
apply_scoped_change
manage_service
collect_evidence
restore_checkpoint
```

No verb accepts an arbitrary shell command. Every mutation resolves through a registered `CapabilityDefinition`, one policy decision, one scoped lease, and one durable action receipt.

## Contract objects

This wave adds:

- `WorkOrder` — durable intent, target, constraints, trigger, approval policy, recovery requirements, and lifecycle state;
- `WorkOrderStage` — one planned transition with exact capability, risk, authority, evidence, and immutable operation intent;
- `StageApproval` — expiring approval bound to one stage digest, operation intent, target set, and risk tier;
- `EvidenceRecord` — authority-free observation, test, measurement, inference, model judgment, or decision evidence;
- `CheckpointRecord` — exact covered objects, consistency class, restore procedure, restore-test evidence, and external-effect limits;
- `ActionReceipt` — idempotency, effect class, authority references, result identity, uncertainty, compensation, and reconciliation state;
- `CapabilityDefinition` — the registry object that defines allowed operations, targets, risk, isolation, verification, approval, security, and learning behavior.

The corresponding schemas live in `modos/contracts/` and are exercised by the extended-autonomy semantic validator.

## Work-order lifecycle

```text
draft
  -> validating
  -> admitted
  -> queued
  -> preparing
  -> running
       -> paused
       -> awaiting-approval
       -> blocked
       -> quarantined
       -> canceling
       -> verifying
            -> running              revision required
            -> rolling-back         verification or canary failure
            -> succeeded
  -> failed | canceled | rolled-back | expired | recovery-failed
```

Every transition must retain:

- prior and next state;
- actor and `mindId`;
- exact policy decision;
- consumed capability and lease;
- operation-intent digest;
- evidence references;
- object versions;
- timestamp and idempotency token.

## Risk classes

| Tier | Name | Typical effects | Default authority |
|---:|---|---|---|
| 0 | observe | read state, logs, metrics, comparisons | automatic |
| 1 | operate | disposable builds, tests, diagnostics, Ghost creation | automatic within budget |
| 2 | reversible | checkpoint-backed development mutation or bounded service operation | delegated only when policy and recovery are proven |
| 3 | confirmed | canonical mutation, canary, production change, meaningful restore | exact expiring approval |
| 4 | external-sovereign | root trust, connector authority, irreversible external effect, audit/rollback disablement | unreachable through the ordinary connector |

A work order may describe or prepare evidence for a Tier 4 action. It may not execute or approve it.

## Admission invariants

A work order is admitted only when:

1. caller identity and `mindId` binding are valid;
2. the request matches the schema;
3. its capability and version are registered;
4. target identity and current version are resolved;
5. risk and blast radius are within the declared ceiling;
6. resource, concurrency, and trigger limits are bounded;
7. checkpoint and restore requirements are satisfiable;
8. Forge returns an allowing or approval-required decision;
9. an idempotency key prevents duplicate logical admission.

## Execution invariants

```text
No connector request becomes a raw command.
No model manufactures authority.
No branch mutates canon directly.
No completed action lacks a receipt.
No completed stage lacks declared evidence.
No reversible claim exists without a tested restore path.
No uncertain non-idempotent effect is blindly retried.
No work order changes its own validators, authority, or audit history.
No learning record promotes itself.
```

## Session handoff

The durable work order, not the chat transcript, is operational truth. A later authorized model session may retrieve:

- objective and accepted interpretation;
- constraints and non-goals;
- plan version and current stage;
- milestones and exceptions;
- evidence and contradictions;
- resource consumption;
- pending decision packet;
- checkpoint and rollback state.

The initiating session may disappear without canceling the work.

## First runtime slice

The first implementation target remains deliberately narrow:

1. inspect one registered repository;
2. create `repository.test_and_report`;
3. continue after the initiating chat closes;
4. execute in one Ghost workspace;
5. emit test evidence and action receipts;
6. support cancellation and resource limits;
7. return structured status to a later session;
8. preserve the result in Atlas and the operational ledger;
9. perform no canonical mutation.

Only after that slice survives restart, duplicate requests, cancellation, failure injection, and session handoff should reversible mutations be enabled.

## Relationship to existing PDK work

The PDK remains the deterministic authority and node-execution substrate. Work orders are the durable supervisory layer above it.

- `CapabilityDefinition` selects what may be requested.
- Forge and PDK policy decide what may be admitted.
- `CapabilityLease` bounds what a node may exercise.
- `WorkOrderStage` binds one planned use.
- PDK emits `ActionReceipt` and evidence.
- canonical promotion still requires the existing `PromotionTransaction` contract.

This does not create a competing control plane. It makes long-running GPT-supervised work a governed organ of the same Pleiades world.
