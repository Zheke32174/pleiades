# Durable heartbeat continuity

The controller treats a signed heartbeat as an immutable identity, not merely a current-state update.

## Stream identity

A heartbeat stream is identified by:

- enrolled node identity;
- boot identity;
- monotonically increasing sequence.

The canonical content identity is the lowercase SHA-256 digest of the complete protobuf-encoded `SignedHeartbeat`, including key ID, payload, and source signature.

## Admission states

For one node, boot, and sequence, the controller permits only:

- **new** — the sequence is above the durable floor and the signed heartbeat is committed with its signed ACK;
- **idempotent** — the exact signed heartbeat already exists and the original stored ACK is returned;
- **collision** — the same sequence exists with different signed content;
- **replay** — an unseen heartbeat is at or below the durable stream floor;
- **storage failure** — no new acceptance is reported.

Every accepted heartbeat remains in the immutable identity table. A separate floor table records the latest accepted sequence and digest for each node/boot stream.

## Freshness and exact retry

Authentication, domain binding, mTLS identity, signing key enrollment, and signature verification always occur first.

After those checks:

1. the controller looks for an exact durable heartbeat identity;
2. an exact prior identity returns its original ACK even when the heartbeat timestamp is now outside the ordinary clock-skew window;
3. conflicting content under that sequence is rejected;
4. an unseen heartbeat must satisfy the current clock-skew policy before it may be admitted.

This distinction permits ACK recovery after response loss or controller restart without allowing unseen stale heartbeats to enter the stream.

## ACK binding

`HeartbeatAckPayload` binds:

- domain and controller identity;
- node and boot identity;
- accepted sequence;
- canonical signed-heartbeat digest;
- accepted time and suggested interval.

The node computes the heartbeat digest before sending and verifies the returned digest, identities, sequence, controller key, and signature before treating the controller response as authoritative.

## Persistence and concurrency

The local single-controller database uses:

- SQLite WAL;
- `synchronous=FULL`;
- a busy timeout;
- one heartbeat write-fence row;
- one transaction for immutable heartbeat identity, ACK, and stream-floor advancement.

Concurrent exact submissions produce one new admission and one idempotent result. Sequence rollback remains rejected after process restart.

## Observation cache

The in-memory latest-observation map is only a read cache. It is updated after durable admission or exact ACK recovery. The durable signed heartbeat table and stream floor are the continuity authority.

## Boundaries

This checkpoint does not create multi-controller consensus, a command channel, a capability grant, remote policy mutation, or global liveness truth. A heartbeat proves only that one enrolled node submitted one authenticated observation that this controller durably admitted.
