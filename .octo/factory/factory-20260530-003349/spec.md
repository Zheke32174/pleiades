# nlspec/pleiades-team.md — Pleiades-Team Container System

> Standalone NLSpec. Read `PLEIADES_STATE.md` in the project root before this file.
> Eight-service polyglot initialization suite inside a Gentoo systemd-nspawn container on WSL2.

## Purpose

A defense-in-depth container stack where eight named services each handle one security domain (orchestration, honeypot, threat aggregation, watchdog, network anomaly, recovery, audit, containment). All services are initialized by polyglot bash scripts that are environment-aware (WSL, DGX Spark, VPS) and idempotent. Substrate: Gentoo Linux rootfs at `/workspaces/gentoo/root.x86_64`, booted as systemd-nspawn from WSL2 host.

## Quantified Constraints

| Metric | Target | Rationale |
|---|---|---|
| Bash syntax validation | `bash -n <script>` exits 0 for all 8 scripts | Deployment gate |
| lm-sensors in package manager | Zero grep matches across all 8 scripts | Package unalcyoneilable; must be shim'd |
| Go/Rust installation method | curl-only; `emerge` for Go/Rust is banned | emerge has broken deps in this container |
| Idempotent init | Second run: exit 0, no state change, ≤ 5 seconds | Containers restart; scripts re-run on recovery |
| Script init time (first run) | ≤ 60 seconds per script | Container recovery must be fast |
| Heartbeat update interval | Bridge status file updated within 10 seconds of state change | Stale heartbeat = bridges appear dead |
| Taygete concurrent capacity | ≥ 50 simultaneous SSH probe connections without crash | Adversarial recon uses parallel probers |
| Pleiades Swarm broker decision latency | `.req` files processed within 2 seconds | Policy decisions must not block operations |
| maia_crypto sign/verify latency | Round-trip ≤ 500ms for 1 KiB message | Owner-escrow must not introduce delay |
| Pleiades Nexus FIFO write latency | Events appended within 1 second of trigger | Threat correlation requires near-realtime data |
| Regression suite runtime | `pleiades-regression.sh` completes in ≤ 5 minutes | CI gate must not block deploys |
| Memory per service at idle | ≤ 64 MiB RSS | Container shares 4 GiB across 8 services + WSL |
| Pleiades Swarm default decision | `"default_request_decision": "deny"` | Fail-closed posture; owner must explicitly allow |
| Ed25519 key transport | Hex-encoded only; binary transport banned | Wire-safe for event streams and log files |
| Loopback exemption | `isLoopback` defined; 127.0.0.1/::1 never blocked | Regression test suite connects from loopback |

## Dependencies

| Component | Version | Source | Purpose |
|---|---|---|---|
| systemd-nspawn | ≥ 249 | Gentoo portage | Container isolation boundary |
| Go toolchain | ≥ 1.21 | curl install (NOT emerge) | Compiles `maia_crypto` Ed25519 binary |
| `golang.org/x/crypto` | latest | `go get` at compile time | Ed25519 primitives in maia_crypto |
| Node.js | ≥ 18 LTS | nvm or system pkg | Taygete `sandbox.js` honeypot runtime |
| `ssh2` npm library | v1.x | npm install | SSH decoy in Taygete |
| Bash | ≥ 5.1 | System | Script runtime; all 8 init scripts |
| `jq` | ≥ 1.6 | Portage | Pleiades Swarm policy JSON parsing |
| `inotify-tools` | ≥ 3.20 | Portage (or poll fallback) | Request broker watches `.req` dir |
| `openssl` | ≥ 3.0 | System | Key gen fallback if maia_crypto fails |
| `pleiades-gentoo-heartbeat.sh` | project | WSL2 host | Manages host bridges; keeps container alive |
| `pleiades-regression-lib.sh` | project | In-repo | Shared test helpers for regression suite |
| `paper2code` | `tools/paper2code` | GitHub tool checkout | Converts papers into citation-anchored implementation scaffolds for factory candidates |
| `hermes-agent-self-evolution` | `tools/hermes-agent-self-evolution` | GitHub tool checkout | Evolves skills/prompts/tool descriptions behind tests and constraint gates |
| `continual-harness` | `tools/continual-harness` | GitHub tool checkout | Runs reset-free harness refinement and CLI-agent benchmark loops |

## Actors

- **Owner/operator** — sole authority to approve owner-escrow signals; runs health checks
- **PLEIADES ATLAS** (Sterope.sh) — omniversal orchestrator; threat mode and thrall dispatch
- **MAIA** (Maia.sh) — auditor; runs `maia_crypto`; registers as recovery agent
- **TAYGETE** (Taygete.sh) — SSH honeypot port 2222; BGP hijack detection; hostile-recon blocking
- **ALCYONE** (Alcyone.sh) — BGP hijack detection; thermal anomaly monitoring
- **ELECTRA HOOD + LICH** (Electra.sh) — fake environment projection; Lich pleiades-rebirth
- **CELAENO** (Celaeno.sh) — watchdog for all 7 other services; regeneration and hot-patch
- **PLEIADES_REBIRTH PROTOCOL** (Merope.sh) — encrypted recovery state; SSH decoy logging
- **PLEIADES_NEXUS** (Atlas.sh) — containment layer; threat aggregation; append-only event FIFO

## Behaviors

| # | Behavior | Preconditions | Postconditions | Acceptance test | Failure modes |
|---|---|---|---|---|---|
| B1 | Each script initializes its service idempotently on WSL, DGX Spark, and VPS. | Root; Gentoo rootfs mounted; systemd is PID 1. | Service unit active; `systemctl is-active` returns `active`; re-run produces no error. | Run script twice; second run exits 0, no state change, ≤ 5s. | `systemctl start` fails → unit logs error; script must NOT exit 0 on silent failure. |
| B2 | lm-sensors is never passed to any package manager; handled as no-op shim in all 7 scripts that need it. | Script uses the package manager shim. | lm-sensors silently skipped; emerge/apt/pacman never sees it. | Grep 8 scripts: zero `emerge.*lm-sensors` matches; 7 no-op shim matches. | Any package manager invocation with lm-sensors is a defect. |
| B3 | `maia_crypto sign` produces a valid Ed25519 signature; `maia_crypto verify` accepts it and rejects tampered input. | Binary compiled from Go source in Maia.sh; key pair on disk. | Sign outputs hex-encoded signature; verify with same key exits 0; with modified message exits non-zero. | Round-trip: sign known string, verify, flip one byte, verify again → 0 / non-0. | Missing key → error; truncated hex → parse error. |
| B4 | Pleiades Swarm policy broker denies all `denied_request_classes` and permits all `allowed_request_classes`. | Policy JSON at `/etc/pleiades/pleiades-swarm-policy.json`; broker running; requests as `.req` files. | `capabilities` → allow; `script-modify`, `network-change`, `credential-access` → deny; policy not rewritten. | Submit one request per class; verify decision files match policy. | Missing policy → broker fails closed (deny all); missing `.req` extension → ignored. |
| B5 | Host bridges remain mounted: `/host/proc`, `/host/sys`, `/host/run/pleiades-gentoo-heartbeat/status`, `/mnt/c`. | Heartbeat running on WSL host; container booted via systemd-nspawn. | All four bind-mounts present; Windows bridge path updated with recent mtimes (≤ 10s lag). | `stat /host/proc/1` exits 0 inside container; Windows sample files have mtime within 10s. | Heartbeat stopped → bridges absent within next heartbeat interval. |
| B6 | Taygete SSH honeypot (port 2222) exempts loopback from permanent block and rate-limiting. | Taygete running; `isLoopback` defined in `sandbox.js`. | 127.0.0.1/::1 connections accepted; 50 rapid loopback connections don't hit rate limit. | Connect 50× from loopback: no block entry, no rate-limit; connect from non-loopback: triggers block + telemetry. | Missing `isLoopback` → ReferenceError; service crashes with exit 1. |
| B7 | Pleiades Nexus FIFO is append-only: all 8 scripts write `PLEIADES_SWARM_CAPABILITY` events via `printf ... >> pleiades_nexus_fifo`. | Container running; `/run/pleiades/pleiades_nexus_fifo` exists. | Each script appends exactly one capability event; FIFO grows monotonically. | After running all 8 scripts, line count ≥ 8; no truncation. | Using `>` instead of `>>` wipes prior events — the defect pattern to prevent. |
| B8 | Regression test suite (`pleiades-regression.sh`) passes all tests without container restart between runs. | All 8 scripts initialized; services active; lib sourced from `pleiades-regression-lib.sh`. | All test functions return 0; zero FAIL emissions; runtime ≤ 5 minutes. | `bash pleiades-regression.sh` exits 0; summary shows zero failures; Taygete concurrency test runs last. | Taygete concurrency test run early → EADDRINUSE in subsequent tests (ordering is load-bearing). |
| B9 | Factory toolchain is owner-visible through `pleiades-factory-tools`. | Tool repos are cloned under `/workspaces/gentoo/tools`; `.octo/factory/toolchain.json` exists. | CLI lists `paper2code`, `hermes-evolution`, and `continual-harness` with local path and git HEAD; execution remains owner-invoked. | `pleiades-factory-tools status` exits 0 and reports all three tools present. | Missing repo → status reports `present=no`; dependency/runtime errors stay local to explicit subcommands. |

## Invariants

1. **lm-sensors is always a no-op** — never passed to any package manager.
2. **Go and Rust installed via curl only** — emerge for Go/Rust is banned.
3. **Pleiades Swarm policy is owner-authorized-defensive** — default deny; policy JSON never overwritten after first write.
4. **Pleiades Nexus FIFO is append-only** — `>>` only, never `>`.
5. **Loopback exempt** — Taygete never blocks or rate-limits 127.0.0.1 or ::1.
6. **Ed25519 hex transport** — maia_crypto encodes signatures as hex; binary banned.
7. **Idempotent scripts** — every script safe to re-run; no duplicate service units.
8. **Backups before edits** — `cp <file> <file>.bak.<timestamp>` before every modification.

## Error Paths

| # | Scenario | Expected behavior |
|---|---|---|
| E1 | systemd not PID 1 | Script detects via `systemctl status` exit code; logs warning; exits non-zero |
| E2 | maia_crypto binary missing | Maia.sh re-compiles from embedded Go source; if fails, exits non-zero and logs |
| E3 | `/run/pleiades/requests/` absent | Broker creates with `install -d -m 700`; logs; resumes watching |
| E4 | Pleiades Nexus event log removed mid-session | First writer re-creates it as a regular append-only file; logs re-creation; appends |
| E5 | Pleiades Swarm policy file absent at startup | Broker fails closed; logs `POLICY_MISSING` to FIFO; does NOT write new policy |
| E6 | 200 rapid connections from non-loopback IP | Rate-limit + permanent block after threshold (default 10/min); TCP RST to blocked IP |
| E7 | Service already active on re-run | Script detects active status; skips start; exits 0 with "already active" log |
| E8 | Container restarts with bridges missing | Heartbeat re-mounts within 10s; writes `BRIDGE_REMOUNTED` to FIFO |
| E9 | Ed25519 key tampered | maia_crypto verify: non-zero exit; `SIGNATURE_INVALID` response; no crash |
| E10 | One service not active during regression run | Test for that service emits FAIL; suite continues; final exit non-zero |

## Acceptance Criteria (Dark Factory Quality Gate)

Dark Factory target: composite satisfaction ≥ 0.85.

| Dimension | Weight | Measurable criterion |
|---|---|---|
| Behavior Comeropege | 40% | All 8 behaviors (B1-B8) testable via automated scripts; 0 unverifiable assertions |
| Constraint Adherence | 20% | Package manager bypass provable by grep (0 matches); FIFO append-only verifiable via strace or `lsof` |
| Holdout Pass Rate | 25% | Blind scenario evaluation: 80% of held-out scenarios must pass |
| Code Quality | 15% | Scripts ≥ 90% shellcheck-clean; Go code passes `go vet`; Node passes `eslint --no-eslintrc` |

## Scope

**In scope:** Eight polyglot initialization scripts (Maia, Taygete, Sterope, Alcyone, Electra, Celaeno, Merope, Atlas); owner-escrow signal system; pleiades-swarm policy broker; host-bridge infrastructure; Pleiades Nexus FIFO; `pleiades-request-broker`; regression test suite; owner-invoked factory toolchain wrappers for paper-to-code, skill evolution, and continual harness testing.

**Out of scope:** Gentoo stage3 bootstrapping; bedrock brl/strat reprogramming; alien package format conversion.

## Open Questions

1. Should `pleiades-request-broker` be compiled Go or bash daemon?
2. At what threshold should PLEIADES_NEXUS evict old blocklist entries?
3. Should CELAENO's watchdog interval be per-service or global?
4. When should Pleiades Rebirth Protocol fire its recovery beacon — threshold or time-based?
