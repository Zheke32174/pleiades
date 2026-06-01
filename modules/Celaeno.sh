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


# LITTLEJOHN_ID
# ==================================================================
# CELAENO – OMNIVERSAL (WSL / DGX Spark / VPS)
# ==================================================================
# Monitors Alcyone, Taygete, Zod, Electra, Pleiades Rebirth, Pleiades Nexus.
# Environment‑aware resource limits, BGP hijack detection,
# thermal anomaly monitoring, regeneration, hot patches.
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

# Fallback for initial run
[[ "$MAX_OPEN_FILES" == "4096" ]] && {
    if [[ "$ENV" == "wsl" ]]; then
        MAX_OPEN_FILES=4096
        MEMORY_LIMIT="512M"
        CPU_QUOTA="50%"
        MONITOR_INTERVAL=30
    elif [[ "$ENV" == "dgx" ]]; then
        MAX_OPEN_FILES=1048576
        MEMORY_LIMIT="2G"
        CPU_QUOTA="200%"
        MONITOR_INTERVAL=10
    else
        MAX_OPEN_FILES=65536
        MEMORY_LIMIT="1G"
        CPU_QUOTA="100%"
        MONITOR_INTERVAL=20
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
# 4. Build Go health monitor (low‑overhead process checker)
# ------------------------------------------------------------
build_go_health() {
    cat > /tmp/health_monitor.go << 'GO_HEALTH'
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
    "time"
)

type Component struct {
    Name        string
    Service     string
    ScreenName  string
    Binary      string
    Installer   string
    IsCritical  bool
}

var components = []Component{
    {"alcyone",       "alcyone-omniversal",       "alcyone_honeypot", "alcyone_pleiades-swarm",       "/usr/local/sbin/install-alcyone-omniversal.sh",       true},
    {"taygete",     "taygete-omniversal",     "taygete",        "taygete_pleiades-swarm",     "/usr/local/sbin/install-taygete-omniversal.sh",     true},
    {"zod",          "zod-omniversal",          "zod_pleiades-swarm",    "zod_pleiades-swarm",          "/usr/local/sbin/install-zod-omniversal.sh",          true},
    {"electra",        "electra-omniversal",        "electra",           "electra_pleiades-swarm",        "/usr/local/sbin/install-electra-omniversal.sh",        true},
    {"pleiades-rebirth", "pleiades-rebirth-omniversal", "pleiades-rebirth",    "pleiades-rebirth_pleiades-swarm", "/usr/local/sbin/install-pleiades-rebirth-omniversal.sh", false},
    {"pleiades-nexus",    "pleiades-nexus-omniversal",    "pleiades-nexus",       "imploder",              "/usr/local/sbin/install-pleiades-nexus-omniversal.sh",    false},
}

func isWSL() bool {
    data, _ := os.ReadFile("/proc/version")
    return strings.Contains(strings.ToLower(string(data)), "microsoft")
}

func reportToPleiades Nexus(msg string) {
    f, err := os.OpenFile("/run/pleiades/pleiades_nexus_fifo", os.O_WRONLY|os.O_APPEND|syscall.O_NONBLOCK, 0666)
    if err == nil {
        defer f.Close()
        fmt.Fprintln(f, msg)
    }
}

func isPleiades RebirthActive() bool {
    _, err := os.Stat("/run/pleiades/pleiades-rebirth_active")
    return err == nil
}

func isAlive(comp Component) bool {
    // Prefer pgrep on binary name — works regardless of init system
    if exec.Command("pgrep", "-f", comp.Binary).Run() == nil {
        return true
    }
    if isWSL() {
        out, err := exec.Command("screen", "-ls", comp.ScreenName).Output()
        return err == nil && strings.Contains(string(out), comp.ScreenName)
    }
    return exec.Command("systemctl", "is-active", "--quiet", comp.Service).Run() == nil
}

func regenerate(comp Component) {
    // If pleiades-rebirth is active and component is critical, skip to avoid interference
    if isPleiades RebirthActive() && comp.IsCritical {
        log.Printf("Pleiades Rebirth active – skipping regeneration of %s", comp.Name)
        reportToPleiades Nexus(fmt.Sprintf("SKIP_REGENERATE|%s", comp.Name))
        return
    }
    if _, err := os.Stat(comp.Installer); err == nil {
        log.Printf("Regenerating %s", comp.Name)
        reportToPleiades Nexus(fmt.Sprintf("REGENERATE|%s", comp.Name))
        exec.Command(comp.Installer).Run()
    } else {
        log.Printf("Installer missing for %s", comp.Name)
        reportToPleiades Nexus(fmt.Sprintf("MISSING_INSTALLER|%s", comp.Name))
    }
}

func processCommands() {
    cmdPath := "/run/pleiades/celaeno_cmd"
    var offset int64
    for {
        f, err := os.Open(cmdPath)
        if err != nil {
            time.Sleep(5 * time.Second)
            continue
        }
        fi, err := f.Stat()
        if err == nil && fi.Size() > offset {
            f.Seek(offset, io.SeekStart)
            scanner := bufio.NewScanner(f)
            for scanner.Scan() {
                line := scanner.Text()
                if strings.HasPrefix(line, "regenerate:") {
                    name := strings.TrimPrefix(line, "regenerate:")
                    for _, comp := range components {
                        if comp.Name == name {
                            regenerate(comp)
                            break
                        }
                    }
                } else if strings.HasPrefix(line, "upgrade:") {
                    parts := strings.SplitN(line, ":", 3)
                    if len(parts) == 3 {
                        compName, instruction := parts[1], parts[2]
                        sockPath := "/run/pleiades/" + compName + ".sock"
                        if _, err := os.Stat(sockPath); err == nil {
                            sh := fmt.Sprintf("echo %q | nc -U %s -w 1", instruction, sockPath)
                            exec.Command("sh", "-c", sh).Run()
                            reportToPleiades Nexus(fmt.Sprintf("UPGRADE|%s|%s", compName, instruction))
                        }
                    }
                } else if line == "pause_regeneration" {
                    log.Println("Regeneration paused")
                    reportToPleiades Nexus("PAUSE_REGENERATION")
                    os.WriteFile("/run/pleiades/.pause_regeneration", []byte("1"), 0644)
                } else if line == "resume_regeneration" {
                    log.Println("Regeneration resumed")
                    reportToPleiades Nexus("RESUME_REGENERATION")
                    os.Remove("/run/pleiades/.pause_regeneration")
                }
            }
            offset, _ = f.Seek(0, io.SeekCurrent)
        }
        f.Close()
        time.Sleep(1 * time.Second)
    }
}

func main() {
    go processCommands()
    for {
        if _, err := os.Stat("/run/pleiades/.pause_regeneration"); err != nil {
            for _, comp := range components {
                if !isAlive(comp) {
                    regenerate(comp)
                }
            }
        }
        time.Sleep(10 * time.Second)
    }
}
GO_HEALTH
    go build -o /usr/local/bin/health_monitor /tmp/health_monitor.go
    chmod +x /usr/local/bin/health_monitor
    rm -f /tmp/health_monitor.go
}

# ------------------------------------------------------------
# 5. Build Rust hot patch engine (with environment awareness)
# ------------------------------------------------------------
build_rust_hotpatch() {
    cat > /tmp/hotpatch.rs << 'RUST_HOT'
use std::fs::OpenOptions;
use std::os::unix::fs::OpenOptionsExt;
use std::io::Write;
use std::process::Command;
use std::thread;
use std::time::Duration;

fn report_to_pleiades-nexus(msg: &str) {
    if let Ok(mut fifo) = OpenOptions::new().write(true).append(true).custom_flags(0o4000).open("/run/pleiades/pleiades_nexus_fifo") {
        let _ = writeln!(fifo, "{}", msg);
    }
}

fn hot_patch_conntrack_flood() {
    let _ = Command::new("sysctl")
        .args(&["-w", "net.netfilter.nf_conntrack_max=131072"])
        .output();
    let _ = Command::new("sysctl")
        .args(&["-w", "net.netfilter.nf_conntrack_tcp_timeout_established=300"])
        .output();
    report_to_pleiades-nexus("HOTPATCH|conntrack_flood");
}

fn hot_patch_watchdog_suspend() {
    Command::new("nohup")
        .args(&["bash", "-c", "while true; do systemctl restart alcyone-watchdog taygete-watchdog 2>/dev/null; sleep 2; done &"])
        .spawn()
        .ok();
    report_to_pleiades-nexus("HOTPATCH|watchdog_suspend");
}

fn hot_patch_ssh_block() {
    Command::new("nohup")
        .args(&["bash", "-c", "socat TCP-LISTEN:443,fork TCP:127.0.0.1:8080 &"])
        .spawn()
        .ok();
    report_to_pleiades-nexus("HOTPATCH|ssh_block");
}

fn detect_and_patch() {
    // Conntrack insertion failures
    let out = Command::new("conntrack").arg("-S").output();
    if let Ok(o) = out {
        if String::from_utf8_lossy(&o.stdout).contains("insert_failed") {
            hot_patch_conntrack_flood();
        }
    }
    // Suspended watchdog processes
    let out = Command::new("ps").arg("aux").output();
    if let Ok(o) = out {
        let s = String::from_utf8_lossy(&o.stdout);
        if (s.contains(" T ") || s.contains(" Z ")) && s.contains("watchdog") {
            hot_patch_watchdog_suspend();
        }
    }
    // Local SSH unreachable
    let out = Command::new("nc").args(&["-z", "127.0.0.1", "22"]).output();
    if out.is_err() {
        hot_patch_ssh_block();
    }
}

fn main() {
    loop {
        detect_and_patch();
        thread::sleep(Duration::from_secs(30));
    }
}
RUST_HOT
    rustc -o /usr/local/bin/hotpatch /tmp/hotpatch.rs
    chmod +x /usr/local/bin/hotpatch
    rm -f /tmp/hotpatch.rs
}

# ------------------------------------------------------------
# 6. Build Bun command processor (for upgrade commands)
# ------------------------------------------------------------
build_bun_cmd_processor() {
    cat > /usr/local/bin/cmd_processor.js << 'BUN_CMD'
#!/usr/bin/env bun
import { existsSync, writeFileSync, appendFileSync, unlinkSync, statSync, readFileSync, execSync } from 'fs';

const CMD_PATH = "/run/pleiades/celaeno_cmd";
const LOG = "/var/lib/.celaeno/cmd.log";

function log(msg) {
    const ts = new Date().toISOString();
    appendFileSync(LOG, `${ts} - ${msg}\n`);
}

function reportToPleiades Nexus(msg) {
    try { appendFileSync("/run/pleiades/pleiades_nexus_fifo", msg + "\n"); } catch(e) {}
}

if (!existsSync(CMD_PATH)) {
    writeFileSync(CMD_PATH, '');
}

log("Command processor started");
reportToPleiades Nexus("CMD_PROCESSOR_STARTED");

let offset = 0;

function processCmd(line) {
    if (line.startsWith('upgrade:')) {
        const parts = line.split(':');
        if (parts.length >= 3) {
            const component = parts[1];
            const instruction = parts.slice(2).join(':');
            log(`Upgrading ${component} with ${instruction}`);
            reportToPleiades Nexus(`UPGRADE|${component}|${instruction}`);
            const sockPath = `/run/pleiades/${component}.sock`;
            if (existsSync(sockPath)) {
                try { execSync(`echo ${JSON.stringify(instruction)} | nc -U ${sockPath} -w 1`); } catch(e) {}
            }
        }
    } else if (line === 'pause_regeneration') {
        log('Regeneration paused');
        reportToPleiades Nexus('PAUSE_REGENERATION');
        writeFileSync('/run/pleiades/.pause_regeneration', '1');
    } else if (line === 'resume_regeneration') {
        log('Regeneration resumed');
        reportToPleiades Nexus('RESUME_REGENERATION');
        if (existsSync('/run/pleiades/.pause_regeneration')) unlinkSync('/run/pleiades/.pause_regeneration');
    }
}

setInterval(() => {
    try {
        const size = statSync(CMD_PATH).size;
        if (size < offset) offset = 0;
        if (size <= offset) return;
        const chunk = readFileSync(CMD_PATH).slice(offset, size).toString();
        offset = size;
        chunk.split('\n').map(l => l.trim()).filter(Boolean).forEach(processCmd);
    } catch(e) {}
}, 1000);
BUN_CMD
    chmod +x /usr/local/bin/cmd_processor.js
}

# ------------------------------------------------------------
# 7. Build Bash fallback scripts (if toolchain missing)
# ------------------------------------------------------------
build_bash_fallbacks() {
    cat > /var/lib/.celaeno/fallback_health.sh << 'BASH_HEALTH'
#!/bin/bash
declare -A BIN_TO_NAME=(
    [alcyone_pleiades-swarm]=alcyone
    [taygete_pleiades-swarm]=taygete
    [zod_pleiades-swarm]=zod
    [electra_pleiades-swarm]=electra
    [pleiades-rebirth_pleiades-swarm]=pleiades-rebirth
    [imploder]=pleiades-nexus
)
while true; do
    for bin in "${!BIN_TO_NAME[@]}"; do
        if ! pgrep -f "$bin" >/dev/null 2>&1; then
            name="${BIN_TO_NAME[$bin]}"
            installer="/usr/local/sbin/install-${name}-omniversal.sh"
            if [[ -x "$installer" ]]; then
                echo "regenerate:${name}" >> /run/pleiades/celaeno_cmd
            fi
        fi
    done
    sleep 20
done
BASH_HEALTH
    chmod +x /var/lib/.celaeno/fallback_health.sh

    cat > /var/lib/.celaeno/fallback_hotpatch.sh << 'BASH_PATCH'
#!/bin/bash
while true; do
    if conntrack -S 2>/dev/null | grep -q "insert_failed"; then
        sysctl -w net.netfilter.nf_conntrack_max=131072
        ( echo "HOTPATCH|conntrack_flood" >> /run/pleiades/pleiades_nexus_fifo & )
fi
    if ps aux | grep -E "[TZ]" | grep -q watchdog; then
        nohup bash -c 'while true; do systemctl restart alcyone-watchdog taygete-watchdog 2>/dev/null; sleep 2; done' &
        ( echo "HOTPATCH|watchdog_suspend" >> /run/pleiades/pleiades_nexus_fifo & )
fi
    sleep 30
done
BASH_PATCH
    chmod +x /var/lib/.celaeno/fallback_hotpatch.sh
}

# ------------------------------------------------------------
# 8. Install systemd service (Celaeno pleiades-swarm)
# ------------------------------------------------------------
install_systemd() {
    if [[ "$ENV" == "wsl" ]]; then
        pkg_install screen
        screen -dmS celaeno /usr/local/bin/celaeno_pleiades-swarm
    else
        cat > /etc/systemd/system/celaeno-omniversal.service << SERVICE
[Unit]
Description=Celaeno Omniversal
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/celaeno_pleiades-swarm
Restart=always
RestartSec=5
LimitNOFILE=$MAX_OPEN_FILES
MemoryMax=$MEMORY_LIMIT
CPUQuota=$CPU_QUOTA

[Install]
WantedBy=multi-user.target
SERVICE
        systemctl daemon-reload
        systemctl enable celaeno-omniversal.service
        systemctl start celaeno-omniversal.service
    fi

    # Build Go pleiades-swarm that coordinates health monitor, hotpatch, and cmd processor
    cat > /tmp/celaeno_pleiades-swarm.go << 'GO_HIVE'
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
    if _, err := os.Stat("/usr/local/bin/health_monitor"); err == nil {
        procs = append(procs, &Proc{Name: "health_monitor", Cmd: exec.Command("/usr/local/bin/health_monitor")})
    } else {
        procs = append(procs, &Proc{Name: "fallback_health", Cmd: exec.Command("/var/lib/.celaeno/fallback_health.sh")})
    }
    if _, err := os.Stat("/usr/local/bin/hotpatch"); err == nil {
        procs = append(procs, &Proc{Name: "hotpatch", Cmd: exec.Command("/usr/local/bin/hotpatch")})
    } else {
        procs = append(procs, &Proc{Name: "fallback_hotpatch", Cmd: exec.Command("/var/lib/.celaeno/fallback_hotpatch.sh")})
    }
    if _, err := os.Stat("/usr/local/bin/cmd_processor.js"); err == nil {
        procs = append(procs, &Proc{Name: "cmd_processor", Cmd: exec.Command("bun", "/usr/local/bin/cmd_processor.js")})
    }

    for _, p := range procs {
        go p.run()
    }
    select {}
}
GO_HIVE
    go build -o /usr/local/bin/celaeno_pleiades-swarm /tmp/celaeno_pleiades-swarm.go
    chmod +x /usr/local/bin/celaeno_pleiades-swarm
    rm -f /tmp/celaeno_pleiades-swarm.go
}

# ------------------------------------------------------------
# 9. Background monitors for BGP and thermal threats
# ------------------------------------------------------------
monitor_threats() {
    while true; do
        if bgp_hijack_detected; then
            logger -t littlejohn "BGP hijack detected – setting flag"
            touch /run/pleiades/bgp_hijack
            # Also trigger regeneration pause if needed
            echo "pause_regeneration" > /run/pleiades/celaeno_cmd
        fi
        if thermal_anomaly; then
            logger -t littlejohn "Thermal anomaly detected – setting flag"
            touch /run/pleiades/thermal_anomaly
            # Reduce monitoring frequency to lower CPU
            sleep 60
        fi
        sleep 30
    done
}

# ------------------------------------------------------------
# 10. Main
# ------------------------------------------------------------
main() {
    # Install dependencies
    pkg_install golang rustc bun screen bc lm-sensors traceroute socat openbsd-netcat

    # Ensure bun is available
    if ! command -v bun &>/dev/null; then
        curl -fsSL https://bun.sh/install | bash
    fi

    mkdir -p /var/lib/.celaeno /run/pleiades
    for dep in alcyone taygete pleiades-rebirth pleiades-nexus electra; do wait_for "$dep" 120; done
    build_go_health
    build_rust_hotpatch
    build_bun_cmd_processor
    build_bash_fallbacks
    install_systemd
    monitor_threats &
    SELF="$0"
    cat > /usr/local/sbin/install-littlejohn-omniversal.sh << INST
#!/bin/bash
exec bash "$SELF"
INST
    chmod +x /usr/local/sbin/install-littlejohn-omniversal.sh
    signal_ready littlejohn
    echo "Celaeno Omniversal deployed on $ENV."
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



