# Pleiades PDK Node Kernel Agent — Epoch 2 Rust Skeleton v0.2

This workspace is the first serious implementation draft of the Pleiades node-kernel-agent boundary for Alienware and Lenovo.

It takes the complete Gemini co-drafter packet and reconciles it against the Pleiades Unified Architecture, Operating Domain System, Upper-Domain Kernel, Context Immunity, and Ancestry/Failure papers.

The result is not a generic cluster agent. It is a local embodiment of the PDK that:

- remains explicit about connected, degraded, read-only, standalone, and quarantined operation;
- uses strict mTLS plus independent Ed25519 message signatures;
- emits replay-resistant signed heartbeats and accepts only signed ACKs;
- inventories the host rather than assuming its capabilities;
- caches only signed, scoped, expiring capability grants;
- gates execution deterministically before the runtime boundary;
- starts native workloads as hardened systemd transient units over D-Bus;
- never constructs a shell command;
- persists signed audit events in SQLite WAL;
- reconciles events sequentially and deletes them only after signed matching ACKs;
- terminates workloads when their capability leases expire;
- never presents the two-node estate as a fictional quorum; this slice uses one active authority and leaves observer replication as the next control-plane draft.

## Workspace

```text
crates/
├── pdk-protocol     canonical Protobuf/gRPC contracts
├── pdk-crypto       Ed25519 envelope signing and verification
├── pdk-transport    strict mTLS and certificate-identity interceptor
├── pdk-controller   authoritative heartbeat/event receiver
├── pdk-node-agent   autonomy, inventory, policy, leases, audit, systemd driver
├── pdk-admin        signed grant + bounded run/status/stop proof surface
└── pdk-keygen       protocol signing-key generator
```

## Node-agent modules

```text
autonomy.rs          explicit local-autonomy state machine
inventory.rs         sysinfo hardware polling and runtime probes
policy.rs            signed capability cache and deterministic authorization
leases.rs            capability expiry and forced workload termination
audit.rs             SQLite WAL signed event ledger
reconciliation.rs    sequential ACK-gated event drain
control_link.rs       mTLS Tonic client and ACK verification
heartbeat.rs          signed registration/heartbeat loop
rpc.rs                controller-facing authorization middleware
runtime/mod.rs        replaceable RuntimeDriver contract
runtime/systemd.rs    zbus StartTransientUnit implementation
```

## Read in this order

1. [`docs/GEMINI_CO_DRAFTER_SPEC.md`](docs/GEMINI_CO_DRAFTER_SPEC.md)
2. [`docs/DRAFTING_SYNTHESIS.md`](docs/DRAFTING_SYNTHESIS.md)
3. [`docs/ARCHITECTURE_ALIGNMENT.md`](docs/ARCHITECTURE_ALIGNMENT.md)
4. [`docs/SECURITY_INVARIANTS.md`](docs/SECURITY_INVARIANTS.md)
5. [`docs/BUILD_AND_BOOTSTRAP.md`](docs/BUILD_AND_BOOTSTRAP.md)
6. [`docs/STATIC_VALIDATION.md`](docs/STATIC_VALIDATION.md)
7. [`docs/SOURCE_PROVENANCE.md`](docs/SOURCE_PROVENANCE.md)
8. [`docs/COMPILATION_STATUS.md`](docs/COMPILATION_STATUS.md)

## Canonical sources used

- `pleiades_unified_architecture_and_construction_canon_v2.md`
- `pleiades_unified_architecture_and_construction_canon.md`
- `pleiades_operating_domain_system_blueprint.md`
- `pleiades_upper_domain_supercluster_kernel_blueprint.md`
- `pleiades_context_immunity_blueprint.md`
- `pleiades_ods_ancestry_and_failure_atlas.md`

The newer convergent-mind canon governs the greater architecture. This node agent remains on the deterministic authority side of that boundary: models and agents may propose work later, but only a valid PDK capability can cause local execution.

## Current boundary

This is the **node-agent slice**, not a claim that Epoch 2 is complete. The host-neutral scheduler, replicated observer, durable control state, full namespace, checkpointing, and third-voter transition remain subsequent work.

## Quick validation target

After build and enrollment, the first proof is:

```text
controller signs capability
        ↓
Lenovo validates mTLS + signature + lease + isolation
        ↓
Lenovo durably records authorization
        ↓
systemd starts a typed-argv transient unit
        ↓
Lenovo reports status and buffers signed evidence
        ↓
controller signs ACK
        ↓
Lenovo clears only the acknowledged event
```

See `BUILD_AND_BOOTSTRAP.md` for exact commands.
