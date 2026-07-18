# PDK Authority Continuity Invariants

Status: implementation checkpoint for PR #10

The node authority layer treats durable restrictions as stronger than restart-local permissions.

## Admission

A capability grant is not durably admitted unless one SQLite transaction commits all of the following:

- the monotonic issuer/target/subject sequence floor;
- immutable token identity and exact signed-content binding;
- active lease use and expiry state;
- the signed admission event in the audit outbox.

A failed transaction leaves none of those admission effects behind. An exact retry after a committed response loss is idempotent and returns the original admission receipt identity.

## Mutation serialization

Every authority mutation first advances the singleton `capability_authority_write_fence` generation inside its transaction. This deliberately acquires the SQLite writer reservation before authority reads occur, preventing deferred reader-to-writer upgrades from failing immediately under ordinary short-lived writer contention.

The fence serializes:

- grant admission;
- durable use consumption;
- revocation tombstone creation;
- expired active-state compaction.

The generation is monotonic local evidence of authority-write ordering. It is not itself a permission or distributed consensus epoch.

## Single use-budget authority

The in-memory policy cache validates signatures, target, action, subject, time, offline policy, and isolation constraints. It does not consume `max_uses`.

The SQLite authority state is the sole mutable use-budget ledger. This prevents a transient database or audit failure from burning an in-memory use while leaving the durable ledger unchanged, or vice versa.

## Restart and cleanup

Restart preserves:

- sequence floors;
- exact token identity;
- consumed uses;
- expiry;
- revocation tombstones;
- signed admission and revocation receipts.

Restart does not automatically reactivate cached permission. The authenticated controller must re-present the exact current signed grant.

Compaction removes only expired active grant rows. It does not lower sequence floors or delete token identity or revocation history.

## Lease sweeping

The lease sweeper removes expired grants from the policy cache, terminates associated workloads, emits signed outcome events, and compacts expired durable active state. Compaction failure is reported but cannot make an expired grant usable because authorization independently enforces signed expiry.

## Required regression gates

The checkpoint remains incomplete unless automated tests prove:

1. audit-outbox insertion failure rolls back admission state and sequence floors;
2. exact retry and exhausted use state survive database reopen;
3. revocation survives reopen and prevents re-admission;
4. compaction preserves identity, sequence, and tombstone restrictions;
5. short SQLite writer contention resolves within the bounded busy timeout;
6. rustfmt, strict Clippy, full workspace tests, and release compilation pass.

Live Alienware–Lenovo behavior, controller quorum, offline cache restoration, and production promotion remain separate gates.
