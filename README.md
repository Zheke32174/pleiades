# Pleiades

Pleiades is a Gentoo `systemd-nspawn` container lab for running honeypot services, collecting forensic evidence, and testing defensive automation on hardware you own. The host does the minimum — launcher, heartbeat, bridge. Analysis, decoy behavior, and policy decisions run inside the container.

It is not for unauthorized deployment, stealth installation, credential theft, lateral movement, or reconnaissance on systems you don't own.

## Ontological ecology

This repository is also the canonical public contract surface for the Pleiades/MODOS Git ecology. The repository-local `MODOS_COMPONENT.yaml`, the schemas under `modos/contracts/`, and the deterministic ecology validator define how repositories declare lifecycle, authority, capabilities, provenance, and typed relations.

The exhaustive private inventory remains in Undergrowth. Public absence does not imply private nonexistence, and catalog membership never grants runtime authority. See [`modos/ecology/PRECEDENCE.md`](modos/ecology/PRECEDENCE.md) for the authority ladder and closure rules.

## Repository Map

| Repo | Status | Purpose |
|------|--------|---------|
| [`pleiades`](https://github.com/Zheke32174/pleiades) | Release-track | Host launcher, docs, agent scripts, architecture, public MODOS contracts |
| [`pleiades-container`](https://github.com/Zheke32174/pleiades-container) | Release-track | Gentoo `systemd-nspawn` container layer |
| [`pleiades-factory-stack`](https://github.com/Zheke32174/pleiades-factory-stack) | Release-track | Tooling, AI/LLM integration, cross-ISA research helpers |
| `pleiades-factory` | Private staging | Governed factory orchestration and promotion work |
| `pleiades-evidence` | Private forever | Forensic evidence archive — never public |
| `undergrowth` | Private canonical spine | Exhaustive ecology inventory, lineage, dispositions, and closure receipts |

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

## Behavior

Requests to decoy services are policy-gated before any action is taken. Destructive operations require explicit confirmation flags (`--cleanup-local`, `--confirm-owned-system`). Setup and recovery scripts that have `--dry-run` support should be run with it first — review each script before running it on a live system. No credentials are committed to this repository; the evidence archive is private.

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

## Recovery Tools

Recovery helpers live under `experimental/owner-authorized-recovery/`. They are not installed by default. Review each script and use `--dry-run` first; these are only for systems you own and administer.

## AI Assistance

Documentation and script scaffolding were partly drafted with Claude (Anthropic) and ChatGPT (OpenAI). Third-party attribution and security review remain the maintainer's responsibility — every tool used must still be credited to its original author.

---

[LICENSE](LICENSE) · [SECURITY.md](SECURITY.md) · [DISCLAIMER.md](DISCLAIMER.md) · [CONTRIBUTING.md](CONTRIBUTING.md)

Report security issues privately via [GitHub Security Advisories](https://github.com/Zheke32174/pleiades/security/advisories).
