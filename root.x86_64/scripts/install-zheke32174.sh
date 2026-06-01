#!/usr/bin/env bash
# install-zheke32174.sh — clone and integrate Zheke32174 repos
# Task #12
set -euo pipefail
LOG_TAG="zheke32174"; log() { printf '[%s] %s\n' "$LOG_TAG" "$*" >&2; }
BASE="https://github.com/Zheke32174"
EXT="/workspaces/gentoo/external/zheke32174"
TOOLS="/workspaces/gentoo/tools"
CAP_DIR="/run/pleiades/capabilities"
mkdir -p "$EXT" "$TOOLS" "$CAP_DIR"

clone_or_update() {
    local repo="$1" dest="$2"
    if [[ -d "$dest/.git" ]]; then git -C "$dest" pull --ff-only 2>/dev/null || true
    else git clone --depth=1 "$BASE/$repo.git" "$dest" || log "WARN: clone $repo failed"; fi
}

# Clone all four repos
for repo in alien scandroid Tracendroid underlode; do
    clone_or_update "$repo" "$EXT/$repo"
done

# Merge alien fork improvements into local alien-bsd
if [[ -d "$EXT/alien" ]]; then
    log "Diffing alien fork vs local alien-bsd"
    diff "$EXT/alien/alien-bsd" /workspaces/gentoo/alien-bsd 2>/dev/null \
        >> "$EXT/MERGE_LOG.md" || true
    log "Diff written to MERGE_LOG.md (review and apply manually)"
fi

# Symlink analysis tools into tools/ and register capabilities
for repo in scandroid Tracendroid underlode; do
    [[ -d "$EXT/$repo" ]] && ln -sfn "$EXT/$repo" "$TOOLS/$repo" || true
done

# Register capabilities
declare -A DOMAINS=(["scandroid"]="reverse_engineering" ["Tracendroid"]="forensics" ["underlode"]="reverse_engineering")
for repo in scandroid Tracendroid underlode; do
    {
        echo "schema=pleiades-pleiades-swarm-capability-v1"
        echo "component=${repo,,}"
        echo "domain=${DOMAINS[$repo]}"
        echo "authority=policy-gated"
        echo "path=$TOOLS/$repo"
        echo "updated_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    } > "$CAP_DIR/${repo,,}.cap"
done

log "Zheke32174 integration complete. Review $EXT/MERGE_LOG.md for alien merge."
