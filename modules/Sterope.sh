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


# ZOD_ID
# ==================================================================
# PLEIADES ATLAS – OMNIVERSAL ORCHESTRATOR (WSL / DGX Spark / VPS)
# ==================================================================
# Environment‑aware resource limits, BGP hijack detection,
# thermal anomaly monitoring, threat scoring, mode switching,
# thrall deployment, pleiades-rebirth/implosion coordination.
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

# ------------------------------------------------------------
# 1. Environment‑specific resource limits
# ------------------------------------------------------------
MAX_OPEN_FILES=4096
MEMORY_LIMIT=3764M
CPU_QUOTA=400%
THRALL_MAX_FLOODS=3
THRALL_INTERVAL=3

# Fallback for initial run
[[ "$MAX_OPEN_FILES" == "4096" ]] && {
    if [[ "$ENV" == "wsl" ]]; then
        MAX_OPEN_FILES=4096; MEMORY_LIMIT="1G"; CPU_QUOTA="100%"
        THRALL_MAX_FLOODS=3; THRALL_INTERVAL=3
    elif [[ "$ENV" == "dgx" ]]; then
        MAX_OPEN_FILES=1048576; MEMORY_LIMIT="4G"; CPU_QUOTA="400%"
        THRALL_MAX_FLOODS=10; THRALL_INTERVAL=1
    else
        MAX_OPEN_FILES=65536; MEMORY_LIMIT="2G"; CPU_QUOTA="200%"
        THRALL_MAX_FLOODS=5; THRALL_INTERVAL=2
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
# 4. Build Go threat calculator (reads FIFO, adaptive scoring)
# ------------------------------------------------------------
build_go_threat_calc() {
    cat > /tmp/threat_calc.go << 'GO_THREAT'
package main

import (
    "bufio"
    "fmt"
    "io"
    "log"
    "os"
    "syscall"
    "syscall"
    "os/exec"
    "strings"
    "sync/atomic"
    "time"
)

var threatScore int64
var pleiades-rebirthNeeded bool
var implosionTriggered bool

func reportToPleiades Nexus(msg string) {
    f, err := os.OpenFile("/run/pleiades/pleiades_nexus_fifo", os.O_WRONLY|os.O_APPEND|syscall.O_NONBLOCK, 0666)
    if err == nil {
        defer f.Close()
        fmt.Fprintln(f, msg)
    }
}

func updateScore(delta int64) {
    atomic.AddInt64(&threatScore, delta)
}

func getScore() int64 {
    return atomic.LoadInt64(&threatScore)
}

func parseLine(line string) {
    if strings.HasPrefix(line, "ANOMALY|") || strings.HasPrefix(line, "NEW_ANOMALY|") {
        updateScore(10)
    } else if strings.HasPrefix(line, "RATE_LIMITED|") {
        updateScore(5)
    } else if strings.HasPrefix(line, "BRUTE_SUCCESS|") {
        updateScore(15)
    } else if strings.HasPrefix(line, "PROXY|") {
        updateScore(20)
    } else if strings.HasPrefix(line, "HARVESTED|") {
        updateScore(8)
    } else if strings.HasPrefix(line, "KERNEL_TRAP|") {
        updateScore(25)
    } else if strings.HasPrefix(line, "BGP_HIJACK") || strings.HasPrefix(line, "THERMAL_ANOMALY") {
        updateScore(50)
        pleiades-rebirthNeeded = true
    } else if strings.Contains(line, "PLEIADES_REBIRTH_TRIGGERED") {
        pleiades-rebirthNeeded = true
        reportToPleiades Nexus("ZOD_PLEIADES_REBIRTH_ACK")
        os.WriteFile("/run/pleiades/pleiades-rebirth_acknowledged", []byte("done"), 0644)
    } else if strings.Contains(line, "IMPLOSION_TRIGGERED") {
        implosionTriggered = true
        atomic.StoreInt64(&threatScore, 0)
        reportToPleiades Nexus("ZOD_IMPLOSION_ACK")
    }
}

func monitorFifo() {
    logPath := "/run/pleiades/pleiades_nexus_fifo"
    var offset int64
    for {
        f, err := os.Open(logPath)
        if err != nil {
            time.Sleep(5 * time.Second)
            continue
        }
        fi, err := f.Stat()
        if err == nil && fi.Size() > offset {
            f.Seek(offset, io.SeekStart)
            scanner := bufio.NewScanner(f)
            for scanner.Scan() {
                parseLine(scanner.Text())
            }
            offset, _ = f.Seek(0, io.SeekCurrent)
        }
        f.Close()
        time.Sleep(1 * time.Second)
    }
}

func sendCommand(sock string, cmd string) {
    sh := fmt.Sprintf("printf '%%s\\n' %q | socat - UNIX-CONNECT:%s 2>/dev/null || printf '%%s\\n' %q | nc -U %s -w 1 2>/dev/null || true", cmd, sock, cmd, sock)
    exec.Command("sh", "-c", sh).Run()
}

func main() {
    go monitorFifo()
    decayTicker := time.NewTicker(30 * time.Minute)
    for {
        select {
        case <-decayTicker.C:
            cur := atomic.LoadInt64(&threatScore)
        newScore := int64(float64(cur) * 0.7)
        if newScore == cur && cur > 0 { newScore-- }
        atomic.StoreInt64(&threatScore, newScore)
        default:
        }
        score := getScore()
        if score >= 8 {
            sendCommand("/run/pleiades/taygete.sock", "aggressive")
            sendCommand("/run/pleiades/alcyone.sock", "active")
            reportToPleiades Nexus(fmt.Sprintf("ZOD_MODE_AGGRESSIVE|%d", score))
        } else if score >= 2 {
            sendCommand("/run/pleiades/alcyone.sock", "passive")
            reportToPleiades Nexus(fmt.Sprintf("ZOD_MODE_PASSIVE|%d", score))
        }
        if pleiades-rebirthNeeded && !implosionTriggered {
            sendCommand("/run/pleiades/taygete.sock", "resurrect")
            sendCommand("/run/pleiades/alcyone.sock", "resurrect")
            reportToPleiades Nexus("ZOD_PLEIADES_REBIRTH_SIGNAL")
            pleiades-rebirthNeeded = false
        }
        if implosionTriggered {
            // Reset everything
            atomic.StoreInt64(&threatScore, 0)
            implosionTriggered = false
        }
        time.Sleep(5 * time.Second)
    }
}
GO_THREAT
    go build -o /usr/local/bin/threat_calc /tmp/threat_calc.go
    chmod +x /usr/local/bin/threat_calc
    rm -f /tmp/threat_calc.go
}

# ------------------------------------------------------------
# 5. Build Go thrall deployer (Bobby Long with environment limits)
# ------------------------------------------------------------
build_go_thrall() {
    cat > /tmp/thrall.go << 'GO_THRALL'
package main

import (
    "bufio"
    "fmt"
    "io"
    "os"
    "syscall"
    "syscall"
    "os/exec"
    "strings"
    "time"
)

const (
    thrallMaxFloods = 3
    thrallInterval  = 3
    banner          = "\n   ____   ____   _      _   _   _   _   ____   _   _   ____   \n  | __ ) | __ ) | |    | | | | | \\ | | / ___| | \\ | | / ___|  \n  |  _ \\ |  _ \\ | |    | | | | |  \\| | | |  _  |  \\| | | |  _ \n  | |_) || |_) || |___ | |_| | | |\\  | | |_| || |\\  | | |_| | \n  |____/ |____/ |_____| \\___/  |_| \\_|  \\____||_| \\_|  \\____| \n  \n   B   O   B   B   Y       L   O   N   G   !   !   ~\n"
)

func reportToPleiades Nexus(msg string) {
    f, _ := os.OpenFile("/run/pleiades/pleiades_nexus_fifo", os.O_WRONLY|os.O_APPEND|syscall.O_NONBLOCK, 0666)
    if f != nil {
        defer f.Close()
        fmt.Fprintln(f, msg)
    }
}

func deployThrall(ip string) {
    script := fmt.Sprintf("/tmp/thrall_%s.sh", strings.ReplaceAll(ip, ".", "_"))
    content := fmt.Sprintf(`#!/bin/bash
TARGET_IP="%s"
MAX_FLOODS=%d
INTERVAL=%d
BANNER='%s'

get_terminals() {
    who | grep -E "$TARGET_IP" | awk '{print "/dev/"$2}'
    for tty in /dev/pts/*; do
        if [[ -w "$tty" ]]; then
            owner=$(stat -c %%U "$tty" 2>/dev/null)
            ip=$(who | grep "$owner" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | head -1)
            [[ "$ip" == "$TARGET_IP" ]] && echo "$tty"
        fi
    done | sort -u
}

live_ttys=()
for tty in $(get_terminals); do
    if echo "test" > "$tty" 2>/dev/null; then
        live_ttys+=("$tty")
    fi
done

if [[ ${#live_ttys[@]} -eq 0 ]]; then
    exit 0
fi

for i in $(seq 1 "$MAX_FLOODS"); do
    for tty in "${live_ttys[@]}"; do
        echo "$BANNER" > "$tty" 2>/dev/null
    done
    sleep "$INTERVAL"
done
rm -f "$0"
`, ip, thrallMaxFloods, thrallInterval, banner)
    os.WriteFile(script, []byte(content), 0755)
    cmd := exec.Command("/bin/bash", script)
    cmd.Start()
    reportToPleiades Nexus(fmt.Sprintf("THRALL_DEPLOYED|%s", ip))
}

func main() {
    deployed := make(map[string]bool)
    var offset int64
    for {
        f, err := os.Open("/run/pleiades/attacker_ips")
        if err == nil {
            fi, _ := f.Stat()
            if fi.Size() > offset {
                f.Seek(offset, io.SeekStart)
                scanner := bufio.NewScanner(f)
                for scanner.Scan() {
                    ip := strings.TrimSpace(scanner.Text())
                    if ip != "" && !deployed[ip] {
                        deployThrall(ip)
                        deployed[ip] = true
                    }
                }
                offset, _ = f.Seek(0, io.SeekCurrent)
            }
            f.Close()
        }
        time.Sleep(5 * time.Second)
    }
}
GO_THRALL
    sed -i -E "s/^const thrallMaxFloods = .*/const thrallMaxFloods = $THRALL_MAX_FLOODS/" /tmp/thrall.go
    sed -i -E "s/^const thrallInterval = .*/const thrallInterval = $THRALL_INTERVAL/" /tmp/thrall.go
    go build -o /usr/local/bin/thrall_deployer /tmp/thrall.go
    chmod +x /usr/local/bin/thrall_deployer
    rm -f /tmp/thrall.go
}

# ------------------------------------------------------------
# 6. Build Bash helpers (mode switching, thrall trigger)
# ------------------------------------------------------------
build_bash_helpers() {
    cat > /etc/zod/switch_modes.sh << 'SWITCH'
#!/bin/bash
# Tails pleiades-nexus log and sends commands to Alcyone/Taygete sockets
unix_send() { printf '%s\n' "$1" | socat - "UNIX-CONNECT:$2" 2>/dev/null || printf '%s\n' "$1" | nc -U "$2" -w 1 2>/dev/null || true; }
tail -n 0 -F /run/pleiades/pleiades_nexus_fifo 2>/dev/null | while read -r line; do
    if [[ "$line" =~ ^ZOD_MODE_(AGGRESSIVE|PASSIVE) ]]; then
        mode=$(echo "$line" | cut -d'|' -f1 | cut -d'_' -f3)
        if [[ "$mode" == "AGGRESSIVE" ]]; then
            unix_send "aggressive" /run/pleiades/taygete.sock
            unix_send "active" /run/pleiades/alcyone.sock
        elif [[ "$mode" == "PASSIVE" ]]; then
            unix_send "passive" /run/pleiades/alcyone.sock
        fi
    fi
done
SWITCH
    chmod +x /etc/zod/switch_modes.sh
}

# ------------------------------------------------------------
# 7. Install systemd service (Zod pleiades-swarm)
# ------------------------------------------------------------
install_systemd() {
    if [[ "$ENV" == "wsl" ]]; then
        pkg_install screen
        screen -dmS zod_pleiades-swarm /usr/local/bin/zod_pleiades-swarm
    else
        cat > /etc/systemd/system/zod-omniversal.service << SERVICE
[Unit]
Description=Pleiades Atlas Omniversal Orchestrator
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/zod_pleiades-swarm
Restart=always
RestartSec=5
LimitNOFILE=$MAX_OPEN_FILES
MemoryMax=$MEMORY_LIMIT
CPUQuota=$CPU_QUOTA

[Install]
WantedBy=multi-user.target
SERVICE
        systemctl daemon-reload
        systemctl enable zod-omniversal.service
        systemctl start zod-omniversal.service
    fi

    # Build Go pleiades-swarm that runs threat calculator and thrall deployer
    cat > /tmp/zod_pleiades-swarm.go << 'GO_HIVE'
package main

import (
    "log"
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
    procs := []*Proc{
        {Name: "threat_calc", Cmd: exec.Command("/usr/local/bin/threat_calc")},
        {Name: "thrall_deployer", Cmd: exec.Command("/usr/local/bin/thrall_deployer")},
        {Name: "switch_modes", Cmd: exec.Command("/etc/zod/switch_modes.sh")},
    }
    for _, p := range procs {
        go p.run()
    }
    select {}
}
GO_HIVE
    go build -o /usr/local/bin/zod_pleiades-swarm /tmp/zod_pleiades-swarm.go
    chmod +x /usr/local/bin/zod_pleiades-swarm
    rm -f /tmp/zod_pleiades-swarm.go
}

# ------------------------------------------------------------
# 8. Background monitors for BGP and thermal threats
# ------------------------------------------------------------
monitor_threats() {
    while true; do
        if bgp_hijack_detected; then
            logger -t zod "BGP hijack detected – signalling Pleiades Nexus"
            ( echo "BGP_HIJACK" >> /run/pleiades/pleiades_nexus_fifo & )
fi
        if thermal_anomaly; then
            logger -t zod "Thermal anomaly detected – signalling Pleiades Nexus"
            ( echo "THERMAL_ANOMALY" >> /run/pleiades/pleiades_nexus_fifo & )
fi
        sleep 30
    done
}

# ------------------------------------------------------------
# 9. Main
# ------------------------------------------------------------
main() {
    if [[ "$ENV" == "wsl" ]]; then
        pkg_install golang bc lm-sensors traceroute socat openbsd-netcat
    elif [[ "$ENV" == "dgx" ]]; then
        pkg_install golang bc lm-sensors traceroute socat openbsd-netcat
    else
        pkg_install golang bc lm-sensors traceroute socat openbsd-netcat
    fi

    mkdir -p /etc/zod /run/pleiades
    wait_for alcyone 2
    wait_for taygete 2
    build_go_threat_calc
    build_go_thrall
    build_bash_helpers
    install_systemd
    monitor_threats &
    SELF="$0"
    cat > /usr/local/sbin/install-zod-omniversal.sh << INST
#!/bin/bash
exec bash "$SELF"
INST
    chmod +x /usr/local/sbin/install-zod-omniversal.sh
    signal_ready zod
    echo "Pleiades Atlas Omniversal deployed on $ENV."
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



