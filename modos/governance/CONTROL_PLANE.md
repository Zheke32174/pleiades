# Pleiades Executive Control Plane

This tranche implements progression points 1–40 from
`modos/ECOLOGY_PROGRESSION_100.md` beneath the delegated executive authority
defined in `modos/EXECUTIVE_AUTHORITY.md`.

The control plane is divided into four deterministic seams. None of them alone
possesses end-to-end authority.

## 1. Executive policy classification

`policy.py` evaluates one bounded change request under one exact
`ExecutivePolicy` and selects:

- risk tier;
- delegated-machine, mixed-quorum, or human-reserved authorization;
- required human approvals;
- whether a persistent Mind decision and active grant are required;
- executor capability;
- rollback obligation.

The classifier cannot approve or execute the change. Constitutional and
self-authority actions are forced into reserved-power handling. Wildcard
policy scopes are refused.

## 2. Authority registry closure

`registry.py` resolves effective grant state from immutable grants and
lifecycle events.

It recognizes issuance, suspension, resumption, revocation, and expiry. A
subject Mind cannot issue its own grant. Revocation is terminal for one grant
generation. Closure emits the active grant set at one exact evaluation time
without mutating the registry.

## 3. Execution and rollback evidence

`execution.py` evaluates a reported attempt against one exact authorization
receipt and one exact admission mandate.

It checks:

- executor identity and zero decision authority;
- mandate digest and expiry;
- preconditions and postconditions;
- bounded write scope and wall-time budget;
- exact target-state digest;
- automatic restoration of the predecessor when postconditions fail.

It emits an `ExecutionReceipt`, a `RollbackReceipt`, and hash-linked append-only
audit events. It does not run commands or write canonical state.

## 4. Outcome learning and competence

`competence.py` updates a domain-specific competence profile only from
independently verified outcome evidence.

The deciding Mind cannot verify its own results. The profile tracks success,
failure, safe rollback, policy violation, and integer-basis-point competence.
The engine may emit an `AuthorityAdjustmentProposal` to grow, narrow, or
suspend authority, but it cannot alter a live grant. Every adjustment proposal
requires external constitutional authorization.

## Contract and fixture surface

`modos/contracts/executive-control-plane.schema.json` contains fourteen Draft
2020-12 definitions covering:

1. executive policy;
2. classification request;
3. policy receipt;
4. authority lifecycle event;
5. authority registry;
6. registry receipt;
7. execution attempt;
8. execution receipt;
9. rollback receipt;
10. executive audit event;
11. outcome evidence;
12. competence profile;
13. authority-adjustment proposal;
14. competence-update receipt.

`control_plane_fixtures.py` pins eight golden digests over a bounded ontology
scenario: policy classification, grant closure, successful execution,
automatic rollback, and competence-driven authority growth proposal.

## Validation

```bash
python ci/validate-executive-control-plane.py
python modos/governance/test_control_plane.py
python -m py_compile \
  ci/validate-executive-control-plane.py \
  modos/governance/policy.py \
  modos/governance/registry.py \
  modos/governance/execution.py \
  modos/governance/competence.py \
  modos/governance/control_plane_fixtures.py \
  modos/governance/test_control_plane.py
```

Locally reproduced for this branch:

- fourteen contract definitions validated;
- four deterministic engines exercised;
- twenty-seven adversarial tests passed;
- eight golden digests reproduced;
- bytecode compilation passed for the executable control-plane files.

## Deliberate boundary

This tranche does not issue a live grant, execute a live mandate, mutate a live
snapshot, apply an authority adjustment, resolve issue #42, or configure a
GitHub ruleset. It supplies the deterministic decision, lifecycle, evidence,
and learning machinery needed before those live-system steps can be admitted.
