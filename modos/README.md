# MODOS — Pleiades Operating-Domain Implementation

**MODOS** is the Modular Ontological Distributed Operating System implementation layer inside the larger Pleiades computing world.

Pleiades supplies the constitution, sovereignty model, convergent mind architecture, security laws, and governed evolutionary process. MODOS supplies the concrete operating-domain contracts and runtime mechanisms that let heterogeneous local computers participate as one logical device without concealing physical distribution.

## Boundary map

```text
Pleiades                 greater governed computing world
└── MODOS                modular ontological distributed OS implementation
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

## Current implementation slice

`pdk-node-agent/` contains the first Rust implementation skeleton for Alienware and Lenovo:

- Tokio asynchronous control loops;
- Tonic gRPC contracts and strict mTLS transport;
- Ed25519-signed durable protocol objects;
- five-state node autonomy;
- hardware/runtime inventory;
- direct systemd D-Bus transient units with no shell concatenation;
- signed capability and lease enforcement;
- SQLite WAL audit buffering and ordered reconciliation;
- controller, key generation, and administrative clients.

This slice is intentionally honest: it implements one authoritative controller and independent nodes. It does **not** claim two-node consensus. A later always-on third node can enable a genuine three-voter control plane.

## Repository policy

This public integration surface contains contracts and code safe for public review. The exhaustive cross-repository resource registry, private branches, backup lineage, and internal deployment bindings live in the private `undergrowth` resource spine.
