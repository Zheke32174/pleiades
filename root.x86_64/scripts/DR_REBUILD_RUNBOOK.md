# Disaster Recovery Rebuild Runbook
# Task #4: Full pleiades-team container from-scratch test

**SAFETY**: Do NOT execute Phase 2+ without explicit operator approval.
Run `phase1_backup` first and confirm backup integrity before proceeding.

## Pre-flight Checklist

- [x] Stage3 archive: `stage3-amd64-systemd-20260524T170105Z.tar.xz`
- [x] All 8 polyglot scripts present in `root.x86_64/scripts/`
- [ ] Disk space verified (rootfs + backup must both fit)
- [ ] Current container state backed up to MEGA or local archive
- [ ] Operator approval received

## Phase 1 — Backup (safe, no destruction)

```bash
# 1. Stop the container gracefully
sudo systemctl stop pleiades-gentoo-heartbeat.timer
tmux -L pleiades-gentoo send-keys -t gentoo "sudo systemctl poweroff" Enter

# 2. Archive current rootfs
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
sudo tar -C /workspaces/gentoo --exclude=root.x86_64/host/proc \
         --exclude=root.x86_64/host/sys --exclude=root.x86_64/host/run \
         --exclude=root.x86_64/host/mnt -czf \
         /workspaces/gentoo/rootfs-backup-${STAMP}.tar.gz root.x86_64
echo "Backup: rootfs-backup-${STAMP}.tar.gz"
```

## Phase 2 — Fresh rootfs (DESTRUCTIVE — requires approval)

```bash
# 3. Move old rootfs aside
sudo mv /workspaces/gentoo/root.x86_64 /workspaces/gentoo/root.x86_64.old.${STAMP}

# 4. Extract fresh stage3
sudo mkdir -p /workspaces/gentoo/root.x86_64
sudo tar -C /workspaces/gentoo/root.x86_64 \
    -xpf /workspaces/gentoo/stage3-amd64-systemd-20260524T170105Z.tar.xz \
    --xattrs-include='*.*' --numeric-owner
echo "Fresh rootfs extracted"

# 5. Restore scripts directory
sudo cp -a /workspaces/gentoo/root.x86_64.old.${STAMP}/scripts \
           /workspaces/gentoo/root.x86_64/scripts
```

## Phase 3 — Deploy polyglot stack (in order)

```bash
# Inside the container after first boot
SCRIPTS=/workspaces/gentoo/root.x86_64/scripts
ORDER=(Maia.sh Taygete.sh Alcyone.sh Electra.sh Celaeno.sh Sterope.sh Merope.sh Atlas.sh)

for script in "${ORDER[@]}"; do
    echo "=== Deploying $script ==="
    sudo nsenter -t $CONTAINER_PID -m -u -i -n -p -- \
        bash "/scripts/${script}" 2>&1 | tee "/tmp/deploy-${script}.log"
    echo "Exit: $?"
    sleep 5
done
```

## Phase 4 — Verification

```bash
# Expected active services (12 total)
EXPECTED=(
    taygete-omniversal.service
    alcyone-omniversal.service
    pleiades-rebirth-omniversal.service
    atlas-omniversal.service
    celaeno-omniversal.service
    electra-omniversal.service
    pleiades-nexus-omniversal.service
    maia.service
    host-bridge-monitor.service
    windows-host-bridge-monitor.service
    pleiades-adaptive-builder.service
    pleiades-request-broker.service
)

for svc in "${EXPECTED[@]}"; do
    state=$(nsenter -t $CONTAINER_PID -- systemctl is-active "$svc" 2>/dev/null)
    echo "$state: $svc"
done

# Port liveness
for port in 2222 2223 2224; do
    ss -tlnp "( sport = :$port )" | grep -q LISTEN && echo "PASS: port $port" || echo "FAIL: port $port"
done

# Run regression
nsenter -t $CONTAINER_PID -- /scripts/pleiades-regression.sh
```

## Expected Result

- `PASS=52 FAIL=0 SKIP=0` (matches last known-good regression score)
- All 12 services active
- Ports 2222/2223/2224 listening
- Bridge bridges visible inside container

## Rollback

```bash
# If rebuild fails, restore backup:
sudo mv /workspaces/gentoo/root.x86_64 /workspaces/gentoo/root.x86_64.failed
sudo mv /workspaces/gentoo/root.x86_64.old.${STAMP} /workspaces/gentoo/root.x86_64
sudo systemctl start pleiades-gentoo-heartbeat.service
```
