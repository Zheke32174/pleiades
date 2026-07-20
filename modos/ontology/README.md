# Proposal-only ontology compiler

This directory contains the first deterministic compilation seam beneath the
`ChangeProposal` contract.

The compiler accepts one exact `OntologySnapshot` and one authority-free
`ChangeProposal`. It produces a candidate snapshot and an
`OntologyClosureReceipt`. It does **not** promote, sign, deploy, admit, or make
the result canonical.

## Determinism and refusal rules

- strict UTF-8 JSON with duplicate keys, floats, NaN, and infinity refused;
- canonical JSON uses sorted keys, compact separators, and direct Unicode;
- source snapshots are normalized by object identity and relation identity;
- every proposal binds the exact normalized source digest, schema version, and
  `mindId`;
- create and update operations carry complete domain objects;
- update generation advances exactly once;
- link endpoints must exist and the final graph must close;
- duplicate identities, duplicate relations, and duplicate operations fail;
- proposed objects cannot arrive with canonical trust or authoritative writes;
- a `Model` cannot declare itself the whole `Mind`;
- output remains `eligible-for-review` and requires a later governed
  `PromotionTransaction`.

## Local validation

No hosted runner is required.

```bash
python modos/ontology/test_compiler.py
python ci/validate-change-proposals.py
python modos/ontology/compiler.py \
  --snapshot modos/ontology/fixtures/seed-snapshot.json \
  --proposal modos/ontology/fixtures/link-workspace.proposal.json \
  --out-snapshot /tmp/pleiades-candidate-snapshot.json \
  --out-receipt /tmp/pleiades-closure-receipt.json
```

The checked-in local validation receipt records the exact validated file hashes
and commands. It is review evidence only, never promotion authority.

## Runner-independent review evidence

Hosted Actions are optional and may be unavailable. Review does not infer a
green result from a queued or failed runner. Reproduce the checked-in receipt
locally, compare the recorded SHA-256 file identities, and attach any later
runner result as additional evidence rather than as the sole truth source.

## Derived read projections

`projection.py` converts an exact closed snapshot and closure receipt into a
deterministic `OntologyProjectionBundle`. The bundle is explicitly
non-canonical and forbids write-back.

`sql/001_ontology_projection.sql` creates a separate Postgres/Supabase read
schema with RLS enabled, consumer roles limited to `SELECT`, no consumer write
policies, and no `SECURITY DEFINER` mutation function. Publication remains a
privileged external operation bound to the exact compiled snapshot and receipt.
