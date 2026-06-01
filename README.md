# SofiaX Purple Team Polyglot Suite

**Ouroboros Mutual-Persistence Security Framework**

A highly resilient, multi-vector "Purple Team" persistence and auditing suite designed to survive extreme environments, active Tier 1 threat actor interference, and total filesystem compromise. The suite operates on a **Mutual Persistence (Ouroboros) model**: seven specialized modules autonomously monitor, defend, and resurrect each other and the master overseer.

---

## Architecture Overview

```
                     ┌─────────────────────────────────────┐
                     │         SofiaX (The Overseer)        │
                     │         core/SofiaX.sh              │
                     │   Deploys, patches, self-obfuscates │
                     └─────────────────────────────────────┘
                                     │
                ┌────────────────────┼────────────────────┐
                │                    │                    │
          ┌─────┴─────┐    ┌────────┴────────┐    ┌──────┴──────┐
          │ Modules   │    │ BIOS Rehydrator  │    │ Daemon      │
          │ (7 .sh)   │    │ container/       │    │ sophia_     │
          │           │    │ rehydrate.sh     │    │ daemon.sh   │
          └─────┬─────┘    └─────────────────┘    └─────────────┘
                │
    ┌──────┬──────┬──────┬──────┬──────┬──────┬──────┐
    │ Ava  │Beryl │Mariah│ Zara │ Vera │Artemis│ Eris │
    └──────┴──────┴──────┴──────┴──────┴──────┴──────┘
```

### Component Descriptions

| Component | File | Role | Internal ID |
|-----------|------|------|-------------|
| **SofiaX** | `core/SofiaX.sh` | Master overseer: deploys, patches modules, manages integrity, self-obfuscates on completion | — |
| **Sophia Daemon** | `core/sophia_daemon.sh` | Unix socket listener that dispatches resurrection/implosion commands from module hooks | — |
| **Ava** | `modules/Ava.sh` | Environment auditor & Hatter deployment — detects WSL/DGX/bare/VPS, configures resource limits | `HATTER_ID` |
| **Beryl** | `modules/Beryl.sh` | Cheshire Cat — BGP route monitoring, Batman/Robin worker mesh, network-level stealth | `CHESHIRE_ID` |
| **Artemis** | `modules/Artemis.sh` | Zod — thermal side-channel detection, brute-force defense throttling | `ZOD_ID` |
| **Eris** | `modules/Eris.sh` | Robin — chaos agent / lich process, adversarial resource exhaustion testing, anti-cryostasis | `ROBIN_ID` |
| **Mariah** | `modules/Mariah.sh` | Little John — central orchestrator/deployer, runs the omniversal installer matrix for all modules | `LITTLEJOHN_ID` |
| **Vera** | `modules/Vera.sh` | Resurrection — mutual-watchdog process, restores any killed/dead module from pristine copies | `RESURRECTION_ID` |
| **Zara** | `modules/Zara.sh` | Ouroboros — the imploder / last-resort self-destruct, ensures zero forensic trace on total compromise | `OUROBOROS_ID` |
| **Rehydrate** | `container/rehydrate.sh` | EFI simulation — polls dead-drop for `RESURRECT` signal, triggers full suite recovery | — |

### Sequencing / Load Order

When SofiaX deploys, modules are launched in this specific order:

1. **Ava** (Environment Detection) → 2. **Vera** (Resurrection Watchdog) → 3. **Eris** (Lich Process) →
4. **Zara** (Ouroboros Imploder) → 5. **Beryl** (Cheshire BGP Monitor) → 6. **Artemis** (Zod Thermal) → 7. **Mariah** (Little John Orchestrator)

---

## Defenses & Resilience Model

This suite has been stress-tested against extreme "Black-Level" attacks:

- **Verified Auditing (Anti-Lobotomy):** Cross-references `sha256sum` vs `openssl dgst -sha256` to detect OS binary hijacking. If hashes diverge, a hash mismatch alert is raised.

- **State-Aware Liveness Probing (Anti-Cryostasis):** Modules check process state (not just PID existence). If daemon is `SIGSTOP`-frozen (State `T`), it is automatically resurrected.

- **Reality Anchors (Anti-Mirror):** Holds open file descriptors to canary files. If the path disappears but the FD remains accessible, a mount-namespace hijack (`mount --bind` masking) is detected.

- **Anti-Thundering Herd Resurrection:** Randomized jitter (0-30s) on resurrection attempts prevents CPU spikes and duplicate deployments.

- **Multi-Channel EFI Rehydration (Cold Boot Recovery):** Even after total filesystem wipe, a rehydrator polls a remote `DEAD_DROP_URL`, local `USB_DEAD_DROP`, and proxy dead-drop for a `RESURRECT` signal to rebuild the entire suite.

---

## Placeholder Token System

SofiaX uses **compile-time placeholders** that are patched at runtime. The source files ship with dummy values; `generate_real_values()` replaces them with cryptographically random tokens.

### DEAD_DROP_URL

The dead-drop URL is a local file path that serves as the resurrection signal channel:

```
# In source:  file:///var/lib/.sophia/dead_drop_86e1fde67780f9b9.txt
# At runtime: file:///var/lib/.sophia/dead_drop_<16-hex-random>.txt
```

The URL contains a hex suffix (8 random bytes via `openssl rand -hex 8`). The file contains the string `RESURRECT` and is polled by the BIOS rehydrator.

### Token Placeholders

| Placeholder | Source Default | Runtime Value |
|-------------|---------------|---------------|
| `DEAD_DROP_URL` | `file:///var/lib/.sophia/dead_drop_86e1fde67780f9b9.txt` | Randomized per deployment |
| `HTTP_TOKEN` | `aa0e670f832a23632ab9f5d554535d9d` | 16 random hex bytes |
| `CONTROL_TOKEN` | `c6160d0a7edde42d253881cf3aea2904` | 16 random hex bytes |
| `MAX_OPEN_FILES` | `4096` | Tuned per environment |
| `MEMORY_LIMIT` | `3764M` | Tuned per environment |
| `CPU_QUOTA` | `400%` | Tuned per environment |
| `THREAT_THRESHOLD` | `500` | Tuned per environment |
| `MAX_BRUTE_CONCURRENCY` | `3` | Tuned per environment |
| `THRALL_MAX_FLOODS` | `3` | Tuned per environment |
| `THRALL_INTERVAL` | `3` | Tuned per environment |
| `BEACON_INTERVAL` | `7200` | Tuned per environment |

Module-level placeholders use the suffix `_PLACEHOLDER` (e.g., `DEAD_DROP_URL_PLACEHOLDER`) and are patched individually by `patch_script()`.

### Self-Patching Flow

1. `detect_environment()` identifies WSL / DGX / VPS / bare-metal
2. `generate_real_values()` creates random tokens and tunes limits
3. SofiaX makes a temporary copy of itself (`TEMP_SELF`)
4. `patch_placeholder()` runs `sed` replacement for every token
5. The patched copy overwrites the original (`SELF_PATH`)
6. `patch_script()` patches each module's placeholders
7. SofiaX self-obfuscates by zeroing its own file and setting mode `000`

---

## Repository Structure

```
.
├── core/
│   ├── SofiaX.sh              # Master overseer (self-patching, deployment, rehydration)
│   └── sophia_daemon.sh       # Unix socket daemon (dispatches module commands)
├── modules/
│   ├── Ava.sh                 # Hatter — environment detection & config
│   ├── Artemis.sh             # Zod — thermal side-channel & brute-force defense
│   ├── Beryl.sh               # Cheshire — BGP monitoring & Batman/Robin mesh
│   ├── Eris.sh                # Robin — chaos agent / lich process
│   ├── Mariah.sh              # Little John — central orchestrator
│   ├── Vera.sh                # Resurrection — mutual-watchdog
│   └── Zara.sh                # Ouroboros — imploder / self-destruct
├── container/
│   └── rehydrate.sh           # EFI simulation — dead-drop polling
├── docs/
│   └── README.md              # Original short README
├── src/                       # Reserved for supplementary source (currently empty)
├── .gitignore
├── LICENSE                    # MIT License
└── README.md                  # This file
```

---

## Requirements & Dependencies

### Runtime

| Tool | Purpose | Auto-Installed? |
|------|---------|-----------------|
| `bash` (>=4) | Shell runtime | System-provided |
| `nc` (netcat) | Unix socket communication | Yes (via `install_tools()`) |
| `curl` | HTTP requests to dead-drop, Homebrew bootstrap | Yes |
| `git` | Version checks, module deployment | Yes |
| `openssl` | Cryptographic hashes, random token generation | Yes |
| `parted` | Partition management | Yes |
| `socat` | Network relay | Yes |
| `bc` | Arithmetic (load comparisons) | Yes |
| `lm-sensors` | Thermal monitoring | Yes |

### Build Toolchains (for polyglot modules)

Some modules embed Go, Rust, or Bun source that compiles on-the-fly:

- **Go** (`golang`) — for compiled binary components
- **Rust** (`rustc`) — for performance-critical modules
- **Bun** — for JavaScript/TypeScript runtime components

### Supported Distributions

Gentoo (`emerge`), Debian/Ubuntu (`apt-get`), Alpine (`apk`), RHEL/Fedora (`dnf`/`yum`), Arch Linux (`pacman`), FreeBSD (`pkg`), macOS (`brew`).

---

## Deployment

```bash
# Production deployment (requires root):
sudo bash core/SofiaX.sh

# Dry-run / development mode (skips self-obfuscation):
TEST_MODE=1 bash core/SofiaX.sh

# Rehydration only (just start the daemon):
bash core/SofiaX.sh --rehydrate-only
```

### What Happens

1. Environment detection (WSL / DGX / VPS / bare-metal)
2. Missing tool installation (`install_tools()`)
3. Runtime placeholder generation and self-patching
4. Module discovery (by internal IDs embedded in each `.sh`)
5. Pristine backups stored (gzip+base64 in `$SOPHIA_DIR/originals/`)
6. Module patching (placeholders → runtime values + Sophia hooks)
7. Sequential module launch
8. BIOS rehydrator injection (into EFI system partition)
9. Sophia daemon start (systemd service or `screen` on WSL)
10. Self-obfuscation (wipes own file content)

---

## Configuration

All configuration happens at runtime via `generate_real_values()`. The key configurable paths are:

| Variable | Default | Description |
|----------|---------|-------------|
| `SOPHIA_DIR` | `/var/lib/.sophia` | Base state directory |
| `LOGS_DIR` | `$SOPHIA_DIR/logs` | Event logs |
| `WORK_DIR` | `$SOPHIA_DIR/work` | Temporary work area |
| `SCRIPT_DIR` | `/usr/local/sbin` | Daemon and omniversal installer location |
| `DEAD_DROP_URL` | (randomized) | Resurrection signal file path |

To override at deployment time, set environment variables before running SofiaX:

```bash
SOPHIA_DIR=/custom/path TEST_MODE=1 bash core/SofiaX.sh
```

---

## Development

### Path Conventions

All shell scripts use absolute paths for deployment targets (`/usr/local/sbin/`, `/var/lib/.sophia/`, `/etc/systemd/system/`). The `SCRIPT_DIR` and `SOPHIA_DIR` variables make these configurable. No hardcoded development paths (e.g., `/workspaces/`) remain in the codebase.

### Adding a New Module

1. Create `modules/YourModule.sh` with shebang `#!/usr/bin/env bash`
2. Embed an internal identifier: `YOUR_ID="some-unique-string"`
3. Add it to `SCRIPT_ID_MAP` in `core/SofiaX.sh`
4. Add it to `load_order` in the `main()` function

### Testing

```bash
# Quick validation — run SofiaX in test mode
TEST_MODE=1 bash core/SofiaX.sh

# Check all .sh scripts for syntax errors
for f in core/*.sh modules/*.sh container/*.sh; do bash -n "$f" || echo "FAIL: $f"; done
```

---

## Companion Container

This suite deploys into a **Gentoo systemd-nspawn container** at
[Zheke32174/pleiades-container](https://github.com/Zheke32174/pleiades-container).

The container provides:
- Isolated execution environment for the defense stack
- Auto-start at boot via systemd units (bare metal / VM)
- Purple bridge for host-side event relay
- Self-destruct and re-deployment from GitHub

```bash
# Clone the companion container
git clone https://github.com/Zheke32174/pleiades-container.git

# Start the container
cd pleiades-container
sudo systemd-nspawn -D root.x86_64 -b --network-veth -M gentoo
```

See [pleiades-container](https://github.com/Zheke32174/pleiades-container) for full setup.

## Dead Drop — GitHub as Rehydration Source

The suite rehydrates from its own GitHub repo, eliminating the need for a unique external URL.

`sophia_crypto probe` fetches
[`dead_drop/signal.json`](dead_drop/signal.json) via the raw GitHub URL and verifies the
Ed25519 signature. If valid and the message is a recognized command, the system acts on it.

```
Default probe URL:
  https://raw.githubusercontent.com/Zheke32174/pleiades/main/dead_drop/signal.json
```

| Signal (decoded) | Action |
|------------------|--------|
| `RESURRECT` | `purple-redeploy.sh` — clone from GitHub, rebuild, re-deploy |
| `PURGE\|AUTHORIZED_PURGE` | `purge-self.sh` — signal-gated self-destruct |

The signal file is signed with the deployment's Ed25519 key. To sign a new signal,
see [`dead_drop/README.md`](dead_drop/README.md).

---

## License

MIT — see [LICENSE](LICENSE).

---

## Security Notice

This is **offensive security tooling** designed for authorized purple-team exercises. The self-obfuscation, EFI rehydration, and persistence mechanisms may be flagged by antivirus/EDR. Use only on systems you own or have explicit written authorization to test.
