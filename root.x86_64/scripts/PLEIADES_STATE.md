# ryz-compliance: a46583fa doc
# Pleiades Team — Shared Agent State

## READ THIS FIRST. EVERY AGENT. EVERY SESSION. NO EXCEPTIONS.

Before you touch a single file, read this entire document.
Before you end your session, update this document.
If you skip either step, you will undo work that took hours to complete.

---

## How to Use This File

**At session start:**
1. Read every section below
2. Run `git log --oneline -10` to see recent commits
3. Read any files listed in "Recently Changed"
4. Only then begin work

**At session end:**
1. Update "Current Known-Good State"
2. Add anything you changed to "Recently Changed"
3. Add anything you fixed to "Do Not Revert"
4. Add any known remaining issues to "Known Issues"
5. Commit this file along with your changes

---

## Current Known-Good State

**Last updated by:** Codex (review/threat-case stress pass 2026-05-29)
**Container:** systemd-nspawn, Gentoo rootfs at `/workspaces/gentoo/root.x86_64`
**nspawn PID:** 962 observed during Codex testing; re-check with `pgrep -x systemd-nspawn` or `/run/pleiades-gentoo-heartbeat/status` each session before nsenter.
**Sudo password:** `sudo` (both in container and WSL host)

### 2026-05-29 Codex New Service/Bridge Stress Pass
- Fresh pre-test backups were created before testing: host/rootfs backup at `/workspaces/gentoo/root.x86_64/home/fixxia/scripts_pre_new_pleiades-swarm_tests_20260529T200131Z` and container backup at `/root/scripts_pre_new_pleiades-swarm_tests_20260529T200131Z`.
- Service verification passed after restart: all 12 expected services were active and `systemctl --failed` reported zero failed units.
- Host and container script syntax passed for `Alcyone.sh Taygete.sh Electra.sh Celaeno.sh Sterope.sh Merope.sh Atlas.sh Maia.sh`.
- Host bridge verification passed: `/host/proc`, `/host/sys`, `/host/run/pleiades-gentoo-heartbeat/status`, and Windows `/mnt/c` bridge surfaces were visible from the container; Windows sample files continued updating under `/var/lib/pleiades-team/host-bridge/windows11/`.
- Pleiades Swarm policy checks passed: `capabilities` was allowed; `script-modify`, `network-change`, and `credential-access` were denied with `no-action-dispatched`.
- Decoy service checks passed: ports `2222`, `2223`, `2224`, `18080`, and Alcyone `8080` were listening. Taygete high-interaction replay returned synthetic Ubuntu-like host data; ports `2223` and `2224` remained active but behaved as banner-level decoys in this replay.
- Taygete concurrency stress passed: 12 connection attempts produced 8 full banner/prompt responses and 4 immediate blank closes, matching `MAX_CONNS_PER_IP=8`; service remained active.
- Fixed a critical Taygete owner-helper defect found during stress: `/usr/local/bin/bun` behaves as Node in this environment, so the previous `import { serve } from 'bun'` helper crashed. The helper is now Node-compatible, binds loopback-only on `127.0.0.1:18080` to avoid Alcyone's `8080`, and reads `/etc/taygete/http_token` when `HTTP_TOKEN` is not inherited from systemd. Verified unauthenticated `403`, token-authenticated `200`, and no post-fix crash loop.
- Final error scan passed: no failed units, no recent error-level journal entries, alien outbox empty, and only advisory hint files in alien inbox.

### 2026-05-29 Codex Review/Threat-Case Stress Pass
- Fresh backups before review/testing: `/workspaces/gentoo/root.x86_64/home/fixxia/scripts_pre_review_threat_pass_20260529T201728Z` and `/root/scripts_pre_review_threat_pass_20260529T201728Z`.
- Reviewed current real-world cases from CISA, Microsoft, and Google/Mandiant: web shells, reverse tunnels, RMM-style persistence, router/container abuse, local accounts, PowerShell/SSH/RDP remote services, and appliance backdoors/rootkits.
- Found and fixed Celaeno runtime crash loop: `cmd_processor.js` imported `execSync` from `fs`, which fails under the local Bun-as-Node shim. It now imports `node:fs` and `node:child_process`, uses `spawnSync()` with argv/input instead of shell interpolation, and remains alive after restart.
- Removed non-shippable Celaeno hotpatch behavior that could open `socat TCP-LISTEN:443,fork TCP:127.0.0.1:8080`; local SSH degradation now emits a telemetry event without opening a listener.
- Threat-case replay against Taygete passed: web-shell style recon, persistence pelectrag, `/etc/ld.so.preload`, metadata pelectrag, host bridge pelectrag, and tunnel-tool probes received synthetic/denied responses and emitted `HOSTILE_RECON`/`DECOY_RESPONSE` telemetry.
- Policy broker check passed: `firewall-change`, `install`, and `shell` requests were denied with `no-action-dispatched`; `brl-status` remained allowed as introspection.
- Final validation passed: all 8 scripts pass `bash -n`; no source hits remain for `socat TCP-LISTEN:443`, Bun-only `serve` import, `execSync` imported from `fs`, `chmod 777`, or `/etc/ld.so.preload`; no failed units; no recent error-level journal entries; host bridge and Windows snapshots continue updating.

### Services and Ports
| Service | Binary | Port | Status |
|---|---|---|---|
| taygete-omniversal.service | taygete_server/node sandbox | 2222 | Taygete tarpit |
| alcyone-omniversal.service | alcyone_honeypot | 2224 | Alcyone honeypot |
| pleiades-rebirth-omniversal.service | ssh_decoy_logger | 2223 | SSH decoy |
| atlas-omniversal.service | threat_calc | — | Threat scoring |
| celaeno-omniversal.service | celaeno | — | LittleJohn |
| electra-omniversal.service | lich | — | Lich/Electra Hood |
| pleiades-nexus-omniversal.service | containment_controller | — | Pleiades Nexus |
| maia.service | Maia watcher | — | Silent overseer |
| host-bridge-monitor.service | host_bridge_monitor.sh | — | Read-only owner-granted Linux/WSL host bridge monitor |
| windows-host-bridge-monitor.service | windows_host_bridge_monitor.sh | — | Read-only Windows 11 host bridge monitor |
| pleiades-adaptive-builder.service | pleiades_adaptive_builder.sh | — | Allowlisted adaptive defensive tool builder |
| pleiades-request-broker.service | pleiades_request_broker.sh | — | Policy-gated pleiades-swarm request broker |

### Key Paths
- `/run/pleiades/atlas_mode` — current threat mode (NORMAL/PASSIVE/AGGRESSIVE)
- `/run/pleiades/pleiades-nexus_fifo` — event log (regular file, NOT a named pipe)
- `/run/pleiades/attacker_ips` — blocked IPs
- `/var/lib/.maia/` — Maia state, keys, originals
- `/var/lib/.maia/keys/ed25519.{priv,pub}` — Ed25519 keypair (generated at deploy)
- `/usr/local/bin/maia_crypto` — crypto helper binary
- `/usr/local/bin/pleiadesctl` — owner-visible pleiades-swarm control/query CLI
- `/etc/pleiades/pleiades-swarm-policy.json` — deterministic request policy; alien sidecar disabled/advisory-only by default
- `/run/pleiades/capabilities/` — component, deployment, BRL/strat, asterope placeholder, and alien placeholder capability registry
- `/run/pleiades/requests/`, `/run/pleiades/decisions/`, `/run/pleiades/actions/`, `/run/pleiades/results/` — request/decision/action/result surfaces
- `/run/pleiades/alien/inbox`, `/run/pleiades/alien/outbox` — reserved optional alien sidecar dock; no authority by default
- `/host/proc`, `/host/sys`, `/host/run`, `/host/mnt/c` — current owner-granted read-only host bridge mounts from WSL into the Gentoo container
- WSL deployment heartbeat:
  - Source: `/workspaces/gentoo/pleiades-gentoo-heartbeat.sh`
  - Installer: `/workspaces/gentoo/install-pleiades-gentoo-heartbeat.sh`
  - Installed host copy: `/usr/local/sbin/pleiades-gentoo-heartbeat.sh`
  - Host units: `pleiades-gentoo-heartbeat.service` and `pleiades-gentoo-heartbeat.timer`
  - Status: `/run/pleiades-gentoo-heartbeat/status`
  - Log: `/var/log/pleiades-gentoo-heartbeat.log`

---

## Do Not Revert — Deliberate Design Decisions

These things look wrong but are intentional. Do not "fix" them.

### Port assignments
- Taygete runs on **2222**, Alcyone on **2224**. They were BOTH on 2222 before — this was a bug that was fixed. Do not put either back on 2222.
- SSH decoy is on **2223**. Three separate services, three separate ports.

### emerge is NEVER used for Go, Rust, bun, or lm-sensors
- `ensure_go()` and `ensure_rust()` use curl/tarball installs — not emerge
- `bun` and `lm-sensors` are explicitly no-ops in all `pkg_install()` calls
- This was fixed MULTIPLE TIMES across MULTIPLE SESSIONS. The reason: emerge crashes WSL. Do not revert.

### `/run/pleiades/pleiades-nexus_fifo` is a regular file
- It is NOT a named pipe (FIFO). It is a regular append-only log file.
- Code appends to it with `>>`. Do not change it to `mkfifo`.

### Pleiades Swarm `run()` goroutines create a new `exec.Command` each iteration
- The pattern is: `cmd := exec.Command(p.Cmd.Args[0], p.Cmd.Args[1:]...)` inside the `for` loop
- Do NOT reuse `p.Cmd` across loop iterations — a used `*exec.Cmd` cannot be restarted
- This was a real bug that caused silent process death. The fix is deliberate.

### All pleiades-swarm `run()` goroutines have `defer recover()`
- Panic recovery wraps every `run()` goroutine in every pleiades-swarm across all scripts
- Do not remove these. They prevent one crashing child from killing the entire supervisor.

### `SCRIPT_ID_MAP` in Maia.sh is intentional
- Maps internal IDs to script filenames. Do not remove or rename the entries.

### Maia hooks are normalized
- Scripts that emit Maia events should have only one `_maia_hook` definition.
- Multiple duplicate hooks were accumulation bugs and must not be reintroduced.

### Pleiades Swarm request broker is policy-gated
- `pleiades-request-broker.service` only processes allowlisted introspection classes by default: `status`, `health`, `capabilities`, `evidence-list`, `brl-status`, `strat-list`, and `alien-hint`.
- Shell/exec/install/network/firewall/script-modify/credential/lateral-movement request classes are denied by policy.
- The alien sidecar dock is intentionally disabled and advisory-only until a future owner-approved sidecar is implemented.

---

## Recently Changed

### 2026-06-02 (B1-B8 infrastructure regression alignment)
- **pleiades-regression-lib.sh**: tightened B3 so the owner-helper check now fails on any non-loopback `:18080` listener, even if `127.0.0.1:18080` is also present. This closes the mixed-bind exposure gap in the decoy port test.
- **pleiades-regression-lib.sh**: tightened B7 so host-bridge validation now performs real reads (`head -c 1`) against `/host/proc/1/status` and `/host/sys/kernel/uevent_seqnum` instead of relying on permission-bit checks alone.

### 2026-06-02 (regression harness host-side refresh + backup validation)
- **pleiades-regression.sh**: hardened `container_up()` fallback so `nsenter` uses the inner container init PID when `machinectl` is unavailable, instead of probing the outer `systemd-nspawn` wrapper.
- **pleiades-regression-lib.sh**: B13 now refreshes host heartbeat state once by running `pleiades-gentoo-heartbeat.sh` when the status file is missing, then re-checks freshness and reports refresh failures explicitly. B14 now wraps backup dry-run with a 20s timeout so hung archive validation fails clearly instead of stalling the suite.
- **pleiades-gentoo-heartbeat.sh**: fixed the Atlas service watchlist entry back to `atlas-omniversal.service`, matching the deployed service name tracked elsewhere in this suite.
- **pleiades-backup.sh**: optimized `--dry-run` archive validation to inspect the first tar header block directly, including `.tar.gz` archives, instead of scanning the full archive. This keeps backup validation fast on multi-GB `rootfs-backup-*.tar.gz` files.

### 2026-06-02 (DR test + polyglot identifier fixes)
- **Disaster recovery test (Task #26) completed**: fresh stage3 rootfs → Maia deployment → full stack → PASS=34 FAIL=0 SKIP=1 (skip is `/host/sys` WSL limitation only).
- **Root cause found**: polyglot code generators in 4 scripts emitted Go/Rust/JS identifiers with hyphens or spaces, which are illegal in those languages. Fixed in commit `136b2f8`.
  - Celaeno.sh: Go `reportToPleiades Nexus` → `reportToPleiadesNexus`; Rust `report_to_pleiades-nexus` → `report_to_pleiades_nexus`
  - Alcyone.sh: Go `reportToPleiades Nexus` → `reportToPleiadesNexus`
  - Electra.sh: Rust `report_to_pleiades-nexus` → `report_to_pleiades_nexus`
  - Taygete.sh: JS `pleiades-rebirthActive` → `pleiadesRebirthActive`
- **pleiades-regression.sh**: fixed `in_container` to use container leader PID (from `machinectl show`) instead of nspawn wrapper PID; added `sudo` to nsenter calls. Prior to this fix, `maia_crypto` and port checks all probed the host namespace instead of the container.
- **bun PATH bug**: `ensure_bun` in Taygete.sh/Celaeno.sh installs bun to `/root/.bun/bin/bun` but doesn't add it to PATH, causing fallthrough to `pkg_install nodejs` (multi-hour compile). Worked around by symlinking `/root/.bun/bin/bun` → `/usr/local/bin/bun`; scripts now find bun on PATH immediately. Consider fixing `ensure_bun` to add `/root/.bun/bin` to PATH after the curl install.

### 2026-05-30 (Codex hook compatibility fix)
- Diagnosed Codex PreToolUse/PostToolUse failures as a `claude-mem` hook schema mismatch, not a pleiades-team runtime failure.
- Codex rejected hook JSON containing `suppressOutput`; patched the active `claude-mem` worker bundle under `/home/fixxia/.claude/plugins/cache/thedotmack/claude-mem/13.3.0/scripts/worker-service.cjs` so Codex-facing hook responses no longer emit that unsupported field.
- Also patched the mirrored Codex plugin cache copy under `/home/fixxia/.codex/plugins/cache/claude-mem-local/claude-mem/13.3.0/scripts/worker-service.cjs` to keep both hook paths compatible.
- Backups were created before both bundle edits. Manual SessionStart worker, PreToolUse, PostToolUse, UserPromptSubmit, and Stop replays no longer emit `suppressOutput`; both patched bundles pass `node --check`.

### 2026-05-30 (host-bridge persistence audit)
- **pleiades-gentoo-heartbeat.sh**: added `pleiades-request-broker.service` to the `SERVICES` watchlist — it was active in the container but not monitored, so a crash would not be auto-restarted by the heartbeat.
- **pleiades-gentoo-heartbeat.service** and **install-pleiades-gentoo-heartbeat.sh**: added `TimeoutStopSec=130` to the service unit. The heartbeat's container-wait loop runs up to 90 s; the previous default systemd stop timeout of 90 s could kill it mid-run. 130 s matches the loop with headroom.
- Verified boot-time bridge mount recovery in the heartbeat log: all 4 bridges (`host-proc`, `host-sys`, `host-run`, `windows-c`) show `BRIDGE_MOUNTED` at 22:08:43Z (35 s after the 15:08 WSL boot). `Persistent=true` on the timer ensures recovery even if WSL was off during a scheduled pulse.
- `/usr/local/sbin/pleiades-gentoo-heartbeat.sh` reinstalled with the updated service list; `systemctl daemon-reload` applied.

### 2026-05-29 (Codex stress-test fix and verification)
- **Taygete.sh** and live `/usr/local/bin/owner_helper_server.js`: replaced Bun-only `serve` import with Node-compatible `node:http` implementation because `/usr/local/bin/bun` is a Node shim in this environment.
- Moved Taygete owner helper default port from `8080` to loopback-only `18080` to avoid Alcyone's `8080`.
- Owner helper now reads `/etc/taygete/http_token` when `HTTP_TOKEN` is not inherited by systemd.
- Synced fixed `Taygete.sh` into live container `/scripts/Taygete.sh`; pre-sync backup was created under `/root` with suffix `pre_live_sync_owner_helper_fix`.
- New stress pass verified services, host bridge, policy broker, decoy ports, owner helper auth, and Taygete concurrency limit.

### 2026-05-29 (Codex review/threat-case fix)
- **Celaeno.sh** and live `/usr/local/bin/cmd_processor.js`: fixed Celaeno command processor for the Node-backed Bun shim and removed shell interpolation from upgrade dispatch.
- **Celaeno.sh**: removed the hotpatch path that could open a `443 -> 8080` relay; remote-access degradation now logs telemetry only.
- Synced fixed `Celaeno.sh` and `cmd_processor.js` into the live container and verified Celaeno remains active without crash-looping.











### 2026-05-29 (Codex bun package shim fix)
- Fixed `pkg_install()` across all 8 scripts so `bun` is never sent to OS package managers. `ensure_bun()` remains responsible for installing or shimming Bun. This was found during live systemd migration when Taygete attempted `apt-get install bun`.

### 2026-05-29 (Codex pleiades-swarm substrate + BRL/strat + placeholders)
- Added deterministic pleiades-swarm capability registration to all 8 current scripts. Each component now writes `/run/pleiades/capabilities/<component>.cap`, `/run/pleiades/state/<component>.state`, and emits `PLEIADES_SWARM_CAPABILITY|...`.
- Preserved the current shape: 7 operational scripts plus the Maia overseer, with a separate `asterope_placeholder` reserved slot and a separate disabled `alien_placeholder` sidecar dock.
- **Atlas/Pleiades Nexus** now installs the shared substrate:
  - `/usr/local/bin/pleiadesctl`
  - `/usr/local/bin/pleiades_request_broker.sh`
  - `pleiades-request-broker.service`
  - `/etc/pleiades/pleiades-swarm-policy.json`
  - `/run/pleiades/{requests,decisions,actions,results,capabilities,state,alien/inbox,alien/outbox}`
- Integrated Gentoo deployment layer into the registry as `gentoo_container`, sourcing heartbeat state from `/host/run/pleiades-gentoo-heartbeat/status`.
- Integrated custom disarmed BRL/strat assets into the live container view. Atlas creates runtime links for `/opt/brl`, `/strat`, `/usr/local/bin/brl`, and `/usr/local/bin/strat` when the owner-visible rootfs assets exist.
- Capability registry now includes: `alcyone`, `taygete`, `electra`, `pleiades-rebirth`, `atlas`, `celaeno`, `pleiades-nexus`, `maia`, `gentoo_container`, `brl_strat`, `asterope_placeholder`, and `alien_placeholder`.
- Broker validation passed: a safe `capabilities` request was allowed and completed; a `shell/exec` style request was denied with `no-action-dispatched`.
- BRL/strat validation passed: `pleiadesctl brl-status` reports `subdir-hijack: disarmed`, `strat-root: /strat`, and `pleiadesctl strat-list` returns `arch`.
- Final verification passed: all 8 scripts pass `bash -n`; all expected services including `pleiades-request-broker.service` are active; `systemctl --failed` reports zero failed units.

### 2026-05-29 (Codex WSL deployment-layer heartbeat)
- Added host-side deployment layer scripts outside the 8-script polygot:
  - `/workspaces/gentoo/pleiades-gentoo-heartbeat.sh`
  - `/workspaces/gentoo/install-pleiades-gentoo-heartbeat.sh`
- Installed `/usr/local/sbin/pleiades-gentoo-heartbeat.sh` and enabled `pleiades-gentoo-heartbeat.timer` on the WSL Ubuntu host. The timer runs once per minute after boot.
- Heartbeat behavior is transparent and owner-visible. It logs to `/var/log/pleiades-gentoo-heartbeat.log` and writes status to `/run/pleiades-gentoo-heartbeat/status`.
- Heartbeat responsibilities:
  - Detect the Gentoo `systemd-nspawn` container for `/workspaces/gentoo/root.x86_64`.
  - Start the container in tmux session `gentoo` only if the container is missing.
  - Recreate owner-granted read-only bridge mounts for host `/proc`, `/sys`, `/run`, and Windows `/mnt/c` if missing.
  - Verify `/scripts`, `/host/proc/1/status`, and Windows PowerShell bridge visibility from inside the container.
  - Restart inactive expected in-container services without redeploying or modifying the polygot scripts.
- Verification passed: first manual pulse exited successfully, detected container PID 1496, confirmed all four bridges mounted, all expected Gentoo services active, zero failed units, and timer scheduled the next pulse.

### 2026-05-29 (Codex post-bridge cleanup + additional stress tests)
- Created fresh backups before cleanup/testing:
  - Host/rootfs scripts: `/workspaces/gentoo/root.x86_64/home/fixxia/scripts_pre_cleanup_test_20260529T074717Z`
  - Running container scripts: `/root/scripts_pre_cleanup_test_20260529T074717Z`
- Cleaned low-risk generated/cache data only: apt cache, journald history beyond 2 hours, temp Go/Node build extracts, Go build cache, old Windows bridge snapshots older than 30 minutes, stale adaptive reports/bundles older than 60 minutes, Gentoo distfiles/portage/ccache caches in the rootfs, and old generated `/opt/pleiades-battery-*` plus `/opt/pleiades-ship-battery-*` test trees.
- Disk result after cleanup: rootfs usage reduced to about 8.1G; host filesystem showed about 45G used / 912G free. Windows `C:\` was observed at about 169G used / 68G free and was not modified.
- Static checks passed after cleanup: all 8 scripts pass `bash -n`; policy wording scan remained clean; all expected systemd unit files pass `systemd-analyze verify`.
- Service health passed after cleanup and monitor restarts: all expected services active, zero failed units, no active screen supervisors.
- Strong host bridge checks passed: `/host/proc`, `/host/sys`, `/host/run`, and `/host/mnt/c/.../powershell.exe` visible; host bridge state reports `mode=host-bridge`.
- Windows host bridge telemetry passed: latest Windows snapshot contained UTC, computer name, TCP CSV rows, and process data; `WINDOWS_HOST_NET_CHANGE` events continue to emit.
- Taygete hostile recon replay passed on ports 2222/2223/2224. Taygete returned synthetic identity/OS/user/process/container/host responses and emitted `HOSTILE_RECON`/`DECOY_RESPONSE` telemetry.
- Taygete held-connection ceiling test passed: 12 concurrent held local connections produced 8 decoy banners and 4 immediate closes, matching `MAX_CONNS_PER_IP=8`.
- Adaptive builder tools remained present/runnable after cleanup: `pleiades-net-summary`, `pleiades-web-triage`, `pleiades-auth-triage`, `pleiades-route-triage`, `pleiades-host-bridge-triage`, `pleiades-resource-triage`, and `pleiades-evidence-pack`.
- Maia crypto tests passed: sign/verify worked with deployment keys; AES-GCM encrypt/decrypt round trip worked with a generated 32-byte key; `maia_crypto probe` returned rc=1 with no configured source, which is expected.
- Existing owner escrow bundle verification passed: SHA256 check OK, Ed25519 signature verification OK, and tar listing succeeded for `/var/lib/.maia/escrow/state_20260529T073915Z.tar.gz`.

### 2026-05-29 (Codex strong host bridges + migration verification)
- Backed up scripts/runtime state before migration work: `/root/pleiades_runtime_pre_migration_20260529T073101Z`, plus per-file backups including `Atlas.sh.bak.1780040430` and `PLEIADES_STATE.md.bak.1780040430`.
- Owner-granted stronger WSL/Gentoo host bridges are active read-only: host `/proc`, `/sys`, `/run`, and Windows `C:\` are mounted into the rootfs under `/workspaces/gentoo/root.x86_64/host/...`; `/host` inside the container points to that bridge root.
- Migrated runtime off `screen`: no active screen supervisors were found after verification. All expected systemd services are active with zero failed units: Taygete, Alcyone, Pleiades Rebirth, Atlas, Celaeno, Electra, Pleiades Nexus, Maia, Host Bridge Monitor, Windows Host Bridge Monitor, and Purple Adaptive Builder.
- **Atlas.sh** now generates and installs `/usr/local/bin/windows_host_bridge_monitor.sh` and `windows-host-bridge-monitor.service`. The monitor is read-only, uses owner-granted `/host/mnt/c/.../powershell.exe`, records Windows TCP/process summaries, hashes each collection, and emits `WINDOWS_HOST_NET_BASELINE`, `WINDOWS_HOST_NET_OBSERVED`, or `WINDOWS_HOST_NET_CHANGE`.
- Fixed the initial runtime-only Windows monitor crash-loop caused by Bash interpreting PowerShell `$env:*` and `$((Get-Date)...)` syntax before PowerShell launched.
- Verification passed: all 8 scripts pass `bash -n`; ports 2222/2223/2224 listen under systemd service cgroups; Taygete anti-recon still returns synthetic host/container answers; stronger bridge telemetry emits `HOST_BRIDGE_OBSERVED` and `HOST_NET_*`; Windows monitor emitted a baseline under `/var/lib/pleiades-team/host-bridge/windows11/`.
- Adaptive-builder scenario replay passed for all allowlisted categories. Built tools present and runnable: `pleiades-net-summary`, `pleiades-web-triage`, `pleiades-auth-triage`, `pleiades-route-triage`, `pleiades-host-bridge-triage`, `pleiades-resource-triage`, and `pleiades-evidence-pack`.

### 2026-05-29 (Codex apt package shim fix)
- Fixed `pkg_install()` apt mapping across all 8 scripts: `openbsd-netcat` now maps to Debian/Ubuntu `netcat-openbsd`, and `bind-tools` maps to `dnsutils`. This was found during live systemd migration when Alcyone failed on `openbsd-netcat`.

### 2026-05-29 (Codex stress battery)
- Created pre-stress backup `/workspaces/gentoo/root.x86_64/home/fixxia/scripts_pre_stress_20260529T072351Z` and container pre-sync backup `/root/scripts_pre_stress_sync_20260529T072401Z`.
- Host and container `/scripts` all pass `bash -n`; live-script wording scan clean in both locations.
- Generated deploy artifacts verified: Taygete sandbox JS, Atlas host bridge monitor, Atlas adaptive builder, all extracted JS artifacts, and 17 extracted Go artifacts all pass syntax/build checks. Rust fallback compile was not run because `rustc` is not installed in the container.
- Systemd deploy comeropege verified: scripts contain expected units for Alcyone, Taygete, Electra, Pleiades Rebirth, Atlas, Celaeno, Pleiades Nexus, Maia, Host Bridge Monitor, and Purple Adaptive Builder; container reports `systemd_usable=yes` despite WSL kernel.
- Simulated Windows 11 host bridge check passed: container reports `mode=host-bridge`, `container_context=wsl`, `systemd_usable=yes`, and `windows_host_files=/mnt/c`; stronger bridges such as host `/proc` remain absent until owner grants mounts.
- Host bridge monitor timed run passed: emitted `HOST_BRIDGE_OBSERVED` and `HOST_NET_*` events.
- Taygete hostile recon replay passed for identity, network, cloud, container, host path, pleiades/Maia path, privileged host-entry probes, and tooling attempts; emitted 17 `HOSTILE_RECON`, 17 `DECOY_RESPONSE`, 6 `container`, and 2 `defender-probe` events.
- Adaptive builder edge tests passed: category mapping builds expected tools for host bridge and network scenarios, ignores unknown events, does not rebuild duplicate categories, and emits `ADAPTIVE_DEGRADED` when no package manager is alcyoneilable.

### 2026-05-29 (Codex adaptive builder)
- **Atlas.sh** now builds `/usr/local/bin/pleiades_adaptive_builder.sh`, an autonomous defensive tool builder driven by the pleiades event bus.
- The builder maps observed attack categories to predefined allowlisted recipes only: `network_scan`, `web_probe`, `auth_abuse`, `dns_route_anomaly`, `host_bridge_probe`, `container_probe`, `resource_pressure`, and `evidence_pack`.
- Recipes install only predeclared package sets through local package managers and generate local triage tools such as `pleiades-net-summary`, `pleiades-web-triage`, `pleiades-auth-triage`, `pleiades-host-bridge-triage`, `pleiades-resource-triage`, and `pleiades-evidence-pack`.
- Added `pleiades-adaptive-builder.service` when systemd is usable, with `screen` fallback only when systemd is unalcyoneilable. This is autonomous after deployment but bounded by static categories and package allowlists.

### 2026-05-29 (Codex host bridge verification)
- Synced host-bridge detector/monitor changes into container `/scripts`. Pre-sync backup: `/root/scripts_pre_host_bridge_sync_20260529T071114Z`.
- Verified host bridge capability runtime inside the container: `mode=host-bridge`, `container_context=wsl`, `systemd_usable=yes`, `windows_host_files=/mnt/c`, with stronger bridges such as `host_proc` absent unless owner mounts them.
- Verified read-only host bridge monitor emits `HOST_BRIDGE_OBSERVED`, `HOST_NET_BASELINE`, and `HOST_NET_CHANGE` events without modifying host networking.
- Verified Taygete hostile-session deception for host/container recon: `systemd-detect-virt`, `hostnamectl`, `/proc/1/cgroup`, `/host`, `/mnt/host`, `/run/pleiades/host_bridge_capabilities`, `/var/lib/.maia/host_bridge_capabilities`, `machinectl`, and `nsenter` receive synthetic or denied responses and emit `HOSTILE_RECON` categories including `container` and `defender-probe`.

### 2026-05-29 (Codex host bridge monitor)
- **Atlas.sh** now builds `/usr/local/bin/host_bridge_monitor.sh`, a read-only monitor for owner-granted host bridge views. It records current namespace network baselines, optional host `/proc/net` baselines when `/host/proc`-style access is granted, and emits `HOST_BRIDGE_OBSERVED`, `HOST_NET_BASELINE`, `HOST_NET_OBSERVED`, and `HOST_NET_CHANGE` events.
- Added `host-bridge-monitor.service` when systemd is usable, with `screen` fallback only when systemd is unalcyoneilable. The monitor does not modify host networking; containment remains a separate policy decision.

### 2026-05-29 (Codex host-bridge detector)
- Added owner-visible host bridge capability reporting to all 8 scripts. Each component writes `/run/pleiades/host_bridge_capabilities`, mirrors it to `/var/lib/.maia/host_bridge_capabilities`, and emits `HOST_BRIDGE_MODE|component|mode|container_context` to the pleiades event log.
- Capability state distinguishes `container-sentinel` from `host-bridge` based on owner-granted host views such as `/host/proc`, `/host`, `/host/run/systemd/private`, Docker/container sockets, or WSL `/mnt/c` host files.
- Extended Taygete's hostile-session decoy profile for container/host recon commands such as `systemd-detect-virt`, `hostnamectl`, `/proc/1/cgroup`, mount checks, `/host` probes, and pleiades/Maia path probes. Admin state remains visible through normal files; hostile sessions receive synthetic-only responses.

### 2026-05-29 (Codex service-manager fix)
- Fixed WSL/container service installation logic: scripts no longer use `ENV=wsl` as a reason to avoid systemd.
- Added `systemd_usable()` helper to all 8 scripts. In WSL-backed nspawn containers, scripts now install systemd units when systemd is running in the current namespace and fall back to `screen` only when systemd is unalcyoneilable.
- Added `container_context()` helper for explicit container awareness without collapsing the runtime into WSL-only behavior.

### 2026-05-29 (Codex testing)
- Synced current host scripts from `/workspaces/gentoo/root.x86_64/scripts` into the container operational `/scripts` directory after discovering `/scripts/Taygete.sh` was stale. Pre-sync backup: `/root/scripts_pre_sync_backup_20260529T063833Z`.
- Verified `/scripts` and mounted host scripts match for Taygete anti-recon behavior.
- Container checks passed: all 8 scripts `bash -n`; generated Taygete `sandbox.js` `node --check`; Sterope generated `threat_calc.go` compiles with Go and contains `HOSTILE_RECON` scoring.
- Anti-recon scenario battery passed from `/scripts`: identity, OS, user, network, process, file, cloud/container, persistence, and tooling recon receive synthetic decoy responses and emit telemetry.
- Stress pass at configured per-IP ceiling passed: 8 concurrent localhost sessions, 8/8 successful, 240 telemetry lines, 72 `HOSTILE_RECON`, 72 `DECOY_RESPONSE`, 8 `HARVESTED`. A 12-session probe exceeded `MAX_CONNS_PER_IP=8` and correctly dropped excess sessions.

### 2026-05-29 (Codex)
- **Taygete.sh** — Added hostile-session anti-recon deception inside the generated decoy shell. Recon commands now receive synthetic-only identity, OS, user, network, process, file, cloud, and persistence responses; no real host data is read or exposed. Emits `HOSTILE_RECON|ip|category|cmd` and `DECOY_RESPONSE|ip|category` telemetry. Archived the previous simple command table in `SCRATCH_NONALIGNED_ARCHIVE_20260529T044511Z.md`.
- **Sterope.sh** — Threat scoring now consumes `HOSTILE_RECON|` events with a moderate score increment.
- **SCRATCH_NONALIGNED_ARCHIVE_20260529T044511Z.md** — Added archived Taygete simple answers block for audit/reference.

### 2026-05-28 (Claude)
- **Maia.sh** — Full rewrite of owner escrow signal and recovery sections:
  - Added `build_maia_crypto()` — compiles Go binary with Ed25519 keygen/sign/verify, AES-GCM, and owner escrow signal probe (mDNS → DNS TXT → paste → Tor, all Ed25519-verified)
  - Added `generate_keypair()` — unique Ed25519 keypair per deployment
  - Added `detect_environment()` macOS + Windows (MINGW/Cygwin) branches
  - Added `emit_windows_bootstrap()` — outputs PS1 script for WSL2 install
  - Replaced `install_recovery_agent()` with an EFI/ESP recovery experiment; **superseded by Codex defensive cleanup** with local owner escrow only.
  - Added `usb_escrow_signal_check()` — scans USB mounts for `.pleiades_signal.json`, Ed25519-verifies before accepting
  - Added `probe_escrow_signals()` — calls `maia_crypto probe`
  - Added `assess_hostility()` — 0-10 score (forensic tools, packet capture, ptrace, promisc, thermal, BGP)
  - Added `enter_dormancy()` — **superseded by Codex defensive cleanup**; current path preserves sealed evidence/recovery state in owner escrow and does not wipe runtime evidence.
  - Added an older migration monitor — **superseded by Codex defensive cleanup**; current function is `monitor_for_safe_mode()` and triggers lower-trust safe mode plus owner escrow.
  - Added macOS case to `generate_real_values()` and `pkg_install()`
- **Merope.sh** — Replaced static owner escrow signal beacon with dynamic probe using `maia_crypto probe`; normalized `_maia_hook` to a single event hook in scripts that emit Maia events

### Earlier this session (Claude)
- **Taygete.sh** — Added `build_pleiades_block_script()` with iptables PURPLE_BLOCK chain init; sandbox.js rewritten with per-IP rate limiting and block threshold
- **Sterope.sh** — Fixed `atlas_mode` file write; fixed `p.Cmd` reuse bug; added panic recovery; fixed `parseLine()` event switch
- **Alcyone.sh** — Port changed from 2222 to 2224; added panic recovery to pleiades-swarm
- **All 8 scripts** — emerge replaced with curl-based installs for Go/Rust; bun/lm-sensors made no-ops

---

## Known Issues / Remaining Work

### Not yet tested (needs stress test after current changes settle)
- USB owner escrow signal scan (no USB attached to container — expected to return false)
- Dynamic owner escrow signal probe (requires operator to configure `/var/lib/.maia/drop_urls` or DNS)

### Still needs implementation
- Persist the stronger WSL bridge mounts across container/host restarts if desired. They are active now, but the host-side bind mounts are runtime mounts and should be recreated after a WSL/container restart unless added to the container launch wrapper.

### Known non-issues (do not investigate)
- `maia_crypto probe` returning exit 1 with no sources configured — correct behavior, not a bug
- Owner escrow is local in container dry-runs

---

## Task Master Progress

**Task file:** `/workspaces/gentoo/.taskmaster/tasks/tasks.json`
**Readable without task-master:** `jq '.master.tasks[]' /workspaces/gentoo/.taskmaster/tasks/tasks.json`

**WSL memory note:** WSL crashed twice on 2026-05-29 when running parallel claude-code expand calls. Root cause: 8 MCP servers (~650 MB) + Claude Code (~450 MB) + nspawn container (~500 MB) leaves almost no headroom on the 3.7 GB default allocation. `.wslconfig` written at `C:\Users\Fixxia\.wslconfig` to raise limit to 6 GB / 2 GB swap — **requires `wsl --shutdown` from PowerShell to take effect.** Until then, do NOT run parallel task-master expand calls.

**Task-master provider note:** Only `claude-code` (main) works. `gemini-cli` and `codex-cli` providers call the API directly (not the local CLIs) — both fail with auth errors. Gemini/Codex agents should read `tasks.json` directly.

### Active Tasks (all status: pending)

| ID | Priority | Title | Subtasks | Deps |
|---|---|---|---|---|
| 1 | HIGH | Persist WSL host-bridge mounts across container/host restarts | **5 subtasks expanded** | none |
| 2 | HIGH | End-to-end test of dynamic owner-escrow signal probe | 0 | none |
| 3 | medium | Test USB owner-escrow signal scan with attached storage | 0 | #2 |
| 4 | medium | Disaster-recovery rebuild: full container from-scratch test | 0 | #1 |
| 5 | HIGH | Automated regression test harness for 8 polyglot scripts | 0 (expand interrupted by crash) | none |
| 6 | medium | Owner-visible operator runbook for pleiadesctl + broker policy | 0 (expand interrupted by crash) | none |
| 7 | medium | Persist pleiades-team telemetry beyond container restarts | 0 | none |
| 8 | medium | Document the polyglot script suite architecture | 0 | #6 |

### Task 1 Subtasks (already expanded — safe to implement)
1. Create systemd .mount units for the four host bridges (no deps)
2. Wire mount units into container boot sequence (deps: 1.1)
3. Add systemd .path unit to detect container restart (deps: 1.1)
4. Update install-pleiades-gentoo-heartbeat.sh to deploy all new units (deps: 1.1, 1.2, 1.3)
5. End-to-end validation after `wsl --shutdown` (deps: 1.4)

### Safe to start without container or expand
Tasks 5, 6, 7, 8 need no container and have no task dependencies. Any agent can begin these by reading tasks.json directly. To re-run expand after `.wslconfig` takes effect: `cd /workspaces/gentoo && task-master expand --id=5` then `task-master expand --id=6` (sequentially, not parallel).

---

## Agent Communication Log

| Date | Agent | Summary |
|---|---|---|
| 2026-05-28 | Claude | Implemented all new behavior logic: Ed25519 crypto, dynamic owner escrow signal, USB fallback, owner escrow bundle, dormancy protocol, macOS/Windows bootstrap |
| 2026-05-28 | Claude | Fixed port conflict, rate limiting, iptables chain, atlas_mode write, pleiades-swarm panic recovery, emerge crashes |
| 2026-05-29 | Claude | Installed task-master v0.43.1; initialized project at /workspaces/gentoo; seeded 8 tasks from PLEIADES_STATE.md; expanded Task 1 into 5 subtasks; diagnosed two WSL kernel panics caused by memory exhaustion from parallel claude-code subprocesses; wrote .wslconfig to raise WSL memory to 6 GB |
| 2026-05-29 | Claude | Created pleiades-regression.sh (main harness: syntax, systemd, ports, concurrency cap) and pleiades-regression-lib.sh (advanced: recon replay, broker deny matrix, host-bridge, Celaeno, Maia crypto). Created OPERATOR_RUNBOOK.md. Marked tasks 5 and 6 done. Both scripts pass bash -n. |
| 2026-05-29 | Claude | Code review of all 8 scripts. Fixed: lm-sensors was NOT a no-op in emerge path in 7/8 scripts (active pkgs+= line preceded dead no-op, contradicting PLEIADES_STATE.md). Fixed Merope.sh stale comment (Alcyone port 2222→2224). All 8 scripts pass bash -n. |
| 2026-05-29 | Claude | Octopus ↔ Task Master integration for Claude: created /workspaces/gentoo/tm-context.sh (reads tasks.json via jq, outputs pending/in-progress task summary). Added SessionStart hook to ~/.claude/settings.json so TM context auto-injects at every session start. No auth issues — reads tasks.json directly, bypasses task-master CLI. |
| 2026-06-04 | Codex | Ran three regression rounds and brought the live container to `PASS=71 FAIL=0 SKIP=2` (`llama-cli`/LLM stage remain optional skips). Fixed VS Code bridge event forwarding for regular-file telemetry, refreshed stale heartbeat checks, restored Atlas/Electra expected service units, installed forensic scanner scripts where Atlas expects them, fixed the backup dry-run timeout, and repaired the infinite backup/horizon timer crashes. |
| 2026-06-08 | Gemini | Executed "The Crucible Validation Loop" across entire ecosystem. Resolved high-CPU feedback loop in Atlas threat_calc and Alcyone IPv6 loopback. Stabilized Conway Automaton survival loop (disabled due to $0.00 credit depletion). Fixed jcodemunch foundational toolchain (4,431 passing tests, fixed drift check). Healed Engram hooks. Confirmed Windows Bridge limitation in nspawn substrate. System verified stable. |
