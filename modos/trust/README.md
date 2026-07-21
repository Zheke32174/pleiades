# Pleiades Operational Trust and Transition Preflight

Checkpoint 400 closes the gap between an opaque operator reference and a
reviewable authorization path.

A SHA-256 digest proves identity, not legitimacy. This layer verifies:

- which active principal issued each evidence binding;
- which active Ed25519 key signed it;
- whether the issuer is scoped to that exact operator input;
- whether the evidence is fresh, unexpired, and unrevoked;
- whether the selected transition plan is the exact compiled plan;
- whether the governing operational policy selects one authorization mode;
- whether the delegated grant is active, in scope, and within its risk ceiling;
- whether required human, Mind, and independent-audit contributions exist;
- whether conflicts recuse, rejects remain below threshold, and proposer,
  approver, and executor duties remain separated;
- whether rollback restores the exact predecessor.

## Authority hierarchy

`OperationalAuthorityRegistry` is subordinate to promoted constitutional
policy. It is a closure and verification registry only. It cannot issue a
grant, alter policy, authorize itself, construct a mandate, contact a node, or
execute a transition.

Constitutional and self-authority changes remain governed by the separate
constitutional evolution path and cannot be downgraded into routine
operational policy.

## Evidence attestations

`evidence.py` verifies Ed25519 signatures over the canonical attestation
statement. The repository contains only synthetic public keys and signatures;
the one-time synthetic private keys used to create the fixtures were discarded
and are not present in the repository or validation package.

Every supplied `OperatorInputCandidate` input requires the configured number
of distinct authorized attestors. Missing attestations produce a blocked
receipt. Tampered signatures, wrong issuer scope, stale evidence, key-digest
mismatch, duplicate nonces, and effective revocation fail closed.

## Transition preflight

`preflight.py` binds:

1. the operator candidate;
2. its deterministic compilation receipt;
3. the trusted-evidence receipt;
4. the selected preparation-plan digest;
5. the exact delegated grant;
6. operational policy;
7. signed approval and audit contributions;
8. predecessor, target, and rollback lineage;
9. the exact executor capability.

The strongest successful result is
`eligible-for-mandate-construction`. No mandate is created, no authorization is
applied, and no execution occurs.

## Validation

```bash
python ci/validate-operational-trust.py
python modos/trust/test_evidence.py
python modos/trust/test_preflight.py
```

All evaluation times are explicit inputs. Wall-clock time is never silently
read into a receipt identity.
