# Promotion review-eligibility bundles

A `PromotionReviewEligibilityBundle` is the strongest result the Factory evidence layer may produce. It is an immutable, content-addressed statement that one exact run and one exact evidence set either:

- satisfy the declared gates and are **eligible for governed promotion review**; or
- remain **blocked** by explicit derived blockers.

It is not approval, promotion, deployment, merge permission, trust elevation, or canon mutation. A later signed `PromotionTransaction` must reference the exact bundle and decision digests before any governed change can proceed.

## Object boundary

The bundle contains four evidence layers:

1. **Run manifest** — immutable run and normalized work-order identity, fixed-point criteria, conservative aggregation policy, reproducibility threshold, and rollback requirement.
2. **Observation records** — immutable criterion evidence with fixed-point scores, recorder identity, independent-verification status, exact evidence references, optional correction lineage, and a canonical content digest.
3. **Evaluation generation** — exact selected evidence, derived criterion status, reproducibility and rollback evidence, safety findings, blockers, verdict, input digest, and decision digest.
4. **Bundle integrity** — one digest over the complete transfer object.

Every authority ceiling in this layer is `none`. The bundle sets `promotionTransactionRequired: true`, and the schema does not contain approval, rollout, deployment, capability, or signature fields.

## Canonical identity

The contract uses the same narrow `modos-canonical-json-v1` rules as observation ingress:

- UTF-8;
- sorted object keys;
- compact separators;
- direct Unicode output;
- finite integer-only values;
- no binary floats, NaN, or infinity.

SHA-256 identities use lowercase `sha256:<64hex>` strings.

### Observation digest

Calculate `contentDigest` over the complete observation with `contentDigest` temporarily set to the empty string.

### Evaluation input digest

Calculate `inputDigest` over:

- the complete run manifest;
- the complete ordered observation array;
- criterion results;
- reproducibility value and evidence references;
- rollback result and evidence references;
- safety violations and evidence references.

The verdict, blockers, evaluator identity, and evaluation timestamp are excluded from the input material so the decision can be recomputed from the same evidence.

### Decision digest

Calculate `decisionDigest` over the complete evaluation with `decisionDigest` temporarily set to the empty string.

### Bundle digest

Calculate `integrity.bundleDigest` over the complete bundle with that field temporarily set to the empty string.

## Conservative evidence aggregation

Version 1 uses only `all-valid-observations-pass`.

For each criterion, the evaluation must select every observation for that criterion in bundle order. A later passing observation cannot hide an earlier failure. A correction record may name the exact earlier digest and explain the correction, but negative evidence remains visible and continues to block under this initial conservative policy.

A required criterion passes only when every selected observation:

- claims pass;
- meets its fixed-point threshold; and
- records independent verification.

No observations means `inconclusive`, which blocks a required criterion.

## Fixed-point values

Promotion-affecting numeric values use millionths:

- `0` means 0%;
- `750000` means 75%;
- `1000000` means 100%.

This removes binary-float ambiguity from cross-language digests.

## Immutable generations

Generation 1 has no predecessor. Every later generation must name the exact previous `decisionDigest`. New evidence creates a new bundle generation; it never overwrites or erases an earlier verdict.

Exact retry of unchanged material should reproduce the same input, decision, and bundle digests. Timestamps and generation identity should therefore be assigned once and persisted before publication.

## Derived blockers

The validator derives blockers in deterministic order:

1. each required non-passing criterion, in manifest order, as `criterion:<criterion-id>`;
2. `reproducibility` when the measured value is below the manifest threshold;
3. `rollback-not-tested` when rollback is required but untested;
4. `safety-violation` when any safety violation is present.

The bundle must contain exactly the derived blocker list. An empty list yields `eligible-for-promotion-review`; any blocker yields `blocked`.

## Factory implementation obligations

A conforming Factory implementation should:

- stage and atomically publish one immutable run manifest;
- verify the manifest digest before accepting evidence;
- serialize observation append and generation allocation;
- verify every observation digest while loading;
- use complete writes, mode 0600, file fsync, atomic replacement, and directory fsync;
- store decisions under generation-and-digest names rather than overwrite `decision.json`;
- preserve negative and superseded observations;
- return exact retry identities for unchanged evaluation inputs;
- expose the current generation as a pointer only, never as the sole copy;
- prevent an eligibility verdict or process exit code from being interpreted as a signed promotion transaction.

## Deliberate exclusions

This contract creates no execution engine, model invocation, approval, merge, release, deployment, capability grant, policy mutation, trust promotion, or canon authority.
