# Pleiades-Team Operator Runbook

**Audience:** Owner/operator only. Read-only posture by default. No implicit privilege elevation.
**Source of truth:** `PLEIADES_STATE.md` in this directory.
**Last updated:** 2026-05-29

---

## 1. Daily Health Checks

Run these in order at the start of every session. Expected completion: under 2 minutes.

### 1.1 WSL host checks (run from WSL Ubuntu, outside container)

```
# Container running?
pgrep -x systemd-nspawn
# → Should return a PID. If empty, container is down — see Section 5.

# Heartbeat status (all four bridges should show "mounted")
cat /run/pleiades-gentoo-heartbeat/status
# → Expected: bridge_proc=mounted  bridge_sys=mounted  bridge_run=mounted  bridge_mnt_c=mounted
#   last_result=ok

# Enter the container for further checks
CPID=$(pgrep -x systemd-nspawn | head -1)
sudo nsenter -t $CPID -m -u -i -n -p -- bash
```

### 1.2 Inside-container checks

```
# Any failed units?
systemctl --failed
# → Expected: 0 loaded units listed

# Current threat mode
cat /run/pleiades/atlas_mode
# → Expected: NORMAL  (PASSIVE or AGGRESSIVE indicates active threat)

# List registered capabilities
pleiadesctl capabilities
# → Should list: alcyone, taygete, electra, pleiades-rebirth, atlas, celaeno,
#   pleiades-nexus, maia, gentoo_container, brl_strat, asterope_placeholder, alien_placeholder

# BRL/strat status
pleiadesctl brl-status
# → Expected: subdir-hijack: disarmed

# Alien outbox — MUST be empty before starting any work
ls /run/pleiades/alien/outbox/
# → Expected: (empty directory)
```

---

## 2. Pleiades Swarm Broker Policy

The `pleiades-request-broker.service` is a policy-gated gate between components and privileged actions. It reads `/etc/pleiades/pleiades-swarm-policy.json`.

### 2.1 Allowed request classes (safe to pass through)

| Class | Purpose |
|---|---|
| `status` | Query current system status |
| `health` | Component health check |
| `capabilities` | List registered component capabilities |
| `evidence-list` | List collected attacker evidence |
| `brl-status` | Query BRL/strat disarm status |
| `strat-list` | List alcyoneilable strats |
| `alien-hint` | Read advisory-only alien sidecar hints |

### 2.2 Denied request classes (always blocked)

| Class | Why blocked |
|---|---|
| `shell` / `exec` | Arbitrary command execution |
| `install` | Package installation |
| `network-change` | Network configuration changes |
| `firewall-change` | Firewall rule mutations |
| `script-modify` | Modifying deployed scripts |
| `credential-access` | Reading credentials or keys |
| `lateral-movement` | Movement to other hosts |

### 2.3 How to safely add a new allowed introspection class

1. Edit `/etc/pleiades/pleiades-swarm-policy.json` — add the new class string to `allowed_request_classes` only
2. Verify the class name does not overlap with any denied class
3. Restart the broker: `systemctl restart pleiades-request-broker.service`
4. Test denial still works: write a `{"class":"shell","action":"exec"}` request to `/run/pleiades/requests/` and verify `/run/pleiades/decisions/` shows `no-action-dispatched`
5. Document the change in `PLEIADES_STATE.md` under "Recently Changed"

---

## 3. Alien Sidecar and Asterope Placeholder

### 3.1 What they are

**`alien_placeholder`** is a reserved capability slot for a future owner-approved external advisor sidecar. It is currently:
- Registered in `/run/pleiades/capabilities/alien_placeholder.cap`
- Advisory-only: the alien sidecar can write hints to `/run/pleiades/alien/outbox/`, but the broker ignores them unless the owner explicitly enables alien authority
- The outbox **must be empty** at session start — verify with `ls /run/pleiades/alien/outbox/`

**`asterope_placeholder`** is a reserved slot for future use. Do not activate. Its capability file exists but has no active implementation.

### 3.2 Session start verification (mandatory)

```
ls /run/pleiades/alien/outbox/   # must be empty
ls /run/pleiades/alien/inbox/    # advisory hints from alien (if any — read-only)
```

### 3.3 Activating alien sidecar (owner-approved only)

Activation requires explicit owner approval and is outside the scope of normal operations. The current design keeps the alien sidecar disabled and advisory-only. Do not modify alien authority in `pleiades-swarm-policy.json` without a recorded owner decision in `PLEIADES_STATE.md`.

---

## 4. Telemetry Events and Incident Response

Events are appended to `/run/pleiades/pleiades-nexus_fifo` (a regular file — do not convert to a named pipe).

**Read recent events:**
```
tail -50 /run/pleiades/pleiades-nexus_fifo
```

### 4.1 Event reference

| Event | Meaning | Operator response |
|---|---|---|
| `HOSTILE_RECON\|ip\|category\|cmd` | Attacker probed a decoy port and sent a recon command | Monitor. Taygete is handling with synthetic responses. |
| `DECOY_RESPONSE\|ip\|category` | Synthetic decoy response sent to attacker | No action. Expected companion to HOSTILE_RECON. |
| `HARVESTED\|ip\|...` | Attacker session data collected by Taygete | Review for threat intelligence. |
| `HOST_BRIDGE_OBSERVED\|...` | Host-bridge monitor ran a baseline check | Normal. |
| `HOST_NET_CHANGE\|...` | Linux host network state changed | Review. Check `ss -tlnp` on WSL host for unexpected listeners. |
| `WINDOWS_HOST_NET_CHANGE\|...` | Windows 11 host TCP or process state changed | Review snapshot in `/var/lib/pleiades-team/host-bridge/windows11/`. |
| `WINDOWS_HOST_NET_BASELINE\|...` | Windows baseline snapshot written | Normal startup event. |
| `ADAPTIVE_DEGRADED\|category` | Adaptive builder could not install a tool | Check if package manager is alcyoneilable inside container. |
| `PLEIADES_SWARM_CAPABILITY\|component\|...` | Component registered its capabilities | Normal startup event. |
| `HOST_BRIDGE_MODE\|component\|mode\|ctx` | Component reported its host-bridge visibility | Normal. `mode=host-bridge` means stronger bridges are active. |
| `CMD_PROCESSOR_STARTED` | Celaeno's command processor started | Normal startup. |

### 4.2 Atlas threat mode transitions

| Mode | Trigger | Effect |
|---|---|---|
| `NORMAL` | Default | Standard monitoring posture |
| `PASSIVE` | Moderate threat score | Increased logging, decoys remain active |
| `AGGRESSIVE` | High threat score | Full engagement; Taygete tightens rate limits |

**Current mode:** `cat /run/pleiades/atlas_mode`

**Manual reset to NORMAL:** `echo NORMAL > /run/pleiades/atlas_mode`
(Use only when threat has passed and you have reviewed HARVESTED evidence.)

---

## 5. Quick Reference

### Key paths

| Path | Purpose |
|---|---|
| `/run/pleiades/atlas_mode` | Current threat mode (NORMAL/PASSIVE/AGGRESSIVE) |
| `/run/pleiades/pleiades-nexus_fifo` | Telemetry event log (append-only regular file) |
| `/run/pleiades/attacker_ips` | Blocked IP list |
| `/run/pleiades/capabilities/` | Component capability registry |
| `/run/pleiades/requests/` | Broker request inbox |
| `/run/pleiades/decisions/` | Broker decision log |
| `/run/pleiades/alien/inbox` | Alien sidecar advisory input |
| `/run/pleiades/alien/outbox` | Alien sidecar output — must be empty |
| `/var/lib/.maia/` | Maia state, keys, owner escrow |
| `/var/lib/.maia/keys/ed25519.{priv,pub}` | Deployment Ed25519 keypair |
| `/etc/pleiades/pleiades-swarm-policy.json` | Broker policy (allowed/denied classes) |
| `/usr/local/bin/pleiadesctl` | Owner-visible pleiades-swarm control CLI |
| `/run/pleiades-gentoo-heartbeat/status` | WSL-host bridge and container status |

### Services and ports

| Service | Port | Purpose |
|---|---|---|
| `taygete-omniversal` | 2222 | SSH tarpit + hostile-recon decoy |
| `pleiades-rebirth-omniversal` | 2223 | SSH decoy logger |
| `alcyone-omniversal` | 2224 | Honeypot (Alcyone) |
| `maia` | — | Silent overseer |
| `atlas-omniversal` | — | Threat scoring engine |
| `celaeno-omniversal` | — | Command processor (via `/run/pleiades/celaeno_cmd`) |
| `electra-omniversal` | — | Electra Hood / lich |
| `pleiades-nexus-omniversal` | — | Containment controller |
| `host-bridge-monitor` | — | Read-only Linux/WSL host bridge monitor |
| `windows-host-bridge-monitor` | — | Read-only Windows 11 host bridge monitor |
| `pleiades-adaptive-builder` | — | Allowlisted defensive tool builder |
| `pleiades-request-broker` | — | Policy-gated pleiades-swarm broker |

### Emergency: stop all pleiades services without destroying the container

```
# From inside the container:
for svc in taygete-omniversal alcyone-omniversal pleiades-rebirth-omniversal \
    atlas-omniversal celaeno-omniversal electra-omniversal pleiades-nexus-omniversal \
    maia host-bridge-monitor windows-host-bridge-monitor \
    pleiades-adaptive-builder pleiades-request-broker; do
  systemctl stop "$svc" 2>/dev/null || true
done
# Container remains running. Restart individual services with: systemctl start <name>
```

---

*For implementation details see the 8 polyglot scripts in this directory. For shared agent state see `PLEIADES_STATE.md`.*
