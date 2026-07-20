# Security Invariants

1. **TLS is necessary but not sufficient.** A request must pass certificate enrollment and message-signature checks where the protocol carries a signed envelope.
2. **Certificate identity and signed identity must agree.** A controller or node cannot present one certificate and name another principal inside the payload.
3. **Network location is never identity.** IP addresses are routing facts only.
4. **Message keys and TLS keys are separate.** Compromise, rotation, and audit can be handled independently.
5. **Private key permissions fail closed.** On Unix, group/world-accessible private key files are rejected.
6. **New authority is unavailable during partition.** Capability grants require `Connected` state.
7. **Cached authority expires.** Expired grants are removed and attached workloads are stopped.
8. **Isolation cannot be weakened by the request.** Signed constraints are interpreted as a mandatory floor.
9. **The runtime sees typed argv.** No shell string is constructed or interpreted.
10. **Audit precedes execution.** A spawn cannot cross into systemd until its authorization decision is durably queued.
11. **Post-start audit failure fails closed.** The newly started workload is stopped if its result cannot be persisted.
12. **Local evidence is ACK-gated.** The node clears an event only after a valid controller signature over the matching event ID.
13. **Replay is rejected.** Heartbeat sequence is scoped by node and boot ID.
14. **Quarantine blocks action.** Quarantined state denies both mutation and status reads through the control API.
15. **No model is in the authority path.** All admission logic is deterministic Rust code.
