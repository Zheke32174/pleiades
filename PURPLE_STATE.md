# Purple Team Project - State Tracking

## Current Status
- **Date**: 2026-05-29
- **Environment**: WSL2 / Gentoo nspawn container
- **Heartbeat**: Stable (v0.2.1: Extended timeouts, tmux watchdog, pgrep fix).
- **Sensor**: Active (v0.2.0: jq-based JSON, seen-cache de-duplication, log rotation).
- **VM Build**: Improved (v0.1.1: Cleanup trap, better rsync exclusions).

## Recent Changes
- **Git Initialization**: Created local git repository plan for project name `pleiades`. `.gitignore` now excludes raw images, stage3 archives, backups, and the live Gentoo rootfs by default while explicitly allowing the active script suite under `root.x86_64/scripts/`.
- **Backup Harness**: Added `/workspaces/gentoo/purple-backup.sh` and `/workspaces/gentoo/test-purple-backups.sh`; `install-purple-gentoo-heartbeat.sh` now uses the shared helper when present. Backups get unique agent/PID suffixes and a `.purple-backups/manifest.jsonl` entry so concurrent Codex/Claude/Gemini/Octopus edits do not overwrite each other.
- **Codex Task Master Hook**: Codex-owned `~/.codex/hooks.json` SessionStart hook now calls `/workspaces/gentoo/tm-context.sh` with a 5s timeout. The bridge reads `.taskmaster/tasks/tasks.json` directly with `jq` to avoid blocking on the Task Master CLI during session startup.
- **Stabilization**: Fixed container PID detection to avoid `nsenter` failures caused by `pgrep` matching the script itself.
- **Sensor Deployment**: Installed and activated `purple-host-process-sensor` as a systemd timer (every 30s).
- **Logging**: Implemented self-managed log rotation for `/var/log/purple-gentoo-heartbeat.log` and `/run/purple-host-capsule/process-alerts.jsonl`.
- **Build Improvements**: Added an EXIT trap to `build-purple-vm.sh` to ensure `/tmp/purple-qemu-mount` is always unmounted on failure.
- **Consistency**: Synchronized `/usr/local/sbin` with workspace files.

## Known Issues / Tasks
- [ ] Monitor "seen_alerts" cache growth in the sensor (clears daily, but check volume).
- [ ] Evaluate if `purple-host-process-sensor` should be integrated directly into the heartbeat pulse to save cycles.
- [ ] Optimize `build-purple-vm.sh` rsync by using `--inplace` or `--link-dest` if rebuilding frequently.

## Architectural Decisions
- **Locking**: Scripts use `flock` on `/run` to ensure single instances.
- **Bridges**: Host-to-guest bridges are managed by the heartbeat script to ensure container visibility into host `/proc`, `/sys`, and `/run`.
- **Communication**: `sophia.sock` in `/run` is the primary socket for cross-boundary communication.
- **Backups**: Mandatory timestamped backups (`.bak.<timestamp>`) are created before any modification pass.
