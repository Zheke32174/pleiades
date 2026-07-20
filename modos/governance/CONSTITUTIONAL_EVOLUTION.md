# Constitutional Evolution and Institutional Plurality

This tranche implements progression points 81–90 from
`modos/ECOLOGY_PROGRESSION_100.md`.

`constitutional.py` verifies one proposed constitutional amendment. It never
activates or applies the amendment.

## Separate amendment path

A constitutional amendment is not an ordinary executive decision. It binds:

- the current and candidate constitution digests;
- exact rollback to the predecessor constitution;
- rationale and evidence;
- amendment class;
- cancellation deadline;
- activation timelock;
- supersession lineage;
- proposal-only authority.

## Institutional plurality

The governance registry recognizes differentiated principals and roles:

- constitutional stewards;
- the persistent machine executive Mind;
- independent auditors;
- appeal authorities;
- institutional successors.

Authority-model amendments require a mixed human–Mind quorum and independent
audit. Audit and appeal principals cannot become ordinary approving votes.

## Conflict, succession, and appeal

Declared or registered conflicts require recusal. Recused principals do not
count toward quorum. Succeeded principals must resolve to a registered
successor. Independent appeal authority remains separate from amendment
approval.

## Timelock, cancellation, and rollback

Every amendment class declares a minimum timelock and appeal window.
Constitutional stewards may cancel before the deadline. Activation cannot occur
before the timelock expires. The rollback digest must equal the exact predecessor
constitution digest, and supersession may not self-reference.

The receipt status is:

- `cancelled`;
- `timelock-pending`; or
- `eligible-for-activation`.

Eligibility is not activation. A later capability-bound constitutional executor
must still verify the receipt and apply the exact transition.

## Validation

```bash
python ci/validate-constitutional.py
python modos/governance/test_constitutional.py
```

Locally reproduced:

- four contract definitions validated;
- one deterministic constitutional gate exercised;
- twelve adversarial tests passed;
- one golden digest reproduced;
- executable files passed bytecode compilation.

## Deliberate boundary

This tranche does not activate an amendment, rewrite authority, appoint a
successor, resolve an appeal, or mutate the live constitution.
