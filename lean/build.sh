#!/usr/bin/env bash
# build.sh — install the lean Pleiades stack into THIS system (run inside the
# container as root). Idempotent. No network, no curl|sh, no runtime compile.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
log() { echo "[build] $*"; }

command -v openssl >/dev/null || { echo "[build] FATAL: openssl missing (emerge dev-libs/openssl)"; exit 1; }

log "installing shared lib"
install -d /usr/local/lib/pleiades
install -m 0644 "$SRC/lib/pleiades-common.sh" /usr/local/lib/pleiades/pleiades-common.sh

log "installing maia (trust root)"
install -m 0755 "$SRC/agents/maia/maia-crypto"     /usr/local/bin/maia-crypto
install -m 0755 "$SRC/agents/maia/maia-overseer.sh" /usr/local/sbin/maia-overseer.sh

log "installing nexus tools"
install -m 0755 "$SRC/agents/nexus/nexus-verify"   /usr/local/bin/nexus-verify

log "installing taygete (honeypot sensor)"
install -m 0755 "$SRC/agents/taygete/taygete-handler.sh" /usr/local/sbin/taygete-handler.sh

log "installing celaeno (watchdog)"
install -m 0755 "$SRC/agents/celaeno/celaeno-watch.sh" /usr/local/sbin/celaeno-watch.sh

log "installing electra (decoy farm)"
install -m 0755 "$SRC/agents/electra/electra-decoy.sh" /usr/local/sbin/electra-decoy.sh

log "installing alcyone (read-only recon)"
install -m 0755 "$SRC/agents/alcyone/alcyone-recon.sh" /usr/local/sbin/alcyone-recon.sh

log "installing merope (snapshot/restore)"
install -m 0755 "$SRC/agents/merope/merope-rebirth.sh" /usr/local/sbin/merope-rebirth.sh

log "installing sterope (threat scoring)"
install -m 0755 "$SRC/agents/sterope/sterope-score.sh" /usr/local/sbin/sterope-score.sh

log "installing units"
for u in "$SRC"/units/*.service "$SRC"/units/*.socket "$SRC"/units/*.timer; do
    [ -e "$u" ] && install -m 0644 "$u" /etc/systemd/system/
done

# Guard the old stack's #1 bug: every unit ExecStart binary must exist.
fail=0
while IFS= read -r bin; do
    [[ -z "$bin" ]] && continue
    [[ -x "$bin" ]] || { echo "[build] ERROR: unit ExecStart missing: $bin"; fail=1; }
done < <(awk -F= '/^ExecStart=/{print $2}' "$SRC"/units/*.service | awk '{print $1}')
[[ "$fail" -eq 0 ]] || { echo "[build] FAILED: unit/binary mismatch"; exit 1; }

# Cadence guard: no in-process busy loops should ship in our daemons.
if grep -RnE '^[[:space:]]*while[[:space:]]+(true|:)' "$SRC/agents" >/dev/null 2>&1; then
    echo "[build] ERROR: in-process while-true loop found in an agent — use a .timer instead"; exit 1
fi

systemctl daemon-reload
log "done."
log "enable with: systemctl enable --now pleiades-maia.service pleiades-maia-checkpoint.timer"
