# Pleiades PDK Node Kernel Agent — Rust Implementation Specification

**Target:** Primary Rust skeleton for the PDK node agent operating on Alienware and Lenovo nodes  
**Language:** Stable Rust  
**Async runtime:** Tokio  
**RPC framework:** Tonic gRPC  
**Status:** Reconstructed from the complete reverse-ordered co-drafter packet and normalized against the Pleiades architecture papers.

## 1. Core State Machine and Autonomy Protocol

The agent is the local embodiment of the domain kernel. It must not panic or cease useful local operation merely because it loses the control plane. It transitions through explicit states:

```text
Connected
DegradedAutonomous
ReadOnlySafe
Standalone
Quarantined
```

Required behavior:

- A nonblocking Tokio heartbeat task sends signed heartbeats at fixed intervals.
- Failure to receive a cryptographically valid ACK within the configured threshold moves the node atomically to `DegradedAutonomous`.
- A longer authority loss can move the node to `ReadOnlySafe`.
- New global capability grants are denied outside `Connected`.
- Singleton destructive operations are denied outside `Connected`.
- Existing locally recoverable work may continue only under valid cached policy and unexpired leases.

**Co-drafter task:** Implement the main Tokio event loop, `AutonomyStateMachine`, explicit transition logic, and deterministic request denials.

## 2. Cryptographic Identity and gRPC Transport

The domain operates with zero ambient network authority.

Required behavior:

- Every control-plane RPC uses strict mutual TLS.
- The two-node MVP uses a strict local CA bootstrap; SPIFFE/SPIRE SVIDs remain the later target.
- A Tonic interceptor extracts the peer certificate identity, validates its enrolled fingerprint and URI SAN, enforces the required role, and attaches a typed identity to request extensions.
- The signed message identity is checked against the mTLS identity.
- Node and controller Ed25519 signing keys remain distinct from TLS keys.
- Private keys are rejected if group- or world-readable.

**Co-drafter task:** Implement Tonic client/server initialization, mTLS identity interception, and secure key/trust-bundle loading.

## 3. Resource Inventory and Telemetry

The over-kernel needs an explicit representation of physical reality before scheduling either node.

Required behavior:

- Poll CPU topology and usage, total/available memory, disks, operating system, kernel, architecture, uptime, and network counters.
- Probe approved absolute paths to determine whether systemd, Podman, and libvirt are actually available.
- Do not infer runtime availability merely from configuration.
- Serialize the exact `NodeInventory` protobuf during initial registration and later heartbeats.
- Preserve power class and trust zone as placement facts.

**Co-drafter task:** Implement `InventoryManager` and the canonical `NodeInventory` payload.

## 4. The systemd Execution Driver

The first runtime driver executes native isolated processes using systemd transient units.

Absolute rule:

> No shell concatenation.

Required interface:

```text
prepare()
start()
status()
stop()
cleanup()
```

Required behavior:

- Use zbus to call the systemd D-Bus API directly.
- Represent the executable and arguments as a typed `ExecStart` array, never one shell string.
- Map workload constraints to transient-unit properties before start, including:
  - `DynamicUser`
  - `ProtectSystem`
  - `ProtectHome`
  - `PrivateTmp`
  - `PrivateNetwork`
  - `NoNewPrivileges`
  - `RestrictSUIDSGID`
  - `RestrictAddressFamilies`
  - empty capability and ambient-capability sets
  - `MemoryMax`
  - `CPUQuotaPerSecUSec`
  - a dedicated cgroup slice
- Require absolute executable and working-directory paths.

**Co-drafter task:** Implement `SystemdDriver` behind the `RuntimeDriver` trait.

## 5. Local Audit and Telemetry Buffer

When a node loses the control plane, forensic evidence must remain durable locally and reconcile later.

Required behavior:

- Use SQLite in WAL mode.
- Store a signed `DomainEvent` envelope containing event ID, timestamp, trace ID, event type, payload, source node, and signature.
- Persist before a consequential operation crosses the runtime boundary.
- A reconciliation worker watches for `Connected`, sends buffered events sequentially over gRPC, and deletes local rows only after verifying a signed controller ACK for that exact event ID.
- Retry failures without reordering or silently discarding events.

**Co-drafter task:** Implement `OfflineAuditBuffer::queue_event()` and `ReconciliationWorker`.

## 6. Local Policy and Capability Cache

The node cannot ask the control plane for permission for every micro-action, but it also cannot obey requests blindly.

Required behavior:

- Maintain a thread-safe in-memory registry of signed, time-bounded capability grants.
- The registry is a cache, not an authority source; every grant is verified against an enrolled controller key.
- New grants require `Connected` state.
- Before `RuntimeDriver::start()` or `stop()`, the deterministic gate checks:
  - mTLS identity and signed issuer agreement;
  - domain and target node;
  - key ID and Ed25519 signature;
  - issued/not-before/expiry times;
  - token, lease, action, and workload subject;
  - singleton-destructive restriction;
  - requested isolation is not weaker than the signed isolation floor.
- An async lease sweeper purges expired grants and force-stops workloads tied to expired tokens.

**Co-drafter task:** Implement `PolicyEnforcer`, `LeaseManager`, and the authorization middleware for `spawn_workload`, `stop_workload`, and status.

## 7. Two-node authority rule

Alienware and Lenovo form one governed domain, but they are not represented as a false two-voter quorum.

```text
Alienware: one authoritative active controller
Lenovo: replicated observer / explicit failover target
Later PS node: third voter enabling genuine three-member quorum
```

The node-agent protocol must remain topology-neutral so the later transition does not require a rewrite.

## 8. Required evidence

The implementation must make these claims testable:

- a signed heartbeat is rejected when the mTLS node identity differs;
- a replayed sequence is rejected;
- a stale or future grant is rejected;
- a spawn request cannot reach the runtime driver without authorization;
- argv never crosses a shell parser;
- a network-denied workload maps to `PrivateNetwork=true`;
- an expired lease terminates its active workload;
- a queued event survives restart and is removed only after a signed matching ACK;
- disconnecting Lenovo changes its state without destroying local audit or approved existing work.
