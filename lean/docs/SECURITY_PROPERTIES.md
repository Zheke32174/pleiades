# Lean Pleiades Security Properties

These are release gates, not aspirations. A build that cannot demonstrate a property must not claim that property.

## Isolation

1. A network-facing decoy cannot read Maia private keys or snapshots.
2. A decoy cannot write or truncate the sealed ledger.
3. A worker cannot access host management sockets or unrestricted host filesystem paths.
4. Only Maia may write the ledger and use the ledger-signing key.
5. Observe-only workers may write only their own runtime state or submit events through the approved intake path.

## Authority

6. No model or worker has ambient root authority.
7. Unknown action verbs and targets are denied.
8. Generic shell text is never a privileged broker action.
9. Every privileged request is authenticated, expiring, replay-protected, logged, and independently verified.
10. Recovery approval is independent from evidence-signing authority.

## Evidence

11. An event is durably recorded before successful acknowledgement.
12. Event identity survives retries, allowing duplicate detection.
13. Sealing failure cannot silently discard unsealed events.
14. Missing, empty, stale, incomplete, and tampered ledgers are distinct health states.
15. Raw evidence remains linked to every summary, score, graph claim, and training example.
16. Ledger heads are periodically anchored outside the runtime that signs them.

## Survival and recovery

17. The host boots and remains manageable without the cognitive plane.
18. A worker or supervisor crash cannot trigger an infinite restart storm.
19. A compromised instance is preserved for evidence and replaced from a known-good image.
20. Restores are version-aware, rollback-protected, signed, and explicitly authorized.

## Build and release

21. One canonical binary and one canonical unit exist per component.
22. No runtime `curl | sh`, runtime toolchain installation, or runtime unit generation ships.
23. Every production image is tested from a clean build.
24. A skipped security test is not a passing guarantee.
25. Release publication occurs only from a protected version tag after required checks.

## Required adversarial tests

- Attempt to read `/var/lib/maia/keys` from Taygete and Electra.
- Attempt to modify the Nexus ledger from every non-Maia service.
- Submit malformed, oversized, stale, replayed, duplicate, and unauthenticated events.
- Interrupt Maia during sealing and prove every event remains recoverable.
- Roll the ledger back to an older signed copy and verify detection.
- Inject event text that resembles another event type and prove typed parsing prevents score manipulation.
- Stop the complete cognitive plane and verify host services remain healthy.
- Crash each service repeatedly and verify the circuit breaker stops respawning.
- Request undeclared broker actions and targets and verify denial.
- Compromise a disposable decoy image and verify no route exists to evidence, authority, or recovery planes.

## Promotion criterion

A defensive change is promoted only when it is machine-measurable, steward-verifiable, and—where user-facing—noticeably better to an ordinary operator. Security and recoverability changes may be invisible to the operator, but must have stronger instrumentation and adversarial proof.
