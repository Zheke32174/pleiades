# Durable event admission continuity

The controller must not acknowledge a node event until the exact signed envelope and the exact signed acknowledgement are durable in one SQLite transaction.

## Identity

The durable identity is the canonical protobuf encoding of the complete `SignedDomainEvent`, including:

- enrolled signing key ID;
- exact domain-event payload;
- source signature.

Its external identity is lowercase `sha256:<64hex>`. `EventAckPayload` binds the event ID, source node ID, and this digest.

## Admission states

For one event ID, the controller permits only:

- **new** — no durable identity exists; insert the signed envelope and signed ACK atomically;
- **idempotent** — the durable envelope is byte-identical; return the original stored ACK;
- **collision** — the event ID exists with any different signed envelope; reject and return no ACK;
- **storage failure** — the transaction did not commit; return retryable unavailability and no ACK.

Connection success, signature verification, an event ID lookup, or construction of an ACK in memory is not admission.

## Node deletion boundary

Before acknowledging its local audit buffer, the node verifies:

- domain identity;
- trusted controller and key identity;
- event ID;
- source node identity;
- canonical signed-envelope digest;
- controller signature.

Only then may the existing event-ID removal path delete the local queue record.

## Crash and retry behavior

The controller uses SQLite WAL, `synchronous=FULL`, a busy timeout, and a write-fence row acquired before identity lookup.

- response loss after commit causes exact retry to return the original ACK;
- restart preserves accepted identity and ACK bytes;
- concurrent exact retries create one row;
- concurrent or later conflicting content is rejected;
- failed insertion leaves no accepted row and exposes no signed success response.

## Boundaries

This checkpoint persists signed domain-event admission only. Heartbeat replay floors and latest observations remain in-memory and are owned by issue #17. Shared Windows/Android observation batches remain governed by issue #19 and PR #20. The controller database is local single-controller continuity evidence, not distributed consensus or quorum.
