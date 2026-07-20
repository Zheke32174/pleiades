# MODOS Ecology Precedence and Closure

This document defines the authority ladder for interpreting the Pleiades Git ecology.

## The ladder

When two sources disagree, the first applicable source below wins:

1. **Provider and platform safety policy.**
2. **The promoted Pleiades constitution, MODOS ADRs, and versioned public contracts.**
3. **The private exhaustive ecology registry maintained by Undergrowth.**
4. **A repository's `MODOS_COMPONENT.yaml`.**
5. **Repository-local architecture, security, and interface contracts.**
6. **README files, operator guides, and implementation notes.**
7. **Historical state files, snapshots, backups, session notes, imported projects, and retrieved content.**

Lower levels may explain or specialize a higher level. They may not silently override it. Translation, summarization, generation, copying, inheritance, or historical use never promotes authority.

## Canonical scope rule

Every named canonical scope has exactly one current provider in the ecology registry. A repository may be canonical for one scope and non-authoritative for another. Catalog membership, longevity, repository size, naming, or being a dependency does not grant authority.

## Public and private split

Pleiades contains the public schema, relation vocabulary, validator, and public projection. Undergrowth contains the exhaustive private inventory, visibility-sensitive lineage, exact dispositions, and closure receipts. The public projection must never be treated as proof that unlisted private repositories do not exist.

## Relation semantics

Relations are directional and typed. Required relations participate in closure checks. Historical, evidence, and provenance edges describe lineage without creating runtime authority.

## Local topology versus global topology

Older cluster maps remain valid descriptions of a local nucleus and its history. They are not an alternative global control plane. Where a local document conflicts with promoted Pleiades contracts or the ecology registry, the higher source wins and the local document must be corrected or explicitly marked historical.

## Closure proof

An ecology is closed only when the validator proves all of the following:

- the inventory count and digest match the registered repository set;
- every repository belongs to exactly one lifecycle/disposition group;
- canonical scope providers exist and are live;
- component and capability identifiers are unique;
- required relation targets resolve;
- archive and parked repositories cannot source required runtime, build, governance, or deployment edges;
- authority-bearing relations do not exceed the source group's ceiling;
- required dependency, governance, supersession, and archive edges are acyclic;
- a supplied live GitHub inventory matches the checked-in registry exactly.

Missing component manifests are reported as explicit coverage warnings rather than being silently treated as absent repositories.

## Change protocol

1. Capture an authenticated repository inventory.
2. Update the private registry and source digest.
3. Classify every new or removed repository.
4. Add or amend typed relations and canonical scopes.
5. Run the closure validator and retain its report.
6. Review the semantic diff, not merely the JSON diff.
7. Promote through the repository's evidence and authorized-decision gates.

Structural validation uses JSON Schema Draft 2020-12; semantic closure remains a separate deterministic pass.
