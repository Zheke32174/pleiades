# Durable Work-Order Controller and Semantic Gateway

This directory contains the first executable runtime slice of the Pleiades Extended Autonomy Envelope.

It is deliberately narrow. The controller persists work-order admission and lifecycle state in SQLite, registers bounded semantic capabilities, enforces idempotency, records transition history and action receipts, survives process restart, and fails closed at the external-sovereign boundary.

The gateway adds a typed GPT-facing supervisory surface with exact caller and `mindId` binding. It has no shell, script, credential, filesystem, or network execution method.

It does **not** execute commands, hold credentials, create Ghosts, mutate canonical resources, schedule live work, expose a network endpoint, or claim production readiness.

## Implemented controller behavior

- SQLite WAL state with full synchronous durability;
- immutable capability-version registration;
- rejection of arbitrary-shell and external-irreversible capabilities;
- exact request-body idempotency;
- registered-operation and risk-ceiling admission;
- canonical-write, checkpoint, approval, and isolation gates;
- explicit legal lifecycle transitions;
- idempotent transition operation tokens;
- durable cancellation and restart recovery;
- evidence-backed action receipts;
- reconciliation requirement for uncertain effects;
- append-only transition history;
- bounded capability and receipt read paths.

## Implemented gateway verbs

```text
inspect_ecology
create_work_order
get_work_order
cancel_work_order
collect_evidence
```

The remaining contracted verbs fail closed until their backends exist:

```text
approve_stage
apply_scoped_change
manage_service
restore_checkpoint
```

There is intentionally no `run_command`, `shell`, or equivalent pass-through.

## Test

```bash
cd modos/work-order-controller
python -m unittest -v test_smoke.py test_gateway.py
```

The next implementation step is a deterministic `repository.test_and_report` worker that consumes admitted operation intents inside one Ghost workspace and returns typed evidence and receipts. That work remains owned by issues #28, #31, #32, and #33. Authentication transport, rate controls, taint handling, approval persistence, service adapters, and recovery remain in issue #29.
