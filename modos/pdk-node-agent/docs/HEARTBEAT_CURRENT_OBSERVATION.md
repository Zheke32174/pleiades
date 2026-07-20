# Durable heartbeat current-observation reads

This branch adds the read-side continuation of the durable heartbeat admission work.

## Implemented boundary

`ControllerHeartbeatReadStore` opens the same controller SQLite database as the authoritative heartbeat writer. It is a read/selection service over durable rows, not a second state authority and not an in-memory cache.

It provides:

- `latest_for_boot(node_id, boot_id)` — reconstructs the exact highest accepted signed heartbeat and original signed acknowledgement for one node/boot stream;
- `activate_boot_epoch(record)` — records an explicit monotonic controller-local boot transition only after at least one heartbeat from that boot has been durably accepted;
- `current_for_node(node_id)` — selects the latest observation from the explicitly active boot epoch inside one SQLite read transaction.

Every returned latest observation is checked against:

- the durable stream floor sequence;
- the durable stream floor digest and acceptance time;
- the stored signed envelope and acknowledgement;
- decoded node, boot, sequence, key, digest, and acknowledgement identity.

A floor that points to missing or contradictory content fails closed.

## Boot-epoch rule

Heartbeat arrival order does not determine node currentness.

A different `boot_id` may be admitted as durable history, but it does not become current until a monotonic `BootEpochRecord` is explicitly activated. Delayed heartbeats from an older boot therefore cannot silently replace the selected current observation.

Transition identity is idempotent. Reusing a transition ID with different content is a collision. A generation that does not advance the current generation is rejected as regression.

## Explicit non-claims

This branch does not add a gRPC read endpoint, consensus boot selection, live Alienware/Lenovo validation, or historical compaction.

Issue #25 remains open for the compaction policy and implementation. Compaction must preserve enough immutable sequence/digest identity to continue rejecting rollback and collision after old envelopes leave the full retry window. No accepted heartbeat rows are deleted by this branch.
