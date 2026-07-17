#!/usr/bin/env bash
# build.sh — install the lean Pleiades stack into this system.
# Run inside the container as root. Idempotent, offline, no runtime compile.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
log() { echo "[build] $*"; }

command -v openssl >/dev/null || {
    echo "[build] FATAL: openssl missing (emerge dev-libs/openssl)"
    exit 1
}

log "installing shared library"
install -d /usr/local/lib/pleiades
install -m 0644 "$SRC/lib/pleiades-common.sh" /usr/local/lib/pleiades/pleiades-common.sh

log "installing authority policy registry"
install -d -m 0750 /etc/pleiades/policy
install -m 0640 "$SRC/policy/authority-actions.v1.json" /etc/pleiades/policy/authority-actions.v1.json

log "installing maia and nexus"
install -m 0755 "$SRC/agents/maia/maia-crypto"       /usr/local/bin/maia-crypto
install -m 0755 "$SRC/agents/maia/maia-overseer.sh" /usr/local/sbin/maia-overseer.sh
install -m 0755 "$SRC/agents/nexus/nexus-verify"     /usr/local/bin/nexus-verify

log "installing sensor and recovery agents"
install -m 0755 "$SRC/agents/taygete/taygete-handler.sh" /usr/local/sbin/taygete-handler.sh
install -m 0755 "$SRC/agents/celaeno/celaeno-watch.sh"   /usr/local/sbin/celaeno-watch.sh
install -m 0755 "$SRC/agents/electra/electra-decoy.sh"  /usr/local/sbin/electra-decoy.sh
install -m 0755 "$SRC/agents/alcyone/alcyone-recon.sh"  /usr/local/sbin/alcyone-recon.sh
install -m 0755 "$SRC/agents/merope/merope-rebirth.sh"  /usr/local/sbin/merope-rebirth.sh
install -m 0755 "$SRC/agents/sterope/sterope-score.sh"  /usr/local/sbin/sterope-score.sh

log "installing systemd units and resource slice"
for u in "$SRC"/units/*.service "$SRC"/units/*.socket "$SRC"/units/*.timer "$SRC"/units/*.slice; do
    [[ -e "$u" ]] && install -m 0644 "$u" /etc/systemd/system/
done

# Guard the old stack's primary failure: every ExecStart binary must exist.
fail=0
while IFS= read -r bin; do
    [[ -z "$bin" ]] && continue
    [[ -x "$bin" ]] || {
        echo "[build] ERROR: unit ExecStart missing: $bin"
        fail=1
    }
done < <(awk -F= '/^ExecStart=/{print $2}' "$SRC"/units/*.service | awk '{print $1}')
[[ "$fail" -eq 0 ]] || {
    echo "[build] FAILED: unit/binary mismatch"
    exit 1
}

# Every service participates in the global resource circuit breaker.
for u in "$SRC"/units/*.service; do
    grep -Fxq 'Slice=pleiades.slice' "$u" || {
        echo "[build] ERROR: $(basename "$u") is outside pleiades.slice"
        exit 1
    }
done

# Cadence and evidence guards inspect executable runtime sources, not historical
# review documents that intentionally quote the old failure patterns.
if grep -RnE '^[[:space:]]*while[[:space:]]+(true|:)' "$SRC/agents"; then
    echo "[build] ERROR: in-process infinite loop found — use event activation or a timer"
    exit 1
fi
if grep -RInE 'journalctl[[:space:]].*--vacuum|curl[^|]*\|[[:space:]]*(sh|bash)' \
    "$SRC/agents" "$SRC/lib" "$SRC/ops" "$SRC/units"; then
    echo "[build] ERROR: prohibited evidence erasure or curl-pipe execution"
    exit 1
fi
if grep -RIn 'Restart=always' "$SRC/units"; then
    echo "[build] ERROR: prohibited infinite restart policy"
    exit 1
fi

systemctl daemon-reload
log "done"
log "enable with: systemctl enable --now pleiades-maia.service pleiades-maia-checkpoint.timer"
