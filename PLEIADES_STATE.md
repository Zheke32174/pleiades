# Pleiades Team Project - State Tracking

## Current Status
- **Date**: 2026-06-01
- **Environment**: WSL2 / Gentoo nspawn container
- **Heartbeat**: Stable (v0.2.1: Extended timeouts, tmux watchdog, pgrep fix).
- **Sensor**: Active (v0.2.0: jq-based JSON, seen-cache de-duplication, log rotation).
- **VM Build**: Improved (v0.1.1: Cleanup trap, better rsync exclusions).

## Recent Changes
- **Ship-readiness pass (2026-06-01)**: DGX→bare_metal migration across all 5 agent scripts (IS_BARE_METAL, systemd-detect-virt detection, bare_metal env). Electra.sh: sysmon-idle→sysmon-idle, electra_pleiades-swarm→sysmon-daemon, electra-omniversal.service→machine-runtime-monitor.service. Maia.sh: removed efivarfs write (forbidden), restored WSL registry bridge, replaced ESP stub with real find_esp() using PowerShell Get-Partition (WSL) and lsblk PARTTYPE (bare metal). New: install-boot-persistence.sh (WSL wsl.conf + bare metal systemd + chattr hardening + owner escape hatch). New: pleiades-selfdestruct.sh (evidence collect→encrypt→push to pleiades-evidence→ESP auth persist→dead drop signal→wipe). Created Zheke32174/pleiades-evidence private repo. Created AGENTS.md (cross-CLI context). Memory files written to ~/.claude/projects/-/memory/. README updated with companion repos.
- **Global Bug Fix Pass**: Fixed heartbeat bridge false positives by making status checks validate the container namespace, adding explicit `systemd-nspawn --bind-ro` host bridges for `/proc`, `/sys`, `/run`, and `/mnt/c`, and restarting the container when required Linux bridges are missing from inside nspawn. Fixed automatic recovery for a missing `windows-host-bridge-monitor.service` once `/host/mnt/c` becomes visible. Fixed regression backup discovery from `root.x86_64/scripts` to resolve `/workspaces/gentoo/pleiades-backup.sh`. Reinstalled `/usr/local/sbin/pleiades-gentoo-heartbeat.sh`; live status now reports all four bridges mounted inside container PID `115620`. Regression after fix: `PASS=48 FAIL=0 SKIP=0`.
- **Task Master Closeout Pass**: Added regression coverage for signed owner-escrow paste probes, USB/loopback `.pleiades_signal.json` scans, and telemetry archive persistence. Fixed `Maia.sh` USB scan so an empty EFI location no longer skips every candidate mount. Added heartbeat-managed `/var/lib/pleiades/archive` copy-and-truncate telemetry archival. Added `root.x86_64/scripts/ARCHITECTURE.md`. Regression after closeout: `PASS=52 FAIL=0 SKIP=0`. Marked Task Master #2, #3, #7, and #8 done; #1 still needs a physical WSL restart validation and #4 still needs an explicitly destructive/disposable rebuild run.
- **Host Contamination Cleanup**: Found WSL-host systemd copies of the purple suite services enabled outside the nspawn container. Backed up `/etc/systemd/system/{taygete,alcyone,host-bridge-monitor,celaeno,pleiades-nexus,pleiades-adaptive-builder,pleiades-request-broker,pleiades-rebirth,electra,maia,windows-host-bridge-monitor,zod}*.service` to `.bak.1780150964`, disabled/stopped the host duplicates, restarted the affected in-container decoys, and verified the container owns ports 2222/2223/2224/8080/18080. Regression after cleanup: `PASS=45 FAIL=0 SKIP=2`.
- **Factory Toolchain Integration**: Added `pleiades-factory-tools.sh` and installed `/usr/local/sbin/pleiades-factory-tools`. Integrated `paper2code`, `hermes-agent-self-evolution`, and `continual-harness` under `/workspaces/gentoo/tools/`, with factory manifest `.octo/factory/toolchain.json` and NLSpec/factory spec entries.
- **Heartbeat Recovery Fix**: Fixed the host heartbeat restart path to use a consistent private tmux socket, record the inner init PID for `nsenter`, avoid `--keep-unit` for heartbeat-started nspawn, and set `KillMode=process` on the host heartbeat unit.
- **Regression Harness Fix**: Fixed `pleiades-regression.sh` to enter the container via the inner init PID instead of the outer `systemd-nspawn` wrapper and to fall back to `/tmp/pleiades-regression` when `/var/log/pleiades-regression` is not writable.
- **Maia Hook Normalization**: Removed duplicate `_maia_hook()` definitions reintroduced in the active script suite; all 8 scripts now have exactly one hook definition.
- **Git Initialization**: Created local git repository plan for project name `pleiades`. `.gitignore` now excludes raw images, stage3 archives, backups, and the live Gentoo rootfs by default while explicitly allowing the active script suite under `root.x86_64/scripts/`.
- **Backup Harness**: Added `/workspaces/gentoo/pleiades-backup.sh` and `/workspaces/gentoo/test-pleiades-backups.sh`; `install-pleiades-gentoo-heartbeat.sh` now uses the shared helper when present. Backups get unique agent/PID suffixes and a `.pleiades-backups/manifest.jsonl` entry so concurrent Codex/Claude/Gemini/Octopus edits do not overwrite each other.
- **Codex Task Master Hook**: Codex-owned `~/.codex/hooks.json` SessionStart hook now calls `/workspaces/gentoo/tm-context.sh` with a 5s timeout. The bridge reads `.taskmaster/tasks/tasks.json` directly with `jq` to avoid blocking on the Task Master CLI during session startup.
- **Stabilization**: Fixed container PID detection to avoid `nsenter` failures caused by `pgrep` matching the script itself.
- **Sensor Deployment**: Installed and activated `pleiades-host-process-sensor` as a systemd timer (every 30s).
- **Logging**: Implemented self-managed log rotation for `/var/log/pleiades-gentoo-heartbeat.log` and `/run/pleiades-host-capsule/process-alerts.jsonl`.
- **Build Improvements**: Added an EXIT trap to `build-pleiades-vm.sh` to ensure `/tmp/pleiades-qemu-mount` is always unmounted on failure.
- **Consistency**: Synchronized `/usr/local/sbin` with workspace files.

## Known Issues / Tasks
- [ ] WSL host restart half of Task #1 still needs a physical WSL restart validation; container restart recovery is verified.
- [ ] Task #4 disaster-recovery rebuild still needs an approved disposable/from-scratch rebuild run; do not burn the current known-good live rootfs without explicit operator approval.
- [ ] `pleiades-gentoo-heartbeat.service` may log systemd "left-over process" warnings because it intentionally leaves the container alive after the oneshot heartbeat exits.
- [ ] Host purple suite unit files are still present on WSL under `/etc/systemd/system`, but are disabled; only the host heartbeat/timer should manage the nspawn container.
- [ ] Monitor "seen_alerts" cache growth in the sensor (clears daily, but check volume).
- [ ] Evaluate if `pleiades-host-process-sensor` should be integrated directly into the heartbeat pulse to save cycles.
- [ ] Optimize `build-pleiades-vm.sh` rsync by using `--inplace` or `--link-dest` if rebuilding frequently.

## Architectural Decisions
- **Locking**: Scripts use `flock` on `/run` to ensure single instances.
- **Bridges**: Host-to-guest bridges are managed by the heartbeat script to ensure container visibility into host `/proc`, `/sys`, and `/run`.
- **Communication**: `maia.sock` in `/run` is the primary socket for cross-boundary communication.
- **Backups**: Mandatory timestamped backups (`.bak.<timestamp>`) are created before any modification pass.
