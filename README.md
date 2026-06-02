# Pleiades

Pleiades is a defensive container lab for host-protection research, honeypot telemetry, and forensic evidence collection on hardware you own and administer.

The design keeps the host footprint small. The host runs a launcher, a heartbeat service, and a host-to-container bridge. The active analysis, decoy behavior, policy decisions, and forensic processing run inside a Gentoo `systemd-nspawn` container.

## What it's for

- Local security labs on hardware you own or explicitly administer
- Honeypot and decoy service research with local telemetry
- Forensic evidence collection and incident response testing
- Container rebuild and recovery drills
- Policy-gated automation research

**Not intended for:** unauthorized deployment, stealth installation, credential theft, lateral movement, anti-forensics, or reconnaissance on systems you don't own.

## Repository Map

| Repo | Status | Purpose |
|------|--------|---------|
| [`pleiades`](https://github.com/Zheke32174/pleiades) | Release-track | Host launcher, docs, agent scripts, architecture |
| [`pleiades-container`](https://github.com/Zheke32174/pleiades-container) | Release-track | Gentoo `systemd-nspawn` container layer |
| [`pleiades-factory-stack`](https://github.com/Zheke32174/pleiades-factory-stack) | Release-track | Tooling, AI/LLM integration, cross-ISA research helpers |
| `pleiades-factory` | Private staging | Future factory orchestration work; not public-ready yet |
| `pleiades-evidence` | Private forever | Forensic evidence archive — never public |

## Architecture

```
Host (minimal footprint)
  ├─ launcher + heartbeat
  ├─ host-to-container bridge and telemetry relay
  └─ recovery fallback (stop token)

Gentoo systemd-nspawn container
  ├─ Alcyone   — host capability inventory
  ├─ Atlas     — recovery coordinator
  ├─ Electra   — decoy environment / honeypot router
  ├─ Maia      — container restore coordinator
  ├─ Merope    — credential exposure detector
  ├─ Taygete   — health monitor and supervised restart
  ├─ Celaeno   — policy-gated request broker
  ├─ Asterope  — telemetry aggregator
  └─ Sterope   — watchdog and integrity verifier
```

## How It Works

- Requests to decoy services are policy-gated before any action is taken
- Destructive operations require explicit flags (`--cleanup-local`, `--confirm-owned-system`)
- Risky setup and recovery scripts should be run with `--dry-run` where supported — review each script before use
- No credentials or secrets are committed to this repository
- The evidence archive remains private

## Quick Start

```bash
# 1. Authenticate GitHub CLI (required for recovery features)
gh auth login

# 2. Run operator setup (writes /etc/pleiades/operator.conf)
sudo bash root.x86_64/scripts/pleiades-setup.sh

# 3. Verify all scripts are syntactically valid
bash -n root.x86_64/scripts/*.sh

# 4. Dry-run the regression suite before starting anything
bash root.x86_64/scripts/pleiades-regression.sh --dry-run
```

For container setup on a new machine, see [`pleiades-container`](https://github.com/Zheke32174/pleiades-container).

## Recovery Tools (Advanced)

Recovery helpers live under `experimental/owner-authorized-recovery/`. They are not installed by default. Review each script and use `--dry-run` first. These tools are only for systems you own and explicitly administer.

## AI Assistance Disclosure

Parts of this project's documentation, planning notes, cleanup checklists, and script scaffolding were developed with assistance from AI tools, including Claude by Anthropic and ChatGPT by OpenAI.

Human maintainers are responsible for reviewing, testing, security boundaries, attribution, and final repository contents. AI assistance does not replace upstream attribution — every third-party tool must still be credited to its original developer or organization.

## License

See [LICENSE](LICENSE).

## Security

See [SECURITY.md](SECURITY.md). Report issues via [GitHub Security Advisories](https://github.com/Zheke32174/pleiades/security/advisories).

## Disclaimer

See [DISCLAIMER.md](DISCLAIMER.md).
