# nlspec/purple-team.md — Purple-Team Container System

> Standalone NLSpec. Read `PURPLE_STATE.md` in the project root before this file.
> Specifies the eight-service polyglot initialization suite running inside a Gentoo systemd-nspawn container on WSL2.

## Purpose

A defense-in-depth container stack where eight named services each handle one security domain (orchestration, honeypot, threat aggregation, watchdog, network anomaly, recovery, audit, containment). All services are initialized by polyglot bash scripts that are environment-aware (WSL, DGX Spark, VPS) and idempotent. The substrate is a Gentoo Linux rootfs at `/workspaces/gentoo/root.x86_64`, booted as a systemd-nspawn container from the WSL2 host.

## Scope

**In scope:**
- Eight polyglot initialization scripts (SofiaX, Beryl, Artemis, Ava, Eris, Mariah, Vera, Zara).
- Owner-escrow signal system (Ed25519 signing via `sophia_crypto`).
- Hivemind policy broker (capability registration + request gating).
- Host-bridge infrastructure (proc, sys, run, mnt/c mounted into container).
- Ouroboros append-only event FIFO.
- `purple-request-broker` service consuming `.req` extension requests.
- Regression test suite (`purple-regression.sh` + `purple-regression-lib.sh`).

**Out of scope:**
- Gentoo stage3 bootstrapping (handled by underhall's `install-scripts/`).
- bedrock brl/strat reprogramming (underhall's concern).
- alien package format conversion (separate project).

## Actors

- **Owner/operator** (human) — sole authority to approve owner-escrow signals; runs health checks from the runbook.
- **GENERAL ZOD** (Artemis.sh) — omniversal orchestrator; controls threat mode, thrall dispatch, mode switching.
- **SOPHIA** (SofiaX.sh) — silent auditor and overseer; runs `sophia_crypto` for Ed25519 sign/verify; registers as recovery agent.
- **CHESHIRE** (Beryl.sh) — SSH honeypot on port 2222; BGP hijack and thermal anomaly detection; hostile-recon IP blocking with loopback exemption.
- **HATTER** (Ava.sh) — BGP hijack detection via looking glass; thermal anomaly monitoring; honeypot listener.
- **ROBIN HOOD + LICH** (Eris.sh) — fake environment projection; Lich resurrection component.
- **LITTLE JOHN** (Mariah.sh) — watchdog for Hatter, Cheshire, Zod, Robin, Resurrection, Ouroboros; regeneration and hot-patch delivery.
- **RESURRECTION PROTOCOL** (Vera.sh) — encrypted recovery state; SSH decoy logging; recovery beacon.
- **OUROBOROS** (Zara.sh) — containment layer; threat aggregation; botnet blocklist; append-only event FIFO (`/run/purple/ouroboros_fifo`).

## Behaviors

| # | Behavior | Preconditions | Postconditions | Acceptance test | Failure modes |
|---|---|---|---|---|---|
| B1 | Each script initializes its service idempotently on any supported environment (WSL, DGX Spark, VPS). | Script run as root; Gentoo rootfs mounted; `systemd` is PID 1 inside container. | Service unit registered and active; `systemctl is-active <service>` returns `active`; re-run produces no error and no duplicate unit. | Run script twice; second run exits 0 with no state change. | `systemctl start` fails → unit logs error; script must not exit 0 on silent failure. |
| B2 | lm-sensors is never passed to the package manager; it is handled as a no-op shim on all 7 scripts that need it. | Script uses the package manager shim (`install_package` or equivalent). | `lm-sensors` is silently skipped; emerge / apt / pacman never sees it; no error logged. | Grep all 8 scripts for emerge/apt/pacman + lm-sensors: zero matches; grep for the no-op shim pattern: 7 matches (not SofiaX). | lm-sensors appearing in any package manager invocation is a defect. |
| B3 | Owner-escrow signal: `sophia_crypto sign` produces a valid Ed25519 signature; `sophia_crypto verify` accepts it and rejects tampered input. | `sophia_crypto` binary compiled from Go source embedded in SofiaX.sh; Ed25519 key pair on disk. | `sign` outputs a hex-encoded Ed25519 signature; `verify` with the same key and message exits 0; `verify` with a modified message exits non-zero. | Round-trip test: sign a known string, verify it, flip one byte, verify again — expect 0 / non-0. | Missing key → `sophia_crypto` returns error; truncated hex → `verify` returns parse error. |
| B4 | Hivemind policy broker denies all `denied_request_classes` and permits all `allowed_request_classes`. | `hivemind-policy.json` written to `/etc/purple/hivemind-policy.json`; `purple-request-broker` running; request file has `.req` extension in `/run/purple/requests/`. | `capabilities` request → `allow`; `script-modify`, `network-change`, `credential-access` requests → `deny`, no action dispatched; policy JSON is not rewritten. | Submit one request per class; verify decision files match policy. | Missing `.req` extension → broker ignores file; missing policy file → broker must fail closed (deny). |
| B5 | Host bridges are mounted into the container and remain visible: `/host/proc`, `/host/sys`, `/host/run/purple-gentoo-heartbeat/status`, `/mnt/c` Windows bridge. | Heartbeat script running on WSL host; container booted via systemd-nspawn. | All four bind-mounts present; `/var/lib/purple-team/host-bridge/windows11/` updates with Windows file timestamps. | `stat /host/proc/1` from inside container exits 0; Windows sample files have recent mtime. | Heartbeat not running → bridges absent; container restart without heartbeat → all four bridges drop. |
| B6 | Cheshire SSH honeypot (port 2222) exempts loopback addresses from permanent blocking and rate-limiting. | Cheshire running; `isLoopback` variable defined in `sandbox.js`. | Connections from `127.0.0.1` / `::1` are accepted without triggering IP block or rate limit; non-loopback hostile recon triggers block + telemetry. | Connect from loopback: receive SSH banner, no block entry; connect 50× rapidly from loopback: no rate-limit hit. | Missing `isLoopback` definition → `ReferenceError`, service crashes with exit status 1. |
| B7 | Ouroboros FIFO is append-only: all eight scripts write `HIVEMIND_CAPABILITY` events via `printf ... >> ouroboros_fifo`; nothing truncates it during normal operation. | Container running; `/run/purple/ouroboros_fifo` exists (created by first script to run). | Each script appends exactly one capability event on initialization; file grows monotonically during a session. | After running all 8 scripts, line count of `ouroboros_fifo` ≥ 8; no truncation markers. | Using `>` instead of `>>` would wipe prior events — that is the defect pattern to prevent. |
| B8 | Regression test suite (`purple-regression.sh`) passes all tests without container restart between runs. | All 8 scripts previously initialized; services active; test harness sourced from `purple-regression-lib.sh`. | All test functions return 0; no test emits FAIL; Cheshire concurrency cap test (if present) runs last to preserve test isolation. | `bash purple-regression.sh` exits 0; summary shows zero failures. | Cheshire concurrency cap test run early causes EADDRINUSE in subsequent tests — test ordering is load-bearing. |

## Constraints

| Metric | Target | Rationale |
|---|---|---|
| All 8 scripts must pass bash syntax validation | `bash -n <script>` exits 0 for each | Basic gate before deployment. |
| lm-sensors never in any package manager call | Zero grep matches | Hardware sensor package unavailable in container; must be shim'd. |
| Go/Rust installers never use emerge | Only curl-based install paths | emerge for Go/Rust has broken dependency chains in this container. |
| Idempotent initialization | Second run of any script: no state change, exit 0 | Containers restart; scripts re-run on recovery. |
| Hivemind default policy | `"default_request_decision": "deny"` | Fail-closed posture. Owner must explicitly allow. |
| Ed25519 key transport | Hex-encoded only | Wire-safe for event streams and log files. |
| Loopback always exempt from Cheshire block | `isLoopback` must be defined | Regression test suite connects from loopback. |
| Owner-escrow signal architecture | Ed25519 sign/verify; no shared secrets | Identity-bound; replay-resistant. |

## Dependencies

| Component | Runtime | Why |
|---|---|---|
| Gentoo nspawn container | systemd-nspawn on WSL2 host | All services run inside this boundary. |
| `sophia_crypto` | Go binary (compiled at SofiaX.sh build time) | Ed25519 sign/verify for owner-escrow signals. |
| `purple-request-broker` | Bash daemon or Go service | Processes `.req` files from `/run/purple/requests/`. |
| Cheshire `sandbox.js` | Node.js | SSH honeypot with hostile recon detection. |
| `purple-regression-lib.sh` | Bash | Shared test helpers for all regression tests. |
| WSL2 host heartbeat | `purple-gentoo-heartbeat.sh` | Manages host bridges; keeps container alive. |

## Invariants

1. **lm-sensors is always a no-op** — never passed to any package manager in any script.
2. **Go and Rust are installed via curl only** — emerge for Go/Rust is banned.
3. **Hivemind policy is owner-authorized-defensive** — default deny; policy JSON is never overwritten by scripts after first write.
4. **Ouroboros FIFO is append-only** — `>>` only, never `>`.
5. **Loopback exempt** — Cheshire must never permanently block or rate-limit `127.0.0.1` or `::1`.
6. **Ed25519 hex transport** — `sophia_crypto` encodes signatures as hex; binary transport is banned.
7. **Idempotent scripts** — every script safe to re-run; no duplicate service units.
8. **Backups before edits** — `cp <file> <file>.bak.<timestamp>` before every modification pass.

## Open questions

1. Should `purple-request-broker` be a compiled Go service or stay as a bash daemon for portability?
2. At what threshold should OUROBOROS evict old entries from its blocklist (currently unbounded)?
3. Should LITTLE JOHN's watchdog interval be configurable per-service or global?
4. When should Resurrection Protocol fire its recovery beacon? Currently manual/threshold — should it be time-based?

## Quality gate

Dark Factory target: composite ≥ 0.85. Dimensions weighted same as underhall attractor runs:
- Behavior Coverage (40%) — all 8 behaviors testable and tested.
- Constraint Adherence (20%) — package manager bypass and FIFO invariants provably enforced.
- Holdout Pass Rate (25%) — blind scenario evaluation.
- Quality (15%) — code clarity, error handling, defensive posture.

## Methodology pointer

Spec is the source of truth. When code lands, revise this spec to reflect what shipped — not the other way around.
