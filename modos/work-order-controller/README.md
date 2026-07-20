# Durable Work-Order Reference Controller

This directory contains the first executable runtime slice of the Pleiades Extended Autonomy Envelope.

It is deliberately narrow. The controller persists work-order admission and lifecycle state in SQLite, registers bounded semantic capabilities, enforces idempotency, records transition history and action receipts, survives process restart, and fails closed at the external-sovereign boundary.

It does **not** execute shell commands, hold credentials, create Ghosts, mutate canonical resources, schedule live work, or claim production readiness.

## Implemented

- SQLite WAL state with full synchronous durability;
- immutable capability-version registration;
- rejection of arbitrary-shell and external-irreversible capabilities;
- exact request-body idempotency;
- registered-operation and risk-ceiling admission;
- canonical-write, checkpoint, approval, and isolation gates;
- explicit legal lifecycle transitions;
- idempotent transition operation tokens;
- durable cancellation;
- restart recovery;
- evidence-backed action receipts;
- reconciliation requirement for uncertain effects;
- append-only transition history.

## Test

```bash
cd modos/work-order-controller
python -m unittest -v test_smoke.py
```

The next implementation step is a deterministic `repository.test_and_report` worker that consumes admitted operation intents inside one Ghost workspace and returns typed evidence and receipts. That work remains owned by issues #28, #31, #32, and #33.
