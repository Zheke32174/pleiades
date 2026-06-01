# AGENTS.md — Pleiades Purple Team Project
# Read by: Claude Code, Codex CLI, Gemini CLI, OpenCode, and any AGENTS.md-aware harness.
# This is the single source of truth for cross-CLI context. Last updated: 2026-06-01.

## STOP — Read These First

### Hard constraints (violations cause aborts and rework)
1. **NEVER write to EFI firmware variables** — no `/sys/firmware/efi/efivars/` writes, no `SetFirmwareEnvironmentVariableA`. ESP FAT32 filesystem writes are fine. Registry writes are fine.
2. **NEVER run task #26** (disaster recovery test) without explicit operator saying "run task 26"
3. **ALWAYS backup before modifying**: `cp <file> <file>.bak.$(date +%s)` — no exceptions
4. **ALWAYS read PURPLE_STATE.md** before starting work in this repo
5. **DO NOT revert any renames** — see Naming section below

### Workspace permission workaround
Files under `root.x86_64/` are owned by root. Use:
```bash
# Fix once per session if needed:
sudo chown fixxia:fixxia /path/to/file
# Or use agent-write helper:
python3 -c "print(content)" | agent-write /path/to/root-owned-file
```

## Project: Pleiades Purple Team Container
Gentoo systemd-nspawn container (`root.x86_64/`) running a 5-agent purple team harness.
Working directory: `/workspaces/gentoo`

### Agent scripts
| Script | Agent | Role |
|---|---|---|
| `root.x86_64/scripts/SofiaX.sh` | Sophia | Overseer, EFI persistence, rehydration |
| `root.x86_64/scripts/Eris.sh` | Robin | Fake environment / honeypot |
| `root.x86_64/scripts/Beryl.sh` | Cheshire | Credential monitor |
| `root.x86_64/scripts/Ava.sh` | Hatter | Recon |
| `root.x86_64/scripts/Mariah.sh` | Little John | Watchdog |

### Canonical names (do NOT revert these)
- Binary: `sysmon-idle` (was `fake_monitor`)
- Binary: `sysmon-daemon` (was `robin_hivemind`)
- Service: `machine-runtime-monitor.service` (was `robin-omniversal.service`)
- Env var: `IS_BARE_METAL` / `ENV="bare_metal"` (was `IS_DGX` / `ENV="dgx"`)
- Detection: `systemd-detect-virt` (was `nvidia-smi && lspci`)
- Honeypot: `/etc/imtherealsparticus/` (operator name); believable prod name for attacker

## Token Efficiency (mandatory for all CLIs)
- **RTK**: prefix `git`, `gh`, `ls`, `find`, `grep`, `diff`, `docker` with `rtk` — 60-90% output reduction
- **JCodeMunch MCP**: use `get_ranked_context`/`index_folder` for code exploration instead of reading whole files
- Both are installed and should be used automatically via hooks

## Task Status
- Tasks #9–#25: DONE
- Task #26: BLOCKED pending explicit operator approval
- Pending: `install-boot-persistence.sh`, `purple-selfdestruct.sh`, evidence repo, pleiades-container git repo

## GitHub
- Main repo: `Zheke32174/pleiades`
- Dead drop: `dead_drop/signal.json`
- Evidence repo (to create): `Zheke32174/pleiades-evidence` (private)
- Container repo (to create): separate git for `root.x86_64/` nspawn rootfs

## Inter-agent bus
FIFO: `/run/purple/ouroboros_fifo` — write event strings; Sophia reads
