# Architecture Alignment

This workspace implements the **Epoch 2 node-kernel-agent slice**, not the whole Pleiades Operating Domain System.

| Canonical requirement | Implementation |
|---|---|
| Each node remains locally useful | `AutonomyStateMachine` separates Connected, degraded, read-only, standalone, and quarantined behavior. |
| No false two-node quorum | Controller ACKs declare `single-authoritative-controller`; observer replication and failover are explicitly left unimplemented rather than implied. |
| Cryptographic enrollment | mTLS certificate fingerprint + URI SAN + role binding, plus independent Ed25519 message signatures. |
| Signed heartbeat | Protobuf payload, domain/boot/sequence/time binding, replay rejection, signed ACK. |
| Explicit physical reality | `InventoryManager` reports CPU, RAM, disks, network, OS, architecture, uptime, runtimes, GPU presence, power class, and trust zone. |
| No ambient authority | `PolicyEnforcer` admits only signed, scoped, expiring capability grants. |
| Deterministic authority before execution | RPC layer authorizes and durably audits before invoking `RuntimeManager`. |
| Native bounded process driver | `SystemdDriver` calls `StartTransientUnit` over zbus with typed properties and argv. |
| No shell concatenation | No shell is invoked anywhere in the runtime path. |
| Local forensic continuity | `OfflineAuditBuffer` uses SQLite WAL and signed protobuf event envelopes. |
| Reconciliation after partition | `ReconciliationWorker` drains in order only while Connected and deletes only after a verified signed ACK. |
| Lease enforcement | `LeaseManager` purges expired grants and stops attached workloads. |
| Stable contracts, replaceable mechanisms | Protobuf contracts and the `RuntimeDriver` trait isolate the systemd implementation from PDK semantics. |

## Deliberately not claimed

The workspace does **not** yet provide:

- a production consensus store;
- observer state replication or automated failover;
- a scheduler that chooses Alienware versus Lenovo without a named target;
- SPIFFE/SPIRE enrollment;
- container, VM, notebook, model, or Windows drivers;
- durable controller metadata;
- checkpointing and migration;
- the complete domain namespace.

Those remain later Epoch 2/Epoch 3 work. The present deliverable is the executable trust, autonomy, inventory, runtime, lease, and audit skeleton upon which those pieces can safely attach.
