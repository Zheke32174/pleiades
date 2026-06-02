# Pleiades Architecture Notes

Pleiades is a defensive container research project for decoy services, telemetry collection, policy-gated automation, and owner-authorized recovery.

The suite runs primarily inside a Gentoo `systemd-nspawn` container. The host-side footprint is minimal: a launcher, heartbeat, bridge, and recovery escape hatch. Active defensive logic runs inside the container.

## Architecture

```
Host (minimal footprint)
  ├─ owner-authorized launcher and heartbeat service
  ├─ host-to-container bridge (telemetry relay)
  └─ recovery escape hatch (owner-signed stop token via pleiades-crypto)

Gentoo systemd-nspawn container
  ├─ Alcyone   — host capability inventory
  ├─ Atlas     — recovery coordinator and rebuild orchestrator
  ├─ Electra   — decoy environment and honeypot router
  ├─ Maia      — container restore coordinator
  ├─ Merope    — credential exposure detector
  ├─ Taygete   — health monitor and supervised restart
  ├─ Celaeno   — policy-gated request broker
  ├─ Asterope  — telemetry aggregator and BSD compatibility layer
  └─ Sterope   — watchdog and integrity verifier
```

## Integrity Checking

Agents cross-reference OS hashing tools (`sha256sum` vs `openssl dgst -sha256`) to detect binary substitution on the host. This is a defensive integrity check, not an offensive capability.

Process liveness checks examine process state (not just PID existence) to detect frozen daemons. Supervised restart uses randomized jitter to prevent restart storms.

Mount-namespace consistency checks hold open file descriptors to canary files, logging anomalies for forensic review if the path disappears while the FD remains accessible.

## Owner-Authorized Recovery

Container recovery is coordinated via:
1. A signed stop token (allows owner to halt recovery without root)
2. An optional owner recovery marker in the operator's private GitHub repo
3. Optional ESP FAT32 metadata storage (filesystem path only — no firmware variable writes)

Recovery is never automatic. It requires the operator's GitHub credentials and an explicit recovery signal written by the operator. See `experimental/owner-authorized-recovery/` for the optional helpers.

## Repository Structure

```
root.x86_64/scripts/              — container agent scripts
experimental/owner-authorized-recovery/  — optional recovery helpers (not installed by default)
.github/workflows/ci.yml          — CI: syntax, wording, secret scan, hygiene, provenance
CREDITS.md                        — third-party attribution
THIRD_PARTY_NOTICES.md            — vendored/adapted code notices
```

## Deployment

```bash
# New machine setup
sudo bash pleiades-container/bootstrap-container.sh
gh auth login
sudo bash root.x86_64/scripts/pleiades-setup.sh
bash root.x86_64/scripts/pleiades-regression.sh --dry-run
```

## Note on Embedded Compiled Code

Several agent scripts embed Go, Rust, or Bun source that compiles at runtime inside the container. This code was generated as part of the Pleiades project. Any scaffold that closely follows an upstream project structure is documented in `CREDITS.md`.
