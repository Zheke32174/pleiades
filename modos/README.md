# MODOS — Pleiades Operating-Domain Contracts

**MODOS** is the Modular Ontological Distributed Operating System implementation layer inside the larger Pleiades computing world.

Pleiades supplies the constitution, sovereignty model, convergent-mind architecture, security laws, and governed evolutionary process. MODOS supplies concrete operating-domain contracts that allow heterogeneous repositories, nodes, services, agents, and artifacts to participate in one logical ecology without concealing their physical or administrative boundaries.

## Boundary map

```text
Pleiades                 greater governed computing world
├── public MODOS contracts and validators
├── private ecology/resource spine (Undergrowth)
└── MODOS runtime implementation
    ├── PDK              deterministic over-kernel / domain kernel
    ├── node agents      local kernel representatives and policy enforcers
    ├── domain objects   typed identity-bearing compute/data/service objects
    ├── adapters         Linux, Windows, Android, containers, VMs, networks
    ├── Atlas            belief/world-state integration
    ├── Forge            governed authority and action synthesis
    └── harness organs   agents, models, memory, evaluation, simulation
```

## Non-negotiable laws

1. Local kernels remain sovereign over local hardware.
2. Every joined node remains useful during domain loss.
3. The domain presents one logical device without dishonest transparency.
4. No ambient authority: capabilities are explicit, scoped, signed, and expiring.
5. Models may propose; deterministic policy disposes.
6. Transformation never launders trust or authority.
7. Desired state is declarative and reconciled.
8. Failure and partition are ordinary object states.
9. Consequential actions retain provenance, authorization evidence, and rollback paths.
10. Canon changes are promoted from isolated branches only after evidence and review.
11. Catalog membership, ancestry, naming, or persistence never grants authority.
12. Every repository is either classified in the ecology or treated as an unresolved closure defect.
13. Convergence never silently erases provenance, active dissent, or a registered distinction.

## Ecology contract

The public ecology foundation consists of:

- `contracts/component-manifest.schema.json` — component identity, authority, lifecycle, capabilities, and typed relations;
- `contracts/ecology-registry.schema.json` — exhaustive inventory, grouping, canonical scopes, capability ownership, and graph edges;
- `ecology/PRECEDENCE.md` — the authority ladder and supersession rules;
- `ecology/public-ecology.json` — a non-exhaustive public projection used as a validation fixture;
- `../ci/validate-ecology.py` — deterministic structural and semantic closure checks.

The exhaustive private registry lives in Undergrowth. A repository-scoped GitHub Actions token cannot prove the complete private account inventory, so exact live-inventory comparison must run in the private spine or with a separately delegated read-only inventory credential. The public validator itself is network-independent and accepts an exported observed inventory.

## Epistemic governance contract

The first public ontological self-criticism layer consists of:

- `contracts/distinction-registry.schema.json` — executable non-equivalence, middle-space, competency-question, counterexample, and collapse-hazard contract;
- `contracts/epistemic-ledger.schema.json` — evidence, claim, dependency, revision, argument, confidence, decision, and dissent contract;
- `ontology/distinctions.json` — initial cross-domain distinction registry;
- `ontology/epistemic-ledger.example.json` — reference Atlas/Forge-compatible ledger;
- `../ci/validate_epistemic_governance.py` — deterministic semantic checks and grounded argument observability;
- `../ci/test_epistemic_governance.py` — regression proofs against silent collapse and erased dissent.

The validator does not decide whether a proposition is true. It proves that category-sensitive reasoning retains the provenance, alternatives, distinctions, attacks, and explicit promotion record needed to evaluate and revise it.

## Repository policy

The public integration surface contains contracts and code safe for public review. Private branches, visibility-sensitive lineage, backup identities, evidence stores, and internal deployment bindings stay in the private ecology spine. Public absence is never interpreted as private nonexistence.
