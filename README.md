# Pleiades

Pleiades is an owner-authorized defensive container lab for host-protection research, decoy-service telemetry, and forensic evidence collection.

The project is designed around a minimal host footprint. The host provides a small launcher, heartbeat, bridge, and recovery escape hatch. Active analysis, decoy behavior, policy decisions, and forensic processing live inside a Gentoo `systemd-nspawn` container or nested sandbox.


## Repository Map

| Repo | Purpose |
|------|---------|
| [`pleiades`](https://github.com/Zheke32174/pleiades) | Host launcher, docs, agent scripts, architecture |
| [`pleiades-container`](https://github.com/Zheke32174/pleiades-container) | Gentoo `systemd-nspawn` container layer |
| [`pleiades-factory-stack`](https://github.com/Zheke32174/pleiades-factory-stack) | Tooling, AI/LLM integration, cross-ISA research helpers |

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
