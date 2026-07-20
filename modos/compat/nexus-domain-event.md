# Nexus → MODOS `SignedDomainEvent` Compatibility

The existing Pleiades Nexus ledger is preserved. MODOS does not replace it by renaming tables or rewriting historical evidence. A compatibility adapter wraps each emitted Nexus record in a canonical signed domain-event envelope.

## Adapter boundary

```text
existing service / Nexus producer
            │
            ▼
      original Nexus record
            │
            ├── stored unchanged in its current ledger
            │
            ▼
NexusDomainEventAdapter
  - canonical event type
  - source identity
  - source record reference
  - digest of original record
  - trace and causal references
  - trust / visibility / lineage
            │
            ▼
SignedDomainEvent
            │
     local WAL / domain stream
```

## Required mapping

| MODOS field | Nexus-derived value |
|---|---|
| `eventId` | New stable MODOS event ID. Do not reuse a mutable database row offset. |
| `domainId` | Configured operating-domain identity. |
| `sourceIdentity` | Enrolled service, node, or adapter principal that observed/emitted the record. |
| `sourceBootId` | Current node boot ID when available. |
| `createdAt` | Original event time when trustworthy; otherwise adapter observation time with the distinction recorded in `body`. |
| `traceId` | Existing Nexus trace/correlation ID or a newly created trace linked to the source record. |
| `eventType` | Namespaced canonical type, for example `nexus.defensive.observation` or `nexus.workload.status`. |
| `sequence` | Monotonic per source identity and boot/stream scope. |
| `body` | Lossless structured representation or a stable reference when the original payload is too large or sensitive. |
| `provenance.sourceRef` | Immutable ledger/table/object reference to the original Nexus record. |
| `provenance.sourceDigest` | Digest calculated over the canonical serialization of the original record. |
| `provenance.trust` | Never higher than the source record and collector identity justify. |
| `provenance.visibility` | At least as restrictive as the original data. |
| `signature` | Ed25519 signature by the enrolled adapter/service identity. |

## Non-negotiable rules

1. The adapter is append-only; it does not rewrite the source ledger.
2. Transformation never upgrades trust, visibility, or authority.
3. Large payloads become content-addressed artifact references rather than silently truncated bodies.
4. Secret-bearing records are not copied to public event streams.
5. Adapter failures are buffered locally and retried in order.
6. Duplicate source records produce idempotent event identities or explicit duplicate links.
7. A domain ACK confirms receipt of the MODOS envelope, not deletion of the original Nexus evidence.
8. Event consumers must be able to resolve the original source reference when authorized.

## Initial event namespaces

- `nexus.defensive.*`
- `nexus.agent.*`
- `nexus.workload.*`
- `nexus.artifact.*`
- `nexus.security.*`
- `nexus.system.*`
- `nexus.steward.*`

The actual inventory must be generated from current Nexus producers before implementation. Unknown types remain namespaced as `nexus.legacy.<source-type>` with their original type preserved in the body.

## Promotion path

1. Inventory every current Nexus producer and record shape.
2. Produce a mapping table and representative fixtures.
3. Implement the adapter behind a feature flag.
4. Run dual-write comparison without changing existing consumers.
5. Verify digest stability, replay behavior, visibility handling, and restart recovery.
6. Promote consumers gradually to the MODOS envelope while preserving the original ledger as provenance.
