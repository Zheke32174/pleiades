# Distributed Substrate Admission

This tranche implements progression points 61–70 from
`modos/ECOLOGY_PROGRESSION_100.md`.

`distributed_admission.py` closes one capability-bound rollout plan over one
exact node registry. It does not contact nodes or execute the rollout.

## Node capability registry

Every target node declares:

- hardware identity digest;
- service principal and service-identity digest;
- key identity digest;
- bounded capabilities;
- bounded write scopes;
- local authority ceiling;
- network-partition behavior.

Node, principal, and key identities must be unique. Wildcard capabilities and
write scopes are refused. A node retaining distributed-stage authority while
partitioned is refused; distributed authority fails closed.

## Staged rollout plan

A rollout binds:

- one authorization receipt and mandate;
- exact target, predecessor, and rollback digests;
- one replay nonce and idempotency key;
- one bounded executor capability and write scope;
- contiguous rollout stages;
- a first canary stage;
- health-gate evidence for every stage;
- coordinated rollback groups.

Every target node must appear exactly once. Each node must possess the required
executor and exact-rollback capabilities, write scope, and authority ceiling.
No later stage may advance without its predecessor health gate passing.

An exact replay of the same plan is reported as `idempotent-replay`. Reusing a
nonce or idempotency key for a different plan fails closed.

## Validation

```bash
python ci/validate-distributed-admission.py
python modos/governance/test_distributed_admission.py
```

Locally reproduced:

- three contract definitions validated;
- one deterministic rollout engine exercised;
- twelve adversarial tests passed;
- one golden digest reproduced;
- executable files passed bytecode compilation.

## Deliberate boundary

This tranche emits a `DistributedRolloutReceipt` only. It does not open network
connections, deploy to a node, advance a stage, perform rollback, rotate a key,
or mutate a live substrate.
