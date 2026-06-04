#!/usr/bin/env bash
set -uo pipefail

# Source shared library
source /usr/local/lib/pleiades-common.sh 2>/dev/null || source "$(dirname "$0")/pleiades-common.sh"
# Source configuration
source /etc/purple/pleiades.conf 2>/dev/null || source "$(dirname "$0")/../etc/purple/pleiades.conf"

# ------------------------------------------------------------
# Curl-based Go and Rust installers — never use emerge for these
# ------------------------------------------------------------

# ------------------------------------------------------------
# Package manager shim — works on Gentoo, Debian, RHEL, Arch, Alpine, FreeBSD
# ------------------------------------------------------------

# ----------------------------------------------------------------
# Shared helpers: socket compat, load-order coordination
# ----------------------------------------------------------------

# ------------------------------------------------------------
# Runtime service manager detection
# Environment awareness is separate from persistence method.
# In WSL-backed nspawn containers, /proc/version says WSL even when
# systemd is fully available inside the container.
# ------------------------------------------------------------

# ZOD_ID
# ==================================================================
# PLEIADES ATLAS – OMNIVERSAL ORCHESTRATOR (WSL / DGX Spark / VPS)
# ==================================================================
# Environment‑aware resource limits, BGP hijack detection,
# thermal anomaly monitoring, threat scoring, mode switching,
# thrall deployment, pleiades-rebirth/containment coordination.
# ==================================================================

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "Must be run as root." >&2; exit 1
fi

# ------------------------------------------------------------
# ------------------------------------------------------------
# 0. Environment detection
# ------------------------------------------------------------
ENV="unknown"
IS_BARE_METAL=false
IS_WSL=false
IS_VPS=false

if grep -qi microsoft /proc/version 2>/dev/null; then
    ENV="wsl"
    IS_WSL=true
elif [[ -d /sys/firmware/efi ]] && ! systemd-detect-virt --container &>/dev/null && ! systemd-detect-virt --vm &>/dev/null; then
    ENV="bare-metal"
    IS_BARE_METAL=true
else
    if dmidecode -s system-manufacturer 2>/dev/null | grep -qiE "kvm|xen|vmware|virtualbox"; then
        ENV="vps"
        IS_VPS=true
    else
        ENV="bare-metal"
        IS_BARE_METAL=true
    fi
fi

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
    elif [[ "$ENV" == "bare-metal" ]]; then
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

# ------------------------------------------------------------
# 3. Thermal/side‑channel anomaly detection
# ------------------------------------------------------------

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
    "os"
    "syscall"
    "os/exec"
    "strings"
    "sync/atomic"
    "time"
)

var threatScore int64
var pleiadesRebirthNeeded bool
var containmentTriggered bool

func reportToPleiadesNexus(msg string) {
    f, err := os.OpenFile("/run/pleiades/pleiades-nexus_fifo", os.O_WRONLY|os.O_APPEND|syscall.O_NONBLOCK, 0666)
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
    } else if strings.HasPrefix(line, "CREDENTIAL_FINDING|") {
        updateScore(15)
    } else if strings.HasPrefix(line, "PROXY|") {
        updateScore(20)
    } else if strings.HasPrefix(line, "HARVESTED|") {
        updateScore(8)
    } else if strings.HasPrefix(line, "HOSTILE_RECON|") {
        updateScore(6)
    } else if strings.HasPrefix(line, "KERNEL_TRAP|") {
        updateScore(25)
    } else if strings.HasPrefix(line, "FORENSIC_OBSERVATION|score=") {
        parts := strings.SplitN(line, "|", 3)
        if len(parts) >= 2 {
            scorePart := strings.TrimPrefix(parts[1], "score=")
            var fs int64
            fmt.Sscanf(scorePart, "%d", &fs)
            updateScore(fs)
        }
        if strings.Contains(line, "PROMISCUOUS_MODE") || strings.Contains(line, "KERNEL_MODULE_SPIKE") {
            updateScore(20)
        }
    } else if strings.HasPrefix(line, "BGP_HIJACK") || strings.HasPrefix(line, "THERMAL_ANOMALY") {
        updateScore(50)
        pleiadesRebirthNeeded = true
    } else if strings.Contains(line, "PLEIADES_REBIRTH_TRIGGERED") {
        pleiadesRebirthNeeded = true
        reportToPleiadesNexus("ZOD_PLEIADES_REBIRTH_ACK")
        os.WriteFile("/run/pleiades/pleiades-rebirth_acknowledged", []byte("done"), 0644)
    } else if strings.Contains(line, "CONTAINMENT_TRIGGERED") {
        containmentTriggered = true
        atomic.StoreInt64(&threatScore, 0)
        reportToPleiadesNexus("ZOD_containment_ACK")
    }
}

func monitorFifo() {
    logPath := "/run/pleiades/pleiades-nexus_fifo"
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
        var modeStr string
        if score >= 8 {
            modeStr = "AGGRESSIVE"
            sendCommand("/run/pleiades/taygete.sock", "aggressive")
            sendCommand("/run/pleiades/alcyone.sock", "active")
            reportToPleiadesNexus(fmt.Sprintf("ZOD_MODE_AGGRESSIVE|%d", score))
        } else if score >= 2 {
            modeStr = "PASSIVE"
            sendCommand("/run/pleiades/alcyone.sock", "passive")
            reportToPleiadesNexus(fmt.Sprintf("ZOD_MODE_PASSIVE|%d", score))
        } else {
            modeStr = "NORMAL"
        }
        os.WriteFile("/run/pleiades/atlas_mode", []byte(modeStr), 0644)
        if pleiadesRebirthNeeded && !containmentTriggered {
            sendCommand("/run/pleiades/taygete.sock", "resurrect")
            sendCommand("/run/pleiades/alcyone.sock", "resurrect")
            reportToPleiadesNexus("ZOD_PLEIADES_REBIRTH_SIGNAL")
            pleiadesRebirthNeeded = false
        }
        if containmentTriggered {
            // Reset everything
            atomic.StoreInt64(&threatScore, 0)
            containmentTriggered = false
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
    "os/exec"
    "strings"
    "time"
)

const (
    thrallMaxFloods = 3
    thrallInterval  = 3
    banner          = "\n   ____   ____   _      _   _   _   _   ____   _   _   ____   \n  | __ ) | __ ) | |    | | | | | \\ | | / ___| | \\ | | / ___|  \n  |  _ \\ |  _ \\ | |    | | | | |  \\| | | |  _  |  \\| | | |  _ \n  | |_) || |_) || |___ | |_| | | |\\  | | |_| || |\\  | | |_| | \n  |____/ |____/ |_____| \\___/  |_| \\_|  \\____||_| \\_|  \\____| \n  \n   B   O   B   B   Y       L   O   N   G   !   !   ~\n"
)

func reportToPleiadesNexus(msg string) {
    f, _ := os.OpenFile("/run/pleiades/pleiades-nexus_fifo", os.O_WRONLY|os.O_APPEND|syscall.O_NONBLOCK, 0666)
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
    reportToPleiadesNexus(fmt.Sprintf("THRALL_DEPLOYED|%s", ip))
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
    cat > /etc/atlas/switch_modes.sh << 'SWITCH'
#!/bin/bash
# Tails pleiades-nexus log and sends commands to Alcyone/Taygete sockets
unix_send() { printf '%s\n' "$1" | socat - "UNIX-CONNECT:$2" 2>/dev/null || printf '%s\n' "$1" | nc -U "$2" -w 1 2>/dev/null || true; }
tail -n 0 -F /run/pleiades/pleiades-nexus_fifo 2>/dev/null | while read -r line; do
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
    chmod +x /etc/atlas/switch_modes.sh
}

# ------------------------------------------------------------
# 7. Install systemd service (Atlas pleiades-swarm)
# ------------------------------------------------------------
install_systemd() {
    if ! systemd_usable; then
        pkg_install screen
        screen -dmS atlas_pleiades-swarm /usr/local/bin/atlas_pleiades-swarm
    else
        cat > /etc/systemd/system/atlas-omniversal.service << SERVICE
[Unit]
Description=General Atlas Omniversal Orchestrator
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/atlas_pleiades-swarm
Restart=always
RestartSec=5
LimitNOFILE=$MAX_OPEN_FILES
MemoryMax=$MEMORY_LIMIT
CPUQuota=$CPU_QUOTA

[Install]
WantedBy=multi-user.target
SERVICE
        systemctl daemon-reload
        systemctl enable atlas-omniversal.service
        systemctl start atlas-omniversal.service
    fi
}

build_go_pleiades-swarm() {
    # Build Go pleiades-swarm that runs threat calculator and thrall deployer
    cat > /tmp/atlas_pleiades-swarm.go << 'GO_HIVE'
package main

import (
    "log"
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
            log.Printf("[pleiades-swarm/%s] panic: %v — restarting in 3s", p.Name, r)
            time.Sleep(3 * time.Second)
            go p.run()
        }
    }()
    for {
        cmd := exec.Command(p.Cmd.Args[0], p.Cmd.Args[1:]...)
        if err := cmd.Run(); err != nil {
            log.Printf("[pleiades-swarm/%s] died: %v — respawning in 2s", p.Name, err)
        }
        time.Sleep(2 * time.Second)
    }
}

func main() {
    procs := []*Proc{
        {Name: "threat_calc", Cmd: exec.Command("/usr/local/bin/threat_calc")},
        {Name: "thrall_deployer", Cmd: exec.Command("/usr/local/bin/thrall_deployer")},
        {Name: "switch_modes", Cmd: exec.Command("/etc/atlas/switch_modes.sh")},
        {Name: "forensic_scanner", Cmd: exec.Command("/usr/local/bin/pleiades-forensic-scanner.sh")},
    }
    for _, p := range procs {
        go p.run()
    }
    select {}
}
GO_HIVE
    go build -o /usr/local/bin/atlas_pleiades-swarm /tmp/atlas_pleiades-swarm.go
    chmod +x /usr/local/bin/atlas_pleiades-swarm
    rm -f /tmp/atlas_pleiades-swarm.go
}

# ------------------------------------------------------------
# 8. Background monitors for BGP and thermal threats
# ------------------------------------------------------------
monitor_threats() {
    while true; do
        if bgp_hijack_detected; then
            logger -t atlas "BGP hijack detected – signalling Pleiades Nexus"
            ( echo "BGP_HIJACK" >> ${PLEIADES_RUN_DIR}/pleiades-nexus_fifo & )
fi
        if thermal_anomaly; then
            logger -t atlas "Thermal anomaly detected – signalling Pleiades Nexus"
            ( echo "THERMAL_ANOMALY" >> ${PLEIADES_RUN_DIR}/pleiades-nexus_fifo & )
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
    elif [[ "$ENV" == "bare-metal" ]]; then
        pkg_install golang bc lm-sensors traceroute socat openbsd-netcat
    else
        pkg_install golang bc lm-sensors traceroute socat openbsd-netcat
    fi

    mkdir -p /etc/atlas /run/pleiades
    host_bridge_capability_report "atlas"
    register_pleiades-swarm_capability "atlas" "threat-orchestrator" "threat-scoring,mode-switch,thrall-dispatch,forensic-integration"
    wait_for alcyone 2
    wait_for taygete 2
    build_go_threat_calc
    build_go_thrall
    build_bash_helpers
    build_go_pleiades-swarm
    install_systemd
    monitor_threats &
    SELF="$0"
    cat > /usr/local/sbin/install-atlas-omniversal.sh << INST
#!/bin/bash
exec bash "$SELF"
INST
    chmod +x /usr/local/sbin/install-atlas-omniversal.sh
    signal_ready atlas
    echo "General Atlas Omniversal deployed on $ENV."
}

main

# --- END MAIA EVENT HOOK ---
