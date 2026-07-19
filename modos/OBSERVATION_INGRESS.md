# MODOS Observation Ingress Contract

Status: **proposed Epoch 0 interoperability contract**

Tracked by: issue #19

## Purpose

Windows, Android/Termux, Linux collectors, application sensors, and future edge adapters need one evidence-delivery contract. Local observations may be unsigned, queued offline, retried after response loss, and filtered from source streams whose native positions contain gaps.

The ingress contract preserves those facts rather than pretending every observation is already a signed MODOS domain event.

## Trust boundary

Keep these objects distinct:

1. **Source observation** — the immutable producer record placed in a local outbox. It may be unsigned.
2. **ObservationIngressBatch** — an ordered, bounded delivery object for one producer, receiver, and delivery stream.
3. **ObservationIngressReceipt** — a receiver-signed acknowledgement created only after durable atomic admission.
4. **SignedDomainEvent** — an optional gateway-authored evidence-plane event describing admission. Its signer is the gateway, not an unsigned edge producer.

Transport authentication proves which enrolled principal submitted a batch. It does not retroactively create a producer signature over each source record.

## Identity

A batch names exactly one:

- stable producer principal;
- stable receiver principal;
- delivery-stream identity;
- adapter class and source schema;
- trace and batch identity.

The receiver records the exact authenticated credential fingerprint and optional credential epoch in its receipt. Credential rotation may preserve one stable producer principal through governed enrollment; a role match alone is insufficient.

## Source position versus delivery sequence

These are different namespaces.

**Source position** records where an observation came from: Windows Security `RecordId`, collection epoch, journal cursor, application offset, or sensor position. It may contain legitimate gaps.

**Delivery sequence** is assigned contiguously when the local outbox durably appends an observation. It belongs to one `deliveryStreamId` and is the only sequence used for batching, receiver high-water state, acknowledgement, and compaction.

Queue replacement, host replacement, explicit epoch reset, or lineage loss requires a new delivery-stream identity. Sequence 1 must never silently restart under an existing stream.

## Initial batch semantics

Version 1 is all-or-nothing:

- one batch covers an exact contiguous delivery range;
- event count equals the range width and ordered event list length;
- every event has an exact SHA-256 digest over canonical source-record bytes;
- every event ID is unique in the batch and must agree with an embedded `event_id` or `eventId` when present;
- the receiver admits all records and its receipt in one transaction or admits none;
- exact retry returns the original receipt;
- identity reuse with different content is a collision and fails closed;
- partial success is not represented.

## MODOS canonical JSON v1

The executable contract currently restricts digest-bearing source records to JSON values containing:

- objects with string keys;
- arrays;
- strings;
- booleans;
- null;
- finite integers.

Floating-point values are rejected.

Canonical bytes are UTF-8 JSON produced with:

- keys sorted lexicographically by Unicode code point;
- no insignificant whitespace;
- `,` and `:` as compact separators;
- non-ASCII text emitted directly rather than ASCII escaped;
- no NaN or infinity.

An event digest is:

```text
sha256( canonical_json(event.record) )
```

The batch digest is computed over a deep copy of the complete batch after:

- replacing `integrity.batchDigest` with the empty string;
- replacing `proof.signature` with the empty string when present.

Then:

```text
sha256( canonical_json(batch_digest_material) )
```

This v1alpha1 rule is deliberately narrow and executable with the current Python contract harness. A future standard such as RFC 8785 may replace it only through an explicit version change and compatibility fixtures.

## Proof modes

### `transport-bound`

The authenticated transport/session principal submitted the batch. The batch carries no detached-signature fields. Source records remain unsigned unless their own schema independently says otherwise.

### `detached-signature`

The batch includes an enrolled key ID, Ed25519 algorithm declaration, and detached signature. The signature covers the canonical batch digest material defined above. Signature verification is a receiver obligation; JSON Schema validates shape only.

## Receiver receipt

A receipt binds:

- receipt, batch, trace, producer, receiver, and stream identities;
- exact contiguous delivery range and event count;
- exact batch digest;
- authenticated producer principal;
- credential fingerprint/epoch and proof mode;
- durable commit identity and acceptance time;
- receiver signing key and signature.

A sender may delete nothing based on connection success, HTTP status, TLS completion, or event ID alone. Compaction requires a verified receipt whose identities, range, and batch digest match durable local acknowledgement state.

## Delivery stream state

`DeliveryStreamState` makes local continuity inspectable without exposing event bodies.

Semantic invariants:

- `acknowledgedHighWater <= queuedHighWater`;
- `nextSequence == queuedHighWater + 1`;
- `pendingEvents == queuedHighWater - acknowledgedHighWater`;
- a nonempty pending queue names its oldest pending time;
- acknowledged state names the last durable receipt;
- observation time cannot precede stream creation.

Compaction and retained-window policy are implementation checkpoints. These contracts do not yet authorize deletion.

## Gateway-to-domain mapping

When a gateway emits a `SignedDomainEvent` for admitted observations:

- the gateway is `sourceIdentity` because it signed the domain event;
- original producer identity, source event ID, source schema, source digest, source position, delivery stream, and delivery sequence remain in provenance or body;
- initial trust is `observed` unless separate verification raises it;
- the event may reference an immutable batch manifest rather than duplicate private payloads;
- no command, capability, policy, enforcement, promotion, or canon authority is created.

## Current fixtures

`observation-ingress.fixtures.json` proves:

- a transport-bound Android batch is accepted;
- delivery-sequence gaps are rejected;
- altered event and batch digests are rejected;
- transport-bound mode cannot falsely carry detached-signature fields;
- Windows source positions may jump while delivery remains contiguous;
- a correctly attributed signed receiver receipt is accepted;
- principal mismatch and partial-range receipt mismatch are rejected;
- coherent stream state is accepted;
- impossible acknowledgement and next-sequence state are rejected.

## Deliberate exclusions

These contracts do not implement:

- a network endpoint;
- producer enrollment;
- cryptographic signature verification;
- receiver storage;
- local upload state;
- acknowledgement-based compaction;
- reverse commands;
- capability grants;
- trust promotion;
- live adapter migration.

Those remain evidence-gated implementation checkpoints after the shared contract is reviewed.
