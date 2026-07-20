# Proposal-only ontology compiler and promotion-evidence gate

This directory contains deterministic compilation and review-evidence seams beneath the `ChangeProposal` contract.

The compiler accepts one exact `OntologySnapshot` and one authority-free `ChangeProposal`. It produces a candidate snapshot and an `OntologyClosureReceipt`. It does **not** promote, sign, deploy, admit, or make the result canonical.

The promotion-evidence gate accepts the exact candidate snapshot, closure receipt, source manifest, and promotion candidate. It produces an `OntologyPromotionGateReport`. It also does **not** promote, sign, deploy, admit, or make the result canonical.

## Determinism and refusal rules

- strict UTF-8 JSON with duplicate keys, floats, NaN, and infinity refused;
- canonical JSON uses sorted keys, compact separators, and direct Unicode;
- source snapshots are normalized by object identity and relation identity;
- every proposal binds the exact normalized source digest, schema version, and `mindId`;
- create and update operations carry complete domain objects;
- update generation advances exactly once;
- link endpoints must exist and the final graph must close;
- duplicate identities, duplicate relations, duplicate operations, source artifacts, and governance evidence fail;
- proposed objects cannot arrive with canonical trust or authoritative writes;
- a `Model` cannot declare itself the whole `Mind`;
- placeholder all-zero SHA-256 values are refused by promotion-evidence contracts;
- source manifest, candidate, receipt, semantic diff, branch, and exact commit must bind;
- output remains `blocked` or `eligible-for-steward-review` and requires a later governed, signed `PromotionTransaction`.

## Local validation

No hosted runner is required.

```bash
python modos/ontology/test_compiler.py
python modos/ontology/test_projection.py
python modos/ontology/test_promotion.py
python ci/validate-change-proposals.py
python ci/validate-promotion-evidence.py

python modos/ontology/compiler.py \
  --snapshot modos/ontology/fixtures/seed-snapshot.json \
  --proposal modos/ontology/fixtures/link-workspace.proposal.json \
  --out-snapshot /tmp/pleiades-candidate-snapshot.json \
  --out-receipt /tmp/pleiades-closure-receipt.json

python modos/ontology/promotion.py \
  --snapshot modos/ontology/fixtures/expected-candidate-snapshot.json \
  --receipt modos/ontology/fixtures/expected-closure-receipt.json \
  --manifest modos/ontology/fixtures/source-manifest.json \
  --candidate modos/ontology/fixtures/promotion-candidate.json \
  --out-report /tmp/pleiades-promotion-gate-report.json
```

The checked-in local validation receipt records exact validated file hashes and commands for the compiler/projection slice. The promotion-evidence fixtures separately pin the exact PR #52 subject commit and artifact identities. Both are review evidence only, never promotion authority.

## Runner-independent review evidence

Hosted Actions are optional and may be unavailable. Review does not infer a green result from a queued or failed runner. Reproduce the checked-in receipts and golden fixtures locally, compare the recorded SHA-256 identities, and attach any later runner result as additional evidence rather than as the sole truth source.

## Current explicit blocker

`promotion-candidate.json` retains `github:Zheke32174/pleiades#42` in `blockingIssues`. Consequently, `expected-promotion-gate-report.json` is deterministically `blocked`. This is intentional: the evidence gate carries unresolved history-cleanup work forward instead of silently losing it.

## Derived read projections

`projection.py` converts an exact closed snapshot and closure receipt into a deterministic `OntologyProjectionBundle`. The bundle is explicitly non-canonical and forbids write-back.

`sql/001_ontology_projection.sql` creates a separate Postgres/Supabase read schema with RLS enabled, consumer roles limited to `SELECT`, no consumer write policies, and no `SECURITY DEFINER` mutation function. Publication remains a privileged external operation bound to the exact compiled snapshot and receipt.
