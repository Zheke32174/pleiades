# MODOS — Pleiades Operating-Domain Contracts and Runtime

**MODOS** is the Modular Ontological Distributed Operating System implementation layer inside the larger Pleiades computing world.

Pleiades supplies the constitution, sovereignty model, convergent-mind architecture, security laws, and governed evolutionary process. MODOS supplies both the public operating-domain contracts and the concrete runtime mechanisms that allow heterogeneous repositories, nodes, services, agents, and artifacts to participate in one logical ecology without concealing physical or administrative boundaries.

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
5. Models are differentiated cognitive organs; the persistent recurrent organization is the Mind.
6. Delegated machine executive authority may decide and act inside promoted bounded grants.
7. Transformation never launders trust or authority.
8. Desired state is declarative and reconciled.
9. Failure and partition are ordinary object states.
10. Consequential actions retain provenance, authorization evidence, and rollback paths.
11. Canon changes are promoted from isolated branches only after evidence and authorized decision.
12. Catalog membership, ancestry, naming, or persistence never grants authority.
13. Every repository is classified in the ecology or treated as an unresolved closure defect.

## Ecology contract

The public ecology foundation consists of:

- `contracts/component-manifest.schema.json` — component identity, authority, lifecycle, capabilities, and typed relations;
- `contracts/ecology-registry.schema.json` — inventory, grouping, canonical scopes, capability ownership, and graph edges;
- `ecology/PRECEDENCE.md` — authority ladder and supersession rules;
- `ecology/public-ecology.json` — non-exhaustive public projection used as a validation fixture;
- `../ci/validate-ecology.py` — deterministic structural and semantic closure checks.

The exhaustive private registry lives in Undergrowth. Public absence is never interpreted as private nonexistence. Exact live-inventory comparison requires an exported authenticated inventory or a separately delegated read-only inventory credential.

## Current runtime implementation

`pdk-node-agent/` contains the Rust implementation slice for Alienware and Lenovo:

- Tokio asynchronous control loops;
- Tonic gRPC contracts and strict mTLS transport;
- Ed25519-signed durable protocol objects;
- five-state node autonomy;
- hardware/runtime inventory;
- direct systemd D-Bus transient units with no shell concatenation;
- signed capability and lease enforcement;
- SQLite WAL audit buffering and ordered reconciliation;
- controller, key-generation, and administrative clients.

This slice implements one authoritative controller and independent nodes. It does not claim two-node consensus. A later always-on third node can enable a genuine three-voter control plane.

## Repository policy

This public integration surface contains contracts and code safe for public review. Private branches, visibility-sensitive lineage, backup identities, evidence stores, and internal deployment bindings stay in the private ecology spine.
