#!/usr/bin/env bash
set -euo pipefail

# --- SOPHIA EVENT HOOK ---
_sophia_hook() {
    [[ -S "/run/sophia.sock" ]] && printf '%s\n' "$1" | (socat - UNIX-CONNECT:/run/sophia.sock 2>/dev/null || nc -U /run/sophia.sock -w 1 2>/dev/null) || true
}
# --- END SOPHIA EVENT HOOK ---


register_hivemind_capability() {
    local component="$1" domain="$2" capabilities="$3"
    local run_dir="/run/purple"
    local cap_dir="$run_dir/capabilities"
    local state_dir="$run_dir/state"
    local policy_dir="/etc/purple"
    local alien_dir="$run_dir/alien"
    mkdir -p "$cap_dir" "$state_dir" "$run_dir/requests" "$run_dir/decisions" "$run_dir/actions" "$run_dir/results" "$alien_dir/inbox" "$alien_dir/outbox" "$policy_dir" /var/lib/purple-team/hivemind 2>/dev/null || true
    touch "$run_dir/ouroboros_fifo" 2>/dev/null || true
    if [[ ! -f "$policy_dir/hivemind-policy.json" ]]; then
        cat > "$policy_dir/hivemind-policy.json" <<'POLICY'
{
  "schema": "purple-hivemind-policy-v1",
  "mode": "owner-authorized-defensive",
  "default_request_decision": "deny",
  "allowed_request_classes": ["status", "health", "capabilities", "evidence-list", "brl-status", "strat-list", "alien-hint"],
  "denied_request_classes": ["shell", "exec", "install", "network-change", "firewall-change", "script-modify", "credential-access", "lateral-movement"],
  "alien_sidecar": {"enabled": false, "authority": "advisory-only", "may_request": true, "may_act": false},
  "audit": {"append_only_events": true, "owner_visible": true}
}
POLICY
    fi
    {
        echo "schema=purple-hivemind-capability-v1"
        echo "component=$component"
        echo "domain=$domain"
        echo "capabilities=$capabilities"
        echo "authority=policy-gated"
        echo "ai_sidecar_required=no"
        echo "updated_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    } > "$cap_dir/$component.cap" 2>/dev/null || true
    {
        echo "schema=purple-hivemind-state-v1"
        echo "component=$component"
        echo "status=registered"
        echo "updated_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    } > "$state_dir/$component.state" 2>/dev/null || true
    printf 'HIVEMIND_CAPABILITY|%s|%s|%s
' "$component" "$domain" "$capabilities" >> "$run_dir/ouroboros_fifo" 2>/dev/null || true
}

# ------------------------------------------------------------
# Curl-based Go and Rust installers — never use emerge for these
# ------------------------------------------------------------
ensure_go() {
    command -v go &>/dev/null && return 0
    local arch; arch=$(uname -m)
    local goarch="amd64"; [[ "$arch" == "aarch64" ]] && goarch="arm64"
    curl -fsSL "https://go.dev/dl/go1.22.5.linux-${goarch}.tar.gz" -o /tmp/_go.tar.gz || return 1
    tar -C /usr/local -xzf /tmp/_go.tar.gz && rm -f /tmp/_go.tar.gz
    ln -sf /usr/local/go/bin/go /usr/local/bin/go
    ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt
    export PATH="/usr/local/go/bin:$PATH"
}

ensure_rust() {
    command -v rustc &>/dev/null && return 0
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable --no-modify-path
    local cargo="$HOME/.cargo/bin"
    ln -sf "${cargo}/rustc" /usr/local/bin/rustc 2>/dev/null || true
    ln -sf "${cargo}/cargo" /usr/local/bin/cargo 2>/dev/null || true
    export PATH="${cargo}:$PATH"
}

# ------------------------------------------------------------
# Package manager shim — works on Gentoo, Debian, RHEL, Arch, Alpine, FreeBSD
# ------------------------------------------------------------
pkg_install() {
    local pkgs=()
    for p in "$@"; do
        case "$p" in
            golang) ensure_go; continue ;;
            rustc)  ensure_rust; continue ;;
            bun)    continue ;;
        esac
        if command -v emerge &>/dev/null; then
            case "$p" in
                openbsd-netcat|nc) pkgs+=("net-analyzer/openbsd-netcat") ;;
                screen) pkgs+=("app-misc/screen") ;;
                bc) pkgs+=("sys-devel/bc") ;;
                lm-sensors) : ;;
                parted) pkgs+=("sys-block/parted") ;;
                socat) pkgs+=("net-misc/socat") ;;
                conntrack) pkgs+=("net-firewall/conntrack-tools") ;;
                golang) : ;;
                bun) : ;;
                lm-sensors) : ;;
                rustc) : ;;
                curl) pkgs+=("net-misc/curl") ;;
                git) pkgs+=("dev-vcs/git") ;;
                openssl) pkgs+=("dev-libs/openssl") ;;
                traceroute) pkgs+=("net-analyzer/traceroute") ;;
                sshpass) pkgs+=("net-misc/sshpass") ;;
                *) pkgs+=("$p") ;;
            esac
        else
            pkgs+=("$p")
        fi
    done

    if command -v emerge &>/dev/null; then
        emerge --quiet --noreplace "${pkgs[@]}"
    elif command -v apt-get &>/dev/null; then
        local apt_pkgs=()
        for p in "${pkgs[@]}"; do
            case "$p" in
                openbsd-netcat) apt_pkgs+=("netcat-openbsd") ;;
                bind-tools) apt_pkgs+=("dnsutils") ;;
                iproute2|net-tools|tcpdump|conntrack|lsof|curl|openssl|jq|procps|sysstat|tar|gzip|coreutils|screen|bc|traceroute|socat|nodejs) apt_pkgs+=("$p") ;;
                *) apt_pkgs+=("$p") ;;
            esac
        done
        DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${apt_pkgs[@]}" || {
            apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${apt_pkgs[@]}"
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
        echo "WARN: no supported package manager; skipping install of: ${pkgs[*]}" >&2
    fi
}

# ----------------------------------------------------------------
# Shared helpers: socket compat, load-order coordination
# ----------------------------------------------------------------
nc_unix_send() {
    local sock="$1" msg="$2"
    if command -v socat &>/dev/null; then
        printf '%s\n' "$msg" | socat - "UNIX-CONNECT:$sock" 2>/dev/null || true
    else
        printf '%s\n' "$msg" | nc -U "$sock" -w 1 2>/dev/null || true
    fi
}
signal_ready() { mkdir -p /run/purple/ready; touch "/run/purple/ready/$1"; }
wait_for()     {
    local name="$1" timeout="${2:-90}" elapsed=0
    while [[ ! -f "/run/purple/ready/$name" ]]; do
        (( elapsed >= timeout )) && { logger -t purple "WARN: timeout waiting for $name"; return 0; }
        sleep 2; (( elapsed += 2 ))
    done
}

# ------------------------------------------------------------
# Runtime service manager detection
# Environment awareness is separate from persistence method.
# In WSL-backed nspawn containers, /proc/version says WSL even when
# systemd is fully available inside the container.
# ------------------------------------------------------------
systemd_usable() {
    command -v systemctl &>/dev/null || return 1
    [[ -d /run/systemd/system ]] || return 1
    local state
    state=$(systemctl is-system-running 2>/dev/null || true)
    case "$state" in
        running|degraded|starting|initializing) return 0 ;;
        *) return 1 ;;
    esac
}

container_context() {
    if command -v systemd-detect-virt &>/dev/null; then
        systemd-detect-virt --container 2>/dev/null || true
        return 0
    fi
    awk -F/ '/docker|lxc|kubepods|machine.slice|systemd-nspawn/ {print $NF; found=1} END {exit found?0:1}' /proc/1/cgroup 2>/dev/null || true
}


host_bridge_capability_report() {
    local component="${1:-unknown}"
    local state_file="${PURPLE_HOST_BRIDGE_STATE:-/run/purple/host_bridge_capabilities}"
    local owner_copy="${PURPLE_HOST_BRIDGE_OWNER_COPY:-/var/lib/.sophia/host_bridge_capabilities}"
    local tmp="${state_file}.$$"
    local container="none"
    local host_proc="absent"
    local host_root="absent"
    local host_systemd="absent"
    local host_container_socket="absent"
    local windows_host_files="absent"
    local mode="container-sentinel"

    mkdir -p /run/purple /var/lib/.sophia 2>/dev/null || true

    container=$(container_context 2>/dev/null | head -1)
    [[ -z "$container" ]] && container="none"

    for p in /host/proc /mnt/host/proc /run/host/proc /hostfs/proc; do
        if [[ -r "$p/1/status" ]]; then host_proc="$p"; break; fi
    done

    for p in /host /mnt/host /run/host /hostfs; do
        if [[ -r "$p/etc/os-release" ]] || [[ -d "$p/Windows/System32" ]]; then host_root="$p"; break; fi
    done

    for p in /host/run/systemd/private /mnt/host/run/systemd/private /run/host/run/systemd/private /hostfs/run/systemd/private; do
        if [[ -S "$p" ]]; then host_systemd="$p"; break; fi
    done

    for p in /var/run/docker.sock /run/docker.sock /host/var/run/docker.sock /mnt/host/var/run/docker.sock /run/host/var/run/docker.sock; do
        if [[ -S "$p" ]]; then host_container_socket="$p"; break; fi
    done

    if [[ -d /mnt/c/Windows/System32 ]]; then
        windows_host_files="/mnt/c"
    fi

    if [[ "$host_proc" != "absent" ]] || [[ "$host_root" != "absent" ]] || [[ "$host_systemd" != "absent" ]] || [[ "$host_container_socket" != "absent" ]] || [[ "$windows_host_files" != "absent" ]]; then
        mode="host-bridge"
    fi

    {
        echo "schema=purple-host-bridge-v1"
        echo "component=$component"
        echo "updated_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "runtime_env=${ENV:-unknown}"
        echo "container_context=$container"
        echo "systemd_usable=$(systemd_usable && echo yes || echo no)"
        echo "mode=$mode"
        echo "host_proc=$host_proc"
        echo "host_root=$host_root"
        echo "host_systemd=$host_systemd"
        echo "host_container_socket=$host_container_socket"
        echo "windows_host_files=$windows_host_files"
        echo "owner_visible=yes"
        echo "attacker_decoy_profile=enabled"
    } > "$tmp" 2>/dev/null && mv "$tmp" "$state_file" 2>/dev/null || true

    cp "$state_file" "$owner_copy" 2>/dev/null || true
    chmod 0644 "$state_file" "$owner_copy" 2>/dev/null || true
    printf 'HOST_BRIDGE_MODE|%s|%s|%s\n' "$component" "$mode" "$container" >> /run/purple/ouroboros_fifo 2>/dev/null || true
}


# RESURRECTION_ID
# ==================================================================
# RESURRECTION PROTOCOL – OMNIVERSAL (WSL / DGX Spark / VPS)
# ==================================================================
# Encrypted recovery state, SSH decoy logging, recovery beacon.
# Environment‑aware resource limits, BGP hijack detection,
# thermal anomaly monitoring.
# ==================================================================

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "Must be run as root." >&2; exit 1
fi

# ------------------------------------------------------------
# 0. Environment detection
# ------------------------------------------------------------
ENV="unknown"
IS_WSL=false
IS_DGX=false
IS_VPS=false

if grep -qi microsoft /proc/version 2>/dev/null; then
    ENV="wsl"
    IS_WSL=true
elif nvidia-smi &>/dev/null && lspci | grep -qi nvidia; then
    ENV="dgx"
    IS_DGX=true
else
    if dmidecode -s system-manufacturer 2>/dev/null | grep -qiE "kvm|xen|vmware|virtualbox"; then
        ENV="vps"
        IS_VPS=true
    else
        ENV="bare"
    fi
fi
echo "Detected environment: $ENV"

DECOY_SSH_PORT="${DECOY_SSH_PORT:-2223}"   # distinct from Hatter's honeypot on 2224


# ------------------------------------------------------------
# 1. Environment‑specific resource limits
# ------------------------------------------------------------
MAX_OPEN_FILES=4096
MEMORY_LIMIT=3764M
CPU_QUOTA=400%
BEACON_INTERVAL=7200

# Fallback for initial run
[[ "$MAX_OPEN_FILES" == "4096" ]] && {
    if [[ "$ENV" == "wsl" ]]; then
        MAX_OPEN_FILES=4096
        MEMORY_LIMIT="512M"
        CPU_QUOTA="50%"
        BEACON_INTERVAL=7200   # 2 hours in WSL
    elif [[ "$ENV" == "dgx" ]]; then
        MAX_OPEN_FILES=1048576
        MEMORY_LIMIT="2G"
        CPU_QUOTA="200%"
        BEACON_INTERVAL=3600
    else
        MAX_OPEN_FILES=65536
        MEMORY_LIMIT="1G"
        CPU_QUOTA="100%"
        BEACON_INTERVAL=3600
    fi
}

# ------------------------------------------------------------
# 2. Anti‑BGP hijack detection
# ------------------------------------------------------------
bgp_hijack_detected() {
    local cache="/run/purple/asn_baseline"
    local my_ip asn
    my_ip=$(curl -s --max-time 5 https://api.ipify.org 2>/dev/null) || return 1
    asn=$(curl -s --max-time 5 "https://api.bgpview.io/ip/${my_ip}" \
        2>/dev/null | grep -o '"asn":[0-9]*' | head -1 | grep -o '[0-9]*')
    [[ -z "$asn" ]] && return 1
    if [[ ! -f "$cache" ]]; then
        echo "$asn" > "$cache"; return 1
    fi
    [[ "$(cat "$cache")" != "$asn" ]]
}

# ------------------------------------------------------------
# 3. Thermal/side‑channel anomaly detection
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

# ------------------------------------------------------------
# 4. Build Go resurrection state keeper (encrypted snapshot)
# ------------------------------------------------------------
build_go_resurrection() {
    cat > /tmp/resurrection.go << 'GO_RES'
package main

import (
    "crypto/rand"
    "os"
    "os/exec"
    "time"
)

const (
    encKeyPath = "/var/lib/.resurrection/key"
    stateTarPath = "/var/lib/.resurrection/state.tar.gz.enc"
)

func saveState() {
    // Tar critical directories
    dirs := []string{"/etc/purple-team", "/etc/cheshire", "/run/purple"}
    args := append([]string{"-czf", "/tmp/state.tar.gz"}, dirs...)
    cmd := exec.Command("tar", args...)
    if err := cmd.Run(); err != nil {
        return
    }
    defer os.Remove("/tmp/state.tar.gz")
    // Encrypt with openssl AES-256-CBC so beacon.sh can decrypt with same tool
    cmd = exec.Command("openssl", "enc", "-aes-256-cbc", "-pbkdf2",
        "-in", "/tmp/state.tar.gz",
        "-out", stateTarPath,
        "-pass", "file:"+encKeyPath)
    cmd.Run()
}

func main() {
    // Generate encryption key if not exists
    if _, err := os.Stat(encKeyPath); os.IsNotExist(err) {
        key := make([]byte, 32)
        rand.Read(key)
        os.WriteFile(encKeyPath, key, 0600)
    }
    // Save state every hour
    for {
        saveState()
        time.Sleep(3600 * time.Second)
    }
}
GO_RES
    go build -o /usr/local/bin/resurrection_keeper /tmp/resurrection.go
    chmod +x /usr/local/bin/resurrection_keeper
    rm -f /tmp/resurrection.go
}

# ------------------------------------------------------------
# 5. Build Go SSH decoy logger
# ------------------------------------------------------------
build_go_ssh_decoy_logger() {
    cat > /tmp/ssh_decoy_logger.go << 'GO_DECOY'
package main

import (
    "bufio"
    "fmt"
    "log"
    "net"
    "os"
    "syscall"
)

var ouroborosFifo *os.File

func init() {
    var err error
    ouroborosFifo, err = os.OpenFile("/run/purple/ouroboros_fifo", os.O_WRONLY|os.O_APPEND|syscall.O_NONBLOCK, 0666)
    if err != nil {
        ouroborosFifo = nil
    }
}

func report(msg string) {
    if ouroborosFifo != nil {
        fmt.Fprintln(ouroborosFifo, msg)
    }
}

func setAttackerIP(ip string) {
    f, err := os.OpenFile("/run/purple/attacker_ips", os.O_WRONLY|os.O_APPEND|syscall.O_NONBLOCK|os.O_CREATE, 0644)
    if err == nil {
        fmt.Fprintln(f, ip)
        f.Close()
    }
}

func fakeUpdate(conn net.Conn, ip string) {
    conn.Write([]byte("SSH-2.0-OpenSSH_8.9p1 Ubuntu-3\r\n"))
    setAttackerIP(ip)
    reader := bufio.NewReader(conn)
    for {
        line, err := reader.ReadString('\n')
        if err != nil {
            break
        }
        if line == "update\n" {
            conn.Write([]byte("Updating system...\n"))
            report(fmt.Sprintf("ATTACKER_REQUESTED_UPDATE|%s", ip))
        } else {
            report(fmt.Sprintf("ATTACKER_CMD|%s|%s", ip, line))
        }
    }
}

func main() {
    port := os.Getenv("DECOY_SSH_PORT")
    if port == "" { port = "2223" }
    l, err := net.Listen("tcp", ":"+port)
    if err != nil {
        log.Fatal(err)
    }
    for {
        conn, err := l.Accept()
        if err != nil {
            continue
        }
        ip := conn.RemoteAddr().(*net.TCPAddr).IP.String()
        go fakeUpdate(conn, ip)
    }
}
GO_DECOY
    go build -o /usr/local/bin/ssh_decoy_logger /tmp/ssh_decoy_logger.go
    chmod +x /usr/local/bin/ssh_decoy_logger
    rm -f /tmp/ssh_decoy_logger.go
}

# ------------------------------------------------------------
# 6. Build Bash beacon — dynamic owner escrow signal with Ed25519 verification
#    Sources: sophia_crypto probe (mDNS → DNS TXT → paste → Tor),
#    fallback to direct DNS TXT if binary unavailable.
# ------------------------------------------------------------
build_bash_beacon() {
    mkdir -p /var/lib/.resurrection
    cat > /var/lib/.resurrection/beacon.sh << 'BEACON'
#!/bin/bash
RESURRECT_DIR="/var/lib/.resurrection"
RUN_DIR="/run/purple"
BEACON_INTERVAL=7200

report_to_ouroboros() { echo "$1" >> "$RUN_DIR/ouroboros_fifo" 2>/dev/null || true; }

check_escrow_signal() {
    local signal=""

    # Primary: sophia_crypto probe — tries mDNS, DNS TXT, paste sites, Tor
    # Every source is Ed25519-verified before being accepted.
    if command -v sophia_crypto &>/dev/null && \
       [[ -f /var/lib/.sophia/keys/ed25519.pub ]]; then
        local probe_out
        probe_out=$(sophia_crypto probe 2>/dev/null) || true
        if [[ -n "$probe_out" ]]; then
            signal=$(echo "$probe_out" | grep "^PAYLOAD=" | cut -d= -f2-)
        fi
    fi

    echo "$signal"
}

while true; do
    signal=$(check_escrow_signal)
    if [[ "$signal" == *"RESURRECT"* ]]; then
        logger -t resurrection "Received resurrect signal – restoring Singularity"
        report_to_ouroboros "RESURRECT_SIGNAL_RECEIVED"
        touch "$RUN_DIR/resurrection_needed"
        _sophia_hook "RESURRECTION_NEEDED"
        for i in {1..30}; do
            [[ -f "$RUN_DIR/resurrection_acknowledged" ]] && break
            sleep 1
        done
        if [[ -f "$RESURRECT_DIR/state.tar.gz.enc" ]] && [[ -f "$RESURRECT_DIR/key" ]]; then
            openssl enc -d -aes-256-cbc -pbkdf2 \
                -in "$RESURRECT_DIR/state.tar.gz.enc" \
                -out /tmp/state.tar.gz \
                -pass file:"$RESURRECT_DIR/key"
            tar -xzf /tmp/state.tar.gz -C /
            for installer in /usr/local/sbin/install-*-omniversal.sh; do
                [[ -f "$installer" ]] && bash "$installer" &
            done
            report_to_ouroboros "RESTORATION_COMPLETE"
        fi
        break
    fi
    jitter=$(( BEACON_INTERVAL / 5 ))
    sleep_sec=$(( BEACON_INTERVAL - jitter + RANDOM % (jitter * 2 + 1) ))
    sleep "$sleep_sec"
done
BEACON
    sed -i "s/7200/$BEACON_INTERVAL/" /var/lib/.resurrection/beacon.sh
    chmod +x /var/lib/.resurrection/beacon.sh
}

# ------------------------------------------------------------
# 7. Build Go hivemind (orchestrates keeper, SSH decoy logger, beacon)
# ------------------------------------------------------------
build_go_hivemind() {
    cat > /tmp/resurrection_hivemind.go << 'GO_HIVE'
package main

import (
    "log"
    "os"
    "os/exec"
    "time"
)

type Proc struct {
    Name string
    Cmd  *exec.Cmd
}

func (p *Proc) run() {
    defer func() {
        if r := recover(); r != nil {
            log.Printf("[hivemind/%s] panic: %v — restarting in 3s", p.Name, r)
            time.Sleep(3 * time.Second)
            go p.run()
        }
    }()
    for {
        cmd := exec.Command(p.Cmd.Args[0], p.Cmd.Args[1:]...)
        if err := cmd.Run(); err != nil {
            log.Printf("[hivemind/%s] died: %v — respawning in 2s", p.Name, err)
        }
        time.Sleep(2 * time.Second)
    }
}

func main() {
    procs := []*Proc{}
    if _, err := os.Stat("/usr/local/bin/resurrection_keeper"); err == nil {
        procs = append(procs, &Proc{Name: "resurrection_keeper", Cmd: exec.Command("/usr/local/bin/resurrection_keeper")})
    }
    if _, err := os.Stat("/usr/local/bin/ssh_decoy_logger"); err == nil {
        procs = append(procs, &Proc{Name: "ssh_decoy_logger", Cmd: exec.Command("/usr/local/bin/ssh_decoy_logger")})
    }
    if _, err := os.Stat("/var/lib/.resurrection/beacon.sh"); err == nil {
        procs = append(procs, &Proc{Name: "beacon", Cmd: exec.Command("/var/lib/.resurrection/beacon.sh")})
    }
    for _, p := range procs {
        go p.run()
    }
    select {}
}
GO_HIVE
    go build -o /usr/local/bin/resurrection_hivemind /tmp/resurrection_hivemind.go
    chmod +x /usr/local/bin/resurrection_hivemind
    rm -f /tmp/resurrection_hivemind.go
}

# ------------------------------------------------------------
# 8. Install systemd service (with WSL fallback)
# ------------------------------------------------------------
install_service() {
    if ! systemd_usable; then
        pkg_install screen
        screen -dmS resurrection_hivemind /usr/local/bin/resurrection_hivemind
    else
        cat > /etc/systemd/system/resurrection-omniversal.service << SERVICE
[Unit]
Description=Resurrection Protocol Omniversal
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/resurrection_hivemind
Restart=always
RestartSec=10
LimitNOFILE=$MAX_OPEN_FILES
MemoryMax=$MEMORY_LIMIT
CPUQuota=$CPU_QUOTA

[Install]
WantedBy=multi-user.target
SERVICE
        systemctl daemon-reload
        systemctl enable resurrection-omniversal.service
        systemctl start resurrection-omniversal.service
    fi
}

# ------------------------------------------------------------
# 9. Background monitors for BGP and thermal threats
# ------------------------------------------------------------
monitor_threats() {
    while true; do
        if bgp_hijack_detected; then
            logger -t resurrection "BGP hijack detected – activating resurrection"
            ( echo "BGP_HIJACK" >> /run/purple/ouroboros_fifo & )
touch /run/purple/resurrection_needed
            _sophia_hook "RESURRECTION_NEEDED"
        fi
        if thermal_anomaly; then
            logger -t resurrection "Thermal anomaly detected – possible side‑channel"
            ( echo "THERMAL_ANOMALY" >> /run/purple/ouroboros_fifo & )
# Reduce CPU usage
            cpulimit -l 10 -p $$ 2>/dev/null || true
        fi
        sleep 30
    done
}

# ------------------------------------------------------------
# 10. Main
# ------------------------------------------------------------
main() {
    # Install dependencies
    if [[ "$ENV" == "wsl" ]]; then
        pkg_install golang bc lm-sensors traceroute openssl socat openbsd-netcat
    elif [[ "$ENV" == "dgx" ]]; then
        pkg_install golang bc lm-sensors traceroute openssl socat openbsd-netcat
    else
        pkg_install golang bc lm-sensors traceroute openssl socat openbsd-netcat
    fi

    mkdir -p /var/lib/.resurrection /run/purple
    host_bridge_capability_report "resurrection"
    register_hivemind_capability "resurrection" "recovery-decoy" "resurrection-keeper,ssh-decoy,owner-escrow-beacon"
    build_go_resurrection
    build_go_ssh_decoy_logger
    build_bash_beacon
    build_go_hivemind
    install_service
    monitor_threats &
    SELF="$0"
    cat > /usr/local/sbin/install-resurrection-omniversal.sh << INST
#!/bin/bash
exec bash "$SELF"
INST
    chmod +x /usr/local/sbin/install-resurrection-omniversal.sh
    signal_ready resurrection
    echo "Resurrection Protocol Omniversal deployed on $ENV."
}

main
# --- SOPHIA EVENT HOOK ---
_sophia_hook() {
    [[ -S "/run/sophia.sock" ]] && printf '%s\n' "$1" | (socat - UNIX-CONNECT:/run/sophia.sock 2>/dev/null || nc -U /run/sophia.sock -w 1 2>/dev/null) || true
}
# --- END SOPHIA EVENT HOOK ---
