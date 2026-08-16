# Co-Drafter Synthesis and Architectural Decisions

Gemini's packet identified the correct implementation seam. The Pleiades papers supplied the laws needed to prevent a superficially working skeleton from contradicting the greater architecture.

## Decisions retained directly

- Stable Rust, Tokio, Tonic, sysinfo, zbus, SQLite/WAL.
- Explicit five-state autonomy model.
- Signed heartbeats and a 15-second degraded threshold.
- Strict mTLS with a local CA now and SPIFFE/SPIRE later.
- Direct systemd D-Bus transient units.
- Thread-safe capability cache.
- Lease sweeper that terminates timed-out workloads.
- Sequential offline-event reconciliation with cryptographic ACKs.

## Decisions strengthened during synthesis

### 1. mTLS identity is bound to fingerprint and URI SAN

A CA-valid certificate alone is not sufficient enrollment. The interceptor checks:

```text
CA trust
+ exact SHA-256 leaf fingerprint
+ required URI SAN
+ required role
```

The signed payload principal must then equal the mTLS principal.

### 2. TLS signatures and protocol signatures are separate

Transport authenticates the channel. Ed25519 authenticates durable protocol objects that may be stored, replay-checked, audited, and reconciled after the connection disappears.

### 3. Heartbeat ACKs are signed

The node does not return to `Connected` because any endpoint answered. It returns only after verifying a controller signature over its domain, node, boot ID, and exact sequence.

### 4. Capability isolation is a floor, not a suggestion

The wire field `maximum_isolation` is defined safely as a mandatory isolation floor. A workload request may strengthen restrictions but may not weaken them.

### 5. Authorization is durably recorded before execution

```text
authenticate peer
→ validate signed grant
→ validate lease/action/subject/state/isolation
→ persist signed authorization event
→ invoke runtime driver
→ persist result
```

If the post-start result cannot be persisted, the agent stops the newly launched workload fail-closed.

### 6. Reconciliation is ACK-gated and ordered

A successful TCP or gRPC return is not enough. The event remains in SQLite until the node verifies a signed ACK naming the exact event ID.

### 7. Partition semantics are stateful rather than binary

The implementation distinguishes initial/unacknowledged operation, degraded autonomy, read-only safety, deliberate standalone operation, and quarantine.

### 8. Two machines do not become two-voter HA by declaration

The controller reports its authority mode literally:

```text
single-authoritative-controller
```

Observer replication is deliberately not claimed by this node-agent slice. The protocol remains topology-neutral so a later Lenovo observer and eventual PS-node three-voter control plane do not require replacing node identity, heartbeat, capability, workload, or audit envelopes.

## Next co-drafting packet

After this slice compiles and runs, the next draft is the Epoch 2 scheduler and observer-replication contract:

1. authoritative desired-state schema;
2. node liveness and inventory view;
3. hard placement filters;
4. explainable scoring;
5. signed workload binding;
6. observer replication format;
7. explicit manual failover transaction;
8. later migration of the same contract onto three-voter consensus.
