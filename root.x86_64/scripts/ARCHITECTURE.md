# ryz-compliance: e4920ba3 doc
# Pleiades-Team Polyglot Suite Architecture

Last updated: 2026-05-30

This document maps the active eight-script suite, the services it installs, and the owner-visible state paths. The runtime is the Gentoo `systemd-nspawn` container at `/workspaces/gentoo/root.x86_64`, entered from the WSL host with `gentoo-shell`/`nsenter`.

## Runtime Model

- Host launcher: `/workspaces/gentoo/pleiades-gentoo-heartbeat.sh`
- Installed host launcher: `/usr/local/sbin/pleiades-gentoo-heartbeat.sh`
- Container rootfs: `/workspaces/gentoo/root.x86_64`
- Container entry: `systemd-nspawn --boot` under tmux session `gentoo`
- Host bridge mounts inside container: `/host/proc`, `/host/sys`, `/host/run`, `/host/mnt/c`
- Heartbeat status: `/run/pleiades-gentoo-heartbeat/status`

The heartbeat owns container recovery. It starts nspawn with explicit read-only host bridge binds, validates the bridge from inside the container namespace, and restarts the container if required bridge paths are absent.

## Script Responsibilities

| Script | Primary role | Main outputs |
|---|---|---|
| `Maia.sh` | Maia overseer, crypto, owner escrow, safe-mode monitor | `maia.service`, `/usr/local/bin/maia_crypto`, `/var/lib/.maia`, Ed25519 keys |
| `Taygete.sh` | Taygete tarpit and owner helper | `taygete-omniversal.service`, port `2222`, owner helper `127.0.0.1:18080` |
| `Alcyone.sh` | Alcyone honeypot | `alcyone-omniversal.service`, port `2224` |
| `Electra.sh` | Electra/Lich fake environment and harvester | `electra-omniversal.service`, fake environment material, `HARVESTED` telemetry |
| `Celaeno.sh` | Celaeno health and command processor | `celaeno-omniversal.service`, `/run/pleiades/celaeno_cmd` |
| `Sterope.sh` | Atlas threat scoring and mode changes | `atlas-omniversal.service`, `/run/pleiades/atlas_mode` |
| `Merope.sh` | Pleiades Rebirth SSH decoy and owner-escrow beacon | `pleiades-rebirth-omniversal.service`, port `2223` |
| `Atlas.sh` | Pleiades Nexus containment, host bridges, policy broker, adaptive builder | `pleiades-nexus-omniversal.service`, host bridge monitors, `pleiades-request-broker.service`, `pleiades-adaptive-builder.service`, `pleiadesctl` |

All eight scripts register pleiades-swarm capabilities under `/run/pleiades/capabilities` and state under `/run/pleiades/state`.

## Services

| Service | Deployed by | Purpose | Port |
|---|---|---|---|
| `maia.service` | `Maia.sh` | Silent overseer and safe-mode monitor | - |
| `taygete-omniversal.service` | `Taygete.sh` | SSH tarpit and hostile recon decoy | `2222` |
| `alcyone-omniversal.service` | `Alcyone.sh` | Alcyone honeypot | `2224` |
| `electra-omniversal.service` | `Electra.sh` | Electra/Lich fake environment | - |
| `celaeno-omniversal.service` | `Celaeno.sh` | Health/hotpatch command processor | - |
| `atlas-omniversal.service` | `Sterope.sh` | Threat scoring and mode switching | - |
| `pleiades-rebirth-omniversal.service` | `Merope.sh` | SSH decoy logger and pleiades-rebirth keeper | `2223` |
| `pleiades-nexus-omniversal.service` | `Atlas.sh` | Containment controller | - |
| `host-bridge-monitor.service` | `Atlas.sh` | Read-only Linux/WSL host bridge telemetry | - |
| `windows-host-bridge-monitor.service` | `Atlas.sh` or heartbeat recovery | Read-only Windows host telemetry | - |
| `pleiades-request-broker.service` | `Atlas.sh` | Policy-gated request broker | - |
| `pleiades-adaptive-builder.service` | `Atlas.sh` | Allowlisted defensive report/tool builder | - |

## Data Flow

1. A connection hits a decoy service such as Taygete on port `2222`.
2. The decoy returns synthetic output and appends telemetry to `/run/pleiades/pleiades-nexus_fifo`.
3. Atlas tails the event log, scores `HOSTILE_RECON`, `HARVESTED`, and related events, then updates `/run/pleiades/atlas_mode`.
4. Pleiades Nexus watches the same event log for containment triggers such as `CONTAIN_NOW`, high attacker counts, BGP hijack markers, or thermal anomalies.
5. Maia independently maintains integrity/escrow state under `/var/lib/.maia`.
6. The request broker accepts only policy-allowed introspection classes and denies shell, exec, install, network, firewall, script modification, credential, and lateral-movement requests.

## Key Paths

| Path | Owner | Meaning |
|---|---|---|
| `/run/pleiades/pleiades-nexus_fifo` | All components append; Pleiades Nexus/Atlas consume | Append-only regular telemetry file, not a FIFO |
| `/var/lib/pleiades/archive` | Host heartbeat via container namespace | Rotated telemetry archives that survive container restarts |
| `/run/pleiades/atlas_mode` | Atlas | Current threat mode: `NORMAL`, `PASSIVE`, or `AGGRESSIVE` |
| `/run/pleiades/attacker_ips` | Decoys/Pleiades Nexus | Observed or blocked attacker IPs |
| `/run/pleiades/capabilities/*.cap` | All scripts, restored by broker startup | Component capability registry |
| `/run/pleiades/state/*.state` | All scripts, restored by broker startup | Component state registry |
| `/run/pleiades/requests` | Components/operator | Broker request inbox |
| `/run/pleiades/decisions` | Request broker | Policy decisions |
| `/run/pleiades/actions` | Request broker | Only for allowed, dispatched actions |
| `/run/pleiades/results` | Request broker | Request results |
| `/run/pleiades/alien/inbox` | Owner/sidecar dock | Advisory input area |
| `/run/pleiades/alien/outbox` | Sidecar dock | Must remain empty unless owner enables sidecar workflow |
| `/etc/pleiades/pleiades-swarm-policy.json` | Atlas/broker | Deny-by-default broker policy |
| `/var/lib/.maia/keys/ed25519.priv` | Maia | Deployment private key, mode `0600` |
| `/var/lib/.maia/keys/ed25519.pub` | Maia | Deployment public key |
| `/var/lib/.maia/drop_urls` | Maia owner-escrow probe | Paste/drop URL source list for signed owner signals |
| `/var/lib/pleiades-team/host-bridge/windows11` | Windows bridge monitor | Windows process/TCP snapshots |

## Owner-Escrow Signals

Maia uses `/usr/local/bin/maia_crypto` for Ed25519 operations. Signed drop messages have this shape:

```json
{"message":"BASE64_PAYLOAD","sig":"ED25519_SIGNATURE_HEX","ts":1760000000}
```

The signature is over the base64 message string. `maia_crypto verify-drop` verifies the timestamp, signature, and base64 payload. `maia_crypto probe` checks mDNS, DNS TXT, paste URLs from `/var/lib/.maia/drop_urls`, then Tor drops. USB scans look for `.pleiades_signal.json` on removable or explicitly configured scan mounts.

## Alien And Asterope Placeholders

`alien_placeholder` and `asterope_placeholder` are registered for owner-visible future expansion, but they have no authority by default. The alien sidecar can only provide hints unless the owner explicitly changes policy. The broker remains deny-by-default and does not dispatch alien-originated actions in the current design.

## Validation

The regression entrypoint is:

```bash
bash /workspaces/gentoo/root.x86_64/scripts/pleiades-regression.sh
```

Current expected result is zero failures and zero skips. The harness covers script syntax, systemd units, decoy ports, Taygete concurrency, hostile recon telemetry, broker policy, host bridges, Windows telemetry, Maia crypto, owner-escrow signed probe, USB escrow scan, telemetry archive persistence, and alien sidecar non-authority.
