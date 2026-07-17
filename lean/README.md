# Pleiades Lean Runtime

`lean/` is the canonical release-track implementation of the Pleiades defensive suite. It is a clean reintroduction of the useful components from the earlier stack, rebuilt around explicit invariants rather than runtime self-assembly.

## Enforced invariants

1. **One canonical binary and one canonical unit per component.** `build.sh` refuses to finish when an `ExecStart` target is missing.
2. **No error masking.** Failures are surfaced through status and the Nexus event path.
3. **systemd owns supervision.** Services use event activation, `OnFailure`, and slow jittered timers rather than custom restart loops.
4. **No direct host mutation.** The remaining `/host/win` bridge reader is a temporary migration interface limited to Maia; the target design replaces it with authenticated host collectors.
5. **Evidence is retained.** Events receive unique IDs and are sealed into a hash-chained, Ed25519-signed ledger.
6. **Every service is resource-bounded.** Services run inside `pleiades.slice`, while public-facing handlers also have per-connection time, CPU, memory, task, and connection limits.
7. **Cognition is non-authoritative.** Future AI workers interpret and propose. A deterministic broker owns the transition from proposal to host action.

## Layout

```text
agents/                       bounded component implementations
lib/pleiades-common.sh        event, status and error helpers
units/                        hardened systemd services, sockets, timers and slice
policy/authority-actions.v1.json
                              default-deny future broker vocabulary
ops/                          boot, deployment and verification helpers
docs/SECURITY_PROPERTIES.md   executable defensive guarantees
build.sh                      offline idempotent installer
```

## Components

| Component | Role | Authority |
|---|---|---|
| Maia | Key initialization, signed checkpoint, Nexus sealing | Evidence-plane write access |
| Nexus | Ledger verification | Read-only verifier |
| Taygete | SSH deception sensor | Event submission only |
| Electra | HTTP/telnet deception sensors | Event submission only |
| Alcyone | Listener and connection posture | Observe-only |
| Celaeno | Failure alert recording | Observe-only |
| Merope | Signed encrypted snapshots | Snapshot state only; restore separately guarded |
| Sterope | Threat posture calculation | Observe-only |

## Build

Run inside the booted Gentoo container as root:

```bash
bash /opt/pleiades-build/build.sh
systemctl enable --now \
  pleiades-maia.service \
  pleiades-maia-checkpoint.timer \
  pleiades-taygete.socket \
  pleiades-electra-http.socket \
  pleiades-electra-telnet.socket
```

The build installs the shared resource slice and rejects unit/binary mismatches, infinite agent loops, `Restart=always`, evidence-vacuuming commands, and runtime `curl | sh` execution.

## Nexus ledger

`nexus_emit` writes an event with a unique ID, source identity, and observed timestamp to the journal and the current flock-serialized queue. Maia claims the queue atomically and seals records into:

```text
SEQ|TS|PREV_HASH|EVENT_B64|HASH|SIG
```

`HASH` covers the sequence, timestamp, previous hash and encoded event. `SIG` is Maia's Ed25519 signature over that hash.

```bash
nexus-verify
nexus-verify --show
nexus-verify --allow-empty
```

Missing, empty, invalid, and valid ledgers produce distinct results. Interrupted sealing leaves an inflight artifact that Maia requeues on the next checkpoint. Delivery is therefore at least once; event IDs permit later deduplication.

## Verification

From the host environment:

```bash
bash lean/ops/verify-full.sh
```

The verifier exercises the trust root, live socket sensors, sealing, sandbox behavior, failure alerts, snapshot gating, threat scoring, and final ledger validation. Any failed assertion exits nonzero.

Static release checks:

```bash
bash ci/check-lean-security.sh lean
```

## Migration direction

The current lean container is a staging substrate, not the final trust topology. The next structural changes are:

1. replace direct host mounts with signed host collectors;
2. move public-facing decoys into disposable microVMs;
3. introduce durable authenticated event intake;
4. place evidence signing and anchoring outside the deception environment;
5. implement the deterministic authority broker;
6. attach the learning spine and non-authoritative cognitive coprocessor.

See [`../docs/DEFENSIVE_ARCHITECTURE.md`](../docs/DEFENSIVE_ARCHITECTURE.md).
