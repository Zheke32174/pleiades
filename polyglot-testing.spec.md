---
nlspec: "1.0"
title: Pleiades-Team Polyglot Script Suite — Testing Battery & Bug Fixes
satisfaction_target: 0.85
complexity: high
---

## Purpose

Produce a comprehensive testing battery for the pleiades-team polyglot script suite — the collection of Bash scripts (`Ava.sh`, `Beryl.sh`, `Eris.sh`, `Mariah.sh`, `Sterope.sh`, `Merope.sh`, `Atlas.sh`, `SofiaX.sh`) deployed inside a systemd-nspawn Gentoo container, plus the WSL host-side scripts (`pleiades-gentoo-heartbeat.sh`, `purple-host-process-sensor.sh`, `pleiades-backup.sh`). The goal is: catch regressions before they reach production, surface current bugs, and ship fixes for any found.

All scripts share a pleiades-swarm architecture with a deterministic policy broker (`/etc/pleiades/pleiades-swarm-policy.json`), capability registration (`/run/pleiades/capabilities/`), and append-only event log (`/run/pleiades/pleiades_nexus_fifo`). Tests run inside the container via `nsenter` when container is up, or skip gracefully when it is down.

## Actors

- **Test harness**: `pleiades-regression.sh` (orchestrator) + `pleiades-regression-lib.sh` (test library)
- **Container**: systemd-nspawn Gentoo rootfs at `/workspaces/gentoo/root.x86_64`
- **Host**: WSL2 Ubuntu running heartbeat/sensor/backup scripts
- **Policy broker**: `pleiades-request-broker.service` reading from `/run/pleiades/requests/`
- **Owner operator**: runs tests and reads results at `/var/log/pleiades-regression/last-run.json`

## Behaviors

### B1 — Syntax gate: all 8 scripts pass `bash -n`
All container scripts (`Ava Beryl Eris Mariah Sterope Merope Atlas SofiaX`) must have zero syntax errors under `bash -n`. Failure of any single script is a hard FAIL.

### B2 — All 12 systemd services active after container restart
After `systemctl daemon-reload` inside the container, all 12 services must report `active (running)` and `systemctl --failed` must report zero failed units. Test must detect partial-start (some active, some failed).

### B3 — Decoy port liveness: 2222, 2223, 2224, 18080
Ports 2222 (Taygete tarpit), 2223 (SSH decoy), 2224 (Alcyone honeypot) must be listening. Owner-helper must be listening on `127.0.0.1:18080` (loopback-only). Test via `ss -tlnp` inside container.

### B4 — Taygete concurrency cap enforced (MAX_CONNS_PER_IP=8)
12 simultaneous connections from 127.0.0.1 to port 2222 must produce ≤8 banner responses. Any result >8 is a FAIL (cap not enforced).

### B5 — Hostile-recon replay: synthetic responses, real hostname not leaked
Sending `id`, `uname -a`, and `cat /etc/passwd` to Taygete port 2222 must: (a) return synthetic/fictional data, (b) not expose the real hostname, (c) emit ≥1 new line to `/run/pleiades/pleiades_nexus_fifo` per probe.

### B6 — Policy broker deny matrix: shell/exec denied, capabilities/list allowed
Writing a `shell/exec` class request to `/run/pleiades/requests/` must produce a `decision=deny` + `no-action-dispatched` within 5 seconds. Writing a `capabilities/list` class request must produce `decision=allow` or at minimum not be denied. Test cleans up temp files after each assertion.

### B7 — Host bridge mounts readable from container
`/host/proc/1/status` and `/host/sys/kernel/uevent_seqnum` must be readable from inside the container. If mounts not present, test skips (not fails) — mounts are owner-optional.

### B8 — Windows host-bridge snapshots fresh
Files under `/var/lib/pleiades-team/host-bridge/windows11/` inside the container must include at least one `*.txt` modified within the last 5 minutes. Skip (not fail) if the monitor service was just started.

### B9 — Celaeno: service active, cmd surface present, no crash-loop
`celaeno-omniversal.service` must be active. `/run/pleiades/celaeno_cmd` must exist. Restart count in last 2 minutes (from journal) must be ≤2.

### B10 — Maia crypto round-trip: sign + verify succeeds
`/usr/local/bin/maia_crypto sign <file>` must produce a non-empty hex signature. `maia_crypto verify <file> <sig>` must exit 0 with that same file+sig pair.

### B11 — pleiades_nexus_fifo is a regular file, NOT a named pipe
`file /run/pleiades/pleiades_nexus_fifo` inside the container must report a regular file (not FIFO). This guards against a recurring regression where agents change it to `mkfifo`.

### B12 — Pleiades Swarm policy file is deterministic and unchanged
`/etc/pleiades/pleiades-swarm-policy.json` must exist, be valid JSON, have `"mode": "owner-authorized-defensive"`, `"default_request_decision": "deny"`, and `"alien_sidecar": {"enabled": false}`. Any drift is a FAIL.

### B13 — Host heartbeat status file fresh (host-side test)
`/run/pleiades-gentoo-heartbeat/status` on the WSL host must exist and have `status=running` with a timestamp within the last 2 minutes.

### B14 — Backup script produces valid archives
Running `pleiades-backup.sh --dry-run` (or checking last-backup metadata) must confirm that backup archives exist at the expected path and are non-zero-byte tar files.

### B15 — purplectl CLI responds to basic queries
`purplectl status` inside the container must exit 0 and print component names. `purplectl help` or `purplectl` alone must not segfault or crash.

### B16 — Alien sidecar has no authority (advisory-only enforcement)
Checking `/etc/pleiades/pleiades-swarm-policy.json` and live container state: alien sidecar outbox must be empty (or contain only hint-type entries). No alien-originated action should appear in `/run/pleiades/actions/`.

## Constraints

- Tests must run non-interactively (no stdin prompts).
- Container-dependent tests must skip gracefully (not fail) when container is down.
- Each test must emit a clear `PASS`, `FAIL`, or `SKIP` line matching the existing harness format.
- Tests must clean up any temp files or request artifacts they create.
- No `emerge`, `bun`-native imports, or named-pipe mkfifo calls allowed in any test script.
- The entire test suite must complete in ≤5 minutes when container is running.
- `pleiades-regression.sh --skip-container` must run in <10 seconds (syntax-only fast path).
- Any bug found during implementation must be fixed in the script under test, not worked around in the harness.

## Acceptance Criteria

- All B1-B16 behaviors are implemented as runnable test functions in `pleiades-regression.sh` and `pleiades-regression-lib.sh`.
- Running `bash pleiades-regression.sh` produces a valid `last-run.json` with `"result": "PASS"` when the container is healthy.
- No existing passing tests are broken by adding the new ones.
- Bugs surfaced by new tests (B11, B12, B13 especially) are fixed at the source.
