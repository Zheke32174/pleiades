# Pleiades

Pleiades is an owner-authorized defensive container lab for host-protection research, decoy-service telemetry, and forensic evidence collection.

The project is designed around a minimal host footprint. The host provides a small launcher, heartbeat, bridge, and recovery escape hatch. Active analysis, decoy behavior, policy decisions, and forensic processing live inside a Gentoo `systemd-nspawn` container or nested sandbox.

## Intended Use

Pleiades is intended for:

- local security labs on hardware you own or administer
- defensive telemetry collection with owner awareness
- decoy service testing and honeypot research
- forensic evidence handling and incident response support
- policy-gated automation research
- owner-authorized recovery testing

Pleiades is **not** intended for unauthorized deployment, stealth installation, credential theft, lateral movement, anti-forensic use, or third-party reconnaissance.

## Scope and Safety

| Allowed | Not allowed |
|---------|-------------|
| Local lab testing on owned hardware | Deployment without explicit authorization |
| Owner-authorized host monitoring | Unauthorized persistence |
| Decoy service telemetry | Credential theft |
| Forensic evidence capture | Lateral movement |
| Container recovery testing | Unauthorized reconnaissance |
| Defensive automation research | Log wiping to conceal unauthorized activity |

## Repository Map

| Repo | Purpose |
|------|---------|
| [`pleiades`](https://github.com/Zheke32174/pleiades) | Host launcher, docs, agent scripts, architecture |
| [`pleiades-container`](https://github.com/Zheke32174/pleiades-container) | Gentoo `systemd-nspawn` container layer |
| [`pleiades-factory-stack`](https://github.com/Zheke32174/pleiades-factory-stack) | Tooling, AI/LLM integration, cross-ISA research helpers |
| `pleiades-evidence` | Private forensic evidence archive — never public |

## Architecture

```
Host (minimal footprint)
  ├─ owner-authorized launcher + heartbeat
  ├─ host-to-container bridge and telemetry relay
  └─ recovery escape hatch (owner-signed stop token)

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

## Safety Defaults

- Deny-by-default request policy
- Explicit owner approval required for write/mutate operations
- Destructive operations require explicit flags (`--cleanup-local`, `--confirm-owned-system`)
- All scripts support `--dry-run`
- No committed secrets or credentials
- Evidence archive remains private

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

## Owner-Authorized Recovery (Advanced)

Recovery helpers are experimental and kept under `experimental/owner-authorized-recovery/`. They are **not installed by default**. Review each script and use `--dry-run` first. These tools are only for systems the operator owns and explicitly administers.

## License

See [LICENSE](LICENSE).

## Security

See [SECURITY.md](SECURITY.md). Report security issues via [GitHub Security Advisories](https://github.com/Zheke32174/pleiades/security/advisories).

## Disclaimer

See [DISCLAIMER.md](DISCLAIMER.md).
