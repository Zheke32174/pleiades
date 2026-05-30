# Purple-Team Operator Runbook

**Audience:** Owner/operator only. Read-only posture by default. No implicit privilege elevation.
**Source of truth:** `PURPLE_STATE.md` in this directory.
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
cat /run/purple-gentoo-heartbeat/status
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
cat /run/purple/zod_mode
# → Expected: NORMAL  (PASSIVE or AGGRESSIVE indicates active threat)

# List registered capabilities
purplectl capabilities
# → Should list: hatter, cheshire, robin, resurrection, zod, little_john,
#   ouroboros, sophia, gentoo_container, brl_strat, quantum_placeholder, alien_placeholder

# BRL/strat status
purplectl brl-status
# → Expected: subdir-hijack: disarmed

# Alien outbox — MUST be empty before starting any work
ls /run/purple/alien/outbox/
# → Expected: (empty directory)
```

---

## 2. Hivemind Broker Policy

The `purple-request-broker.service` is a policy-gated gate between components and privileged actions. It reads `/etc/purple/hivemind-policy.json`.

### 2.1 Allowed request classes (safe to pass through)

| Class | Purpose |
|---|---|
| `status` | Query current system status |
| `health` | Component health check |
| `capabilities` | List registered component capabilities |
| `evidence-list` | List collected attacker evidence |
| `brl-status` | Query BRL/strat disarm status |
| `strat-list` | List available strats |
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

1. Edit `/etc/purple/hivemind-policy.json` — add the new class string to `allowed_request_classes` only
2. Verify the class name does not overlap with any denied class
3. Restart the broker: `systemctl restart purple-request-broker.service`
4. Test denial still works: write a `{"class":"shell","action":"exec"}` request to `/run/purple/requests/` and verify `/run/purple/decisions/` shows `no-action-dispatched`
5. Document the change in `PURPLE_STATE.md` under "Recently Changed"

---

## 3. Alien Sidecar and Quantum Placeholder

### 3.1 What they are

**`alien_placeholder`** is a reserved capability slot for a future owner-approved external advisor sidecar. It is currently:
- Registered in `/run/purple/capabilities/alien_placeholder.cap`
- Advisory-only: the alien sidecar can write hints to `/run/purple/alien/outbox/`, but the broker ignores them unless the owner explicitly enables alien authority
- The outbox **must be empty** at session start — verify with `ls /run/purple/alien/outbox/`

**`quantum_placeholder`** is a reserved slot for future use. Do not activate. Its capability file exists but has no active implementation.

### 3.2 Session start verification (mandatory)

```
ls /run/purple/alien/outbox/   # must be empty
ls /run/purple/alien/inbox/    # advisory hints from alien (if any — read-only)
```

### 3.3 Activating alien sidecar (owner-approved only)

Activation requires explicit owner approval and is outside the scope of normal operations. The current design keeps the alien sidecar disabled and advisory-only. Do not modify alien authority in `hivemind-policy.json` without a recorded owner decision in `PURPLE_STATE.md`.

---

## 4. Telemetry Events and Incident Response

Events are appended to `/run/purple/ouroboros_fifo` (a regular file — do not convert to a named pipe).

**Read recent events:**
```
tail -50 /run/purple/ouroboros_fifo
```

### 4.1 Event reference

| Event | Meaning | Operator response |
|---|---|---|
| `HOSTILE_RECON\|ip\|category\|cmd` | Attacker probed a decoy port and sent a recon command | Monitor. Cheshire is handling with synthetic responses. |
| `DECOY_RESPONSE\|ip\|category` | Synthetic decoy response sent to attacker | No action. Expected companion to HOSTILE_RECON. |
| `HARVESTED\|ip\|...` | Attacker session data collected by Cheshire | Review for threat intelligence. |
| `HOST_BRIDGE_OBSERVED\|...` | Host-bridge monitor ran a baseline check | Normal. |
| `HOST_NET_CHANGE\|...` | Linux host network state changed | Review. Check `ss -tlnp` on WSL host for unexpected listeners. |
| `WINDOWS_HOST_NET_CHANGE\|...` | Windows 11 host TCP or process state changed | Review snapshot in `/var/lib/purple-team/host-bridge/windows11/`. |
| `WINDOWS_HOST_NET_BASELINE\|...` | Windows baseline snapshot written | Normal startup event. |
| `ADAPTIVE_DEGRADED\|category` | Adaptive builder could not install a tool | Check if package manager is available inside container. |
| `HIVEMIND_CAPABILITY\|component\|...` | Component registered its capabilities | Normal startup event. |
| `HOST_BRIDGE_MODE\|component\|mode\|ctx` | Component reported its host-bridge visibility | Normal. `mode=host-bridge` means stronger bridges are active. |
| `CMD_PROCESSOR_STARTED` | Little John's command processor started | Normal startup. |

### 4.2 Zod threat mode transitions

| Mode | Trigger | Effect |
|---|---|---|
| `NORMAL` | Default | Standard monitoring posture |
| `PASSIVE` | Moderate threat score | Increased logging, decoys remain active |
| `AGGRESSIVE` | High threat score | Full engagement; Cheshire tightens rate limits |

**Current mode:** `cat /run/purple/zod_mode`

**Manual reset to NORMAL:** `echo NORMAL > /run/purple/zod_mode`
(Use only when threat has passed and you have reviewed HARVESTED evidence.)

---

## 5. Quick Reference

### Key paths

| Path | Purpose |
|---|---|
| `/run/purple/zod_mode` | Current threat mode (NORMAL/PASSIVE/AGGRESSIVE) |
| `/run/purple/ouroboros_fifo` | Telemetry event log (append-only regular file) |
| `/run/purple/attacker_ips` | Blocked IP list |
| `/run/purple/capabilities/` | Component capability registry |
| `/run/purple/requests/` | Broker request inbox |
| `/run/purple/decisions/` | Broker decision log |
| `/run/purple/alien/inbox` | Alien sidecar advisory input |
| `/run/purple/alien/outbox` | Alien sidecar output — must be empty |
| `/var/lib/.sophia/` | Sophia state, keys, owner escrow |
| `/var/lib/.sophia/keys/ed25519.{priv,pub}` | Deployment Ed25519 keypair |
| `/etc/purple/hivemind-policy.json` | Broker policy (allowed/denied classes) |
| `/usr/local/bin/purplectl` | Owner-visible hivemind control CLI |
| `/run/purple-gentoo-heartbeat/status` | WSL-host bridge and container status |

### Services and ports

| Service | Port | Purpose |
|---|---|---|
| `cheshire-omniversal` | 2222 | SSH tarpit + hostile-recon decoy |
| `resurrection-omniversal` | 2223 | SSH decoy logger |
| `hatter-omniversal` | 2224 | Honeypot (Hatter) |
| `sophia` | — | Silent overseer |
| `zod-omniversal` | — | Threat scoring engine |
| `little-john-omniversal` | — | Command processor (via `/run/purple/little_john_cmd`) |
| `robin-omniversal` | — | Robin Hood / lich |
| `ouroboros-omniversal` | — | Containment controller |
| `host-bridge-monitor` | — | Read-only Linux/WSL host bridge monitor |
| `windows-host-bridge-monitor` | — | Read-only Windows 11 host bridge monitor |
| `purple-adaptive-builder` | — | Allowlisted defensive tool builder |
| `purple-request-broker` | — | Policy-gated hivemind broker |

### Emergency: stop all purple services without destroying the container

```
# From inside the container:
for svc in cheshire-omniversal hatter-omniversal resurrection-omniversal \
    zod-omniversal little-john-omniversal robin-omniversal ouroboros-omniversal \
    sophia host-bridge-monitor windows-host-bridge-monitor \
    purple-adaptive-builder purple-request-broker; do
  systemctl stop "$svc" 2>/dev/null || true
done
# Container remains running. Restart individual services with: systemctl start <name>
```

---

*For implementation details see the 8 polyglot scripts in this directory. For shared agent state see `PURPLE_STATE.md`.*
