# Pleiades Operator Handoff Compiler

This directory contains the repository-side preparation layer between a clean Pleiades convergence checkpoint and real sovereign or live intervention.

It does **not** ingest raw private registries, credentials, private keys, node secrets, or execution payloads. Public GitHub receives only opaque references, SHA-256 digests, explicit decisions, bounded selections, and proposal state.

## Empty template

`template.py` produces a deterministic, schema-valid candidate with every evidence slot unsupplied, every private/live binding null, the history decision pending, and all outputs requested. The operator fills references and digests outside public GitHub, then supplies only the authorized opaque candidate.

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

## Compiled preparation plans

`intake.py` emits only preparation plans:

- private-closure candidate;
- history decision record;
- node-admission candidate;
- grant-issuance proposal;
- canary-admission plan;
- observation-window plan;
- next-progression candidate.

Every output carries `executionApplied=false` and `canonicalMutationApplied=false`. A fully satisfied candidate becomes `ready-to-derive-next-progression`; it still does not authorize or perform any action.

## Bound handoff packet

`packet.py` binds the exact candidate and compilation receipt to:

- the branch convergence evidence digest;
- the intervention-frontier receipt digest;
- repository readiness state;
- ready and blocked preparation plans;
- exact operator/live actions;
- the matching numbered runbook sections.

Repository failure always takes precedence over operator readiness. A stale candidate, tampered receipt, failed convergence suite, non-clear current tree, missing validation package, or unresolved input prevents a review-ready packet.

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
- observation windows without an observation-plan receipt;
- candidate, convergence, or frontier receipts whose self-digests do not reproduce.

The synthetic fixtures contain no real private identities and cannot satisfy the actual operator frontier.
