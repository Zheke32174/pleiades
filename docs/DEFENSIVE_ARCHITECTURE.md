# Pleiades Defensive Architecture

Pleiades is evolving from a single defensive container into a set of deliberately separated trust planes. The purpose of the separation is simple: compromise of a public-facing sensor or decoy must not provide a route to evidence signing, recovery authority, host control, or the cognitive control plane.

## Non-negotiable rule

> Sensors observe. Cognitive services interpret. The authority broker executes a small declared action vocabulary. The host kernel remains sovereign.

No AI worker, decoy, parser, retrieved document, or generated script receives ambient host authority.

## Defensive planes

### 1. Sensor plane

Host-local collectors produce typed observations from logs, eBPF, audit, identity, network, storage, Android, and service health. Collectors export only declared fields through authenticated channels. They do not expose the host filesystem namespace to the analysis environment.

### 2. Deception plane

Taygete, Electra, and future public-facing decoys run as disposable workloads. They have no access to signing keys, recovery state, management sockets, or the knowledge store. Rebuilding the complete deception plane must be cheaper and safer than repairing it in place.

### 3. Evidence plane

The Nexus accepts authenticated events, validates schemas, assigns durable identities, and records them before acknowledgement. Maia seals ledger epochs with a rotatable subordinate signing key. Ledger heads are anchored to an independent node or storage target so compromise of one runtime cannot produce an undetectable alternate history.

### 4. Knowledge plane

Verified events become experience packets, graph relationships, semantic indexes, and retrieval material. Raw evidence remains linked and is never replaced by model-written summaries. Contradictions and stale knowledge remain visible.

### 5. Cognitive plane

Tiny bounded AI services classify, correlate, summarize, prioritize, retrieve prior experience, and propose actions. They may abstain or escalate. They cannot directly execute privileged operations or rewrite their own policies, models, or training data.

### 6. Authority plane

A deterministic host-local broker authenticates every request and checks the action, target, parameters, evidence, freshness, rate limits, rollback path, and current host state. Unknown verbs and targets are denied. Generic shell and unrestricted `exec` are not broker actions.

### 7. Recovery plane

Recovery uses independently stored images, keys, snapshots, attestations, and signed approvals. A compromised instance is frozen for evidence and replaced with a known-good instance. Recovery authority is separate from evidence-signing authority.

## Target topology

```text
Public network
    |
Disposable deception microVMs
    |
Authenticated one-way event intake
    v
Evidence gateway -> signed ledger -> independent anchor
    |                     |
    v                     v
Knowledge / retrieval   forensic archive
    |
Cognitive coprocessor and tiny service colony
    |
Typed capability proposal
    v
Deterministic authority broker
    |
Host-local bounded executor
    v
Authoritative host kernel and services
```

## Host boundary

The target design does not mount the host's `/proc`, `/sys`, `/run`, or Windows system drive into the cognitive or deception plane. Host collectors expose typed telemetry over Unix sockets or `vsock`. The host must continue operating safely when every cognitive component is stopped.

## Event requirements

Every event must carry:

- a unique event ID;
- source identity and trust class;
- source-local sequence number where available;
- observed timestamp and ingestion timestamp;
- schema version;
- subject identity;
- evidence references;
- sensitivity and retention class.

The intake path must provide durable queueing, replay detection, schema validation, dead-letter quarantine, and at-least-once delivery. Duplicate event IDs are safe to reject or coalesce.

## Authority request requirements

Every request must declare:

- requester identity and service role;
- manifest and policy version;
- action verb;
- exact target;
- typed parameters;
- supporting evidence IDs;
- confidence and escalation state;
- expiry and nonce;
- rollback and verification plan;
- signature or authenticated channel identity.

The first broker vocabulary should remain deliberately small: service status, restart an allowlisted noncritical unit, move an identified process to a declared cgroup, run an approved diagnostic package, stage a signed configuration, and roll back a known deployment.

## Deployment progression

### Phase 1 — Canonical lean stack

`lean/` is the only release-track runtime. The older self-assembling scripts remain historical reference and are not deployable production inputs.

### Phase 2 — Hardened identities and resource envelope

Every service receives an explicit operating-system identity or equivalent isolation, private state, a shared resource slice, syscall and address-family restrictions, and no writable shared directory except through an ingestion interface.

### Phase 3 — Durable event gateway

Replace direct shared-spool writes with authenticated event submission and transactional sealing. Anchor ledger heads independently.

### Phase 4 — Deception split

Move public-facing decoys into disposable containers or microVMs with one-way telemetry and no management-plane route.

### Phase 5 — Authority broker

Introduce a deterministic broker and host-local executors before granting any cognitive service automatic action authority.

### Phase 6 — Cognitive coprocessor

Deploy the non-authoritative Pleiades cognitive coprocessor beside the polyglot execution plane. It coordinates tiny workers and retrieval but remains revocable and unnecessary for host boot.

### Phase 7 — Distributed recovery and attestation

Use independent nodes and storage for ledger anchoring, images, recovery authorization, and rollback protection.

## Security objective

Pleiades is successful when compromise of any one worker, decoy, model, parser, container, or retrieved artifact cannot silently alter evidence, manufacture authority, erase recovery options, or prevent the host from returning to deterministic safe operation.
