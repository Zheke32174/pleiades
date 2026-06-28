# Pleiades — lean rebuild

A clean, reproducible reintroduction of the Pleiades defensive swarm, rebuilt one
agent at a time to avoid the previous stack's failure modes (see
`../pleiades-design-review.md` and `../pleiades-improvement-brainstorm.md`).

## Invariants (enforced, not aspirational)
1. **One canonical binary + one unit per agent.** No runtime self-install, no `curl|sh`.
   `build.sh` checks every unit's `ExecStart` binary exists before it will finish.
2. **No error masking.** Use `require <cmd>` from the shared lib; failures are logged and
   surface in the agent's status. An agent reports `ok` only when it really is.
3. **systemd owns supervision.** `Restart=on-failure` + `StartLimitBurst` — no bespoke
   while-true restart loops. No crash-loop storms.
4. **Stay in the container.** Read host telemetry only through the explicit read-only
   bridge; never write host paths. No EFI/firmware persistence.
5. **The Nexus is the journal.** Structured events via `nexus_emit` (tag `pleiades-nexus`),
   retained — never self-vacuumed.
6. **No fast loops. Cadence lives in systemd timers.** Agents NEVER run an in-process
   `while true; sleep N` loop (`build.sh` rejects any agent that does). Periodic work is a
   `.timer` with `RandomizedDelaySec` (jitter — agents never wake in lockstep) and a generous
   `AccuracySec` (systemd coalesces wakeups). Prefer event-driven (path/socket units) over
   polling. The old stack's many 10s/30s/2s/0.1s loops across 9 agents were a primary failure
   mode — we do not repeat it.

## Layout
```
lib/pleiades-common.sh     shared helpers (log, require, nexus_emit, status_set)
agents/<name>/             per-agent binary + daemon
units/<name>.service       one hardened, rate-limited unit per agent
build.sh                   idempotent installer (run in-container as root)
```

## Build / deploy
Run inside the booted container as root:
```bash
bash /opt/pleiades-build/build.sh
systemctl enable --now pleiades-maia.service pleiades-maia-checkpoint.timer
```

## The Nexus ledger
Events emitted via `nexus_emit` go to the journal (transport) and a spool. Maia drains the
spool on its checkpoint into a **hash-chained, Ed25519-signed, append-only** ledger at
`/var/lib/maia/nexus/ledger` — never self-vacuumed. Each record:
```
SEQ|TS|PREV_HASH|EVENT_B64|HASH|SIG     HASH = sha256(SEQ|TS|PREV_HASH|EVENT_B64), SIG = Maia(HASH)
```
`nexus-verify [--show]` walks the chain, recomputes every hash, and verifies every signature
against Maia's public key — any alteration or deletion breaks the chain and is detected.
Sealing rides Maia's existing checkpoint timer (no extra wakeups).

## Reintroduction order
1. **Maia** — trust root (Ed25519 via openssl).            [done]
2. **Nexus** — journal-backed, hash-chained signed ledger.  [done]
3. **Taygete** — SSH honeypot sensor (socket-activated).    [done]
4. **Celaeno** — watchdog, event-driven `OnFailure` (no restart loop).  [done]
5. **Electra** — multi-port decoy farm (:8088 http, :2323 telnet).  [done]
Then Alcyone (read-only) / Merope / Sterope (de-offensified) / Asterope.

## Adding the next agent
1. `agents/<name>/<name>-daemon.sh` — source the lib, use `require`, `status_set`, `nexus_emit`.
2. `units/pleiades-<name>.service` — copy the Maia unit's hardening + rate-limit block.
3. Add install lines to `build.sh`. Re-run; the ExecStart check guards mismatches.
