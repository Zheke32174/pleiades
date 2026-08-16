# MODOS Convergence Artifact Layout

All generated evidence belongs under an untracked `artifacts/` directory. No validator writes into canonical contract, fixture, source, or policy paths.

## Required layout

```text
artifacts/
├── contract-catalog.json
├── stack-closure-receipt.json
├── public-ecology-closure.json
├── public-ecology-ontology.json
├── public-ecology-ontology-receipt.json
├── convergence-suite-receipt.json
├── current-tree-sensitivity-receipt.json
├── reachable-history-sensitivity-receipt.json
├── synthetic-rehearsal-receipt.json
├── intervention-frontier.json
├── pleiades-modos-validation.tar.gz
└── validation-package-receipt.json
```

## Evidence rules

- Every JSON receipt is UTF-8, sorted-key, indented JSON ending in one newline.
- Canonical digests use compact sorted-key UTF-8 JSON and SHA-256.
- Generated receipts are evidence, never authority.
- A workflow result is additive evidence; queued, cancelled, or unavailable hosted runners are never treated as a pass.
- Current-tree sensitivity must be clear before publication.
- Reachable-history sensitivity may remain blocked only when explicitly carried as issue `github:Zheke32174/pleiades#42`.
- Public ecology compilation must retain the missing-private-registry blocker.
- Synthetic rehearsal must retain all live-operation blockers.
- Validation packages must contain no private key material, credentials, private registries, local absolute paths, or live topology.

## Package contents

The reproducible validation package includes:

- public schemas and contracts;
- deterministic validators and test modules;
- public ecology projection and precedence rules;
- ontology and governance source needed by the convergence suite;
- synthetic fixtures only;
- runtime matrix, progression ledgers, and operator runbooks;
- package manifest and CycloneDX SBOM.

It deliberately excludes:

- `.git` and reachable history;
- `artifacts/` from prior runs;
- caches and build directories;
- private ecology data;
- secrets and signing material;
- machine-specific state;
- live deployment configuration.

## Retention

Hosted workflow artifacts may use a finite review retention period. Long-term evidence selected for preservation belongs in the private evidence spine, referenced by digest from public promotion records when appropriate. Moving evidence into private retention does not alter its original digest or authority class.
