# Pleiades Operator Handoff Compiler

This directory contains the repository-side preparation layer between a clean Pleiades convergence checkpoint and real sovereign or live intervention.

It does **not** ingest raw private registries, credentials, private keys, node secrets, or execution payloads. Public GitHub receives only opaque references, SHA-256 digests, explicit decisions, bounded selections, and proposal state.

## Inputs

`OperatorInputCandidate` binds eight evidence classes:

- exhaustive private ecology;
- authenticated observed inventory;
- live node/capability inventory;
- public signing identity and issuer provenance;
- history-rewrite decision evidence;
- delegated-authority grant proposal evidence;
- canary and rollback plan evidence;
- sustained-observation plan evidence.

Each supplied input must provide an opaque artifact reference, artifact digest, and receipt digest. Unsupplied inputs must contain no bindings. Non-public inputs must use `urn:pleiades:` references rather than public paths or URLs.

## Outputs

`intake.py` emits only preparation plans:

- private-closure candidate;
- history decision record;
- node-admission candidate;
- grant-issuance proposal;
- canary-admission plan;
- observation-window plan;
- next-progression candidate.

Every output carries `executionApplied=false` and `canonicalMutationApplied=false`. A fully satisfied candidate becomes `ready-to-derive-next-progression`; it still does not authorize or perform any action.

## Safety boundary

The compiler rejects:

- embedded payloads;
- private-key material;
- secret-like token patterns;
- non-opaque references for private, sovereign, or live evidence;
- supplied inputs missing exact digest bindings;
- unsupplied inputs retaining bindings;
- history decisions without sovereign evidence;
- canary selections without node and rollback-plan evidence;
- observation windows without an observation-plan receipt.

The synthetic fixture contains no real private identities and cannot satisfy the actual operator frontier.
