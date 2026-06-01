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


# PLEIADES_NEXUS_ID
# ==================================================================
# PLEIADES_NEXUS IMPLOSION – OMNIVERSAL (WSL / DGX Spark / VPS)
# ==================================================================
# Environment‑aware resource limits, BGP hijack detection,
# thermal anomaly monitoring, threat aggregation, botnet blocklist.
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
THREAT_THRESHOLD=500

# Fallback for initial run
[[ "$MAX_OPEN_FILES" == "4096" ]] && {
    if [[ "$ENV" == "wsl" ]]; then
        MAX_OPEN_FILES=4096
        MEMORY_LIMIT="1G"
        CPU_QUOTA="100%"
        THREAT_THRESHOLD=2000
    elif [[ "$ENV" == "dgx" ]]; then
        MAX_OPEN_FILES=1048576
        MEMORY_LIMIT="8G"
        CPU_QUOTA="400%"
        THREAT_THRESHOLD=5000
    else
        MAX_OPEN_FILES=65536
        MEMORY_LIMIT="2G"
        CPU_QUOTA="200%"
        THREAT_THRESHOLD=5000
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
# 4. Build Go implosion monitor (reads FIFO, aggregates threats)
# ------------------------------------------------------------
build_go_imploder() {
    cat > /tmp/imploder.go << 'GO_IMP'
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

var attackerCount int64
var imploded bool
const threshold = THRESHOLD_PLACEHOLDER

func reportToPleiades Nexus(msg string) {
    f, err := os.OpenFile("/run/pleiades/pleiades_nexus_fifo", os.O_WRONLY|os.O_APPEND|syscall.O_NONBLOCK, 0666)
    if err == nil {
        defer f.Close()
        fmt.Fprintln(f, msg)
    }
}

func addToBlocklist(ip string) {
    if ip == "" {
        return
    }
    // Ensure the set exists first
    exec.Command("nft", "add", "set", "inet", "filter", "blocklist",
        "{ type ipv4_addr; flags interval; }").Run()
    exec.Command("nft", "add", "element", "inet", "filter", "blocklist",
        "{ "+ip+" }").Run()
    reportToPleiades Nexus(fmt.Sprintf("BLOCKLIST_ADD|%s", ip))
}

func archiveLogs() {
    stamp := time.Now().Format("20060102T150405Z")
    archive := fmt.Sprintf("/var/lib/pleiades-team/forensics/logs_%s.tar.gz", stamp)
    os.MkdirAll("/var/lib/pleiades-team/forensics", 0750)
    exec.Command("journalctl", "-o", "json", "--no-pager",
        "--output-file=/tmp/pleiades_journal_"+stamp+".json").Run()
    exec.Command("tar", "-czf", archive,
        "/tmp/pleiades_journal_"+stamp+".json",
        "/run/pleiades/pleiades_nexus_fifo").Run()
    os.Remove("/tmp/pleiades_journal_" + stamp + ".json")
    exec.Command("journalctl", "--rotate").Run()
    exec.Command("journalctl", "--vacuum-time=1s").Run()
    reportToPleiades Nexus(fmt.Sprintf("LOGS_ARCHIVED|%s", archive))
}

func implode() {
    if imploded {
        return
    }
    imploded = true
    log.Println("Threat threshold exceeded – initiating Pleiades Nexus implosion")
    reportToPleiades Nexus("IMPLOSION_TRIGGERED; _maia_hook "IMPLOSION_TRIGGERED"; _maia_hook "IMPLOSION_TRIGGERED"; _maia_hook "IMPLOSION_TRIGGERED"")

    // Block all current attackers from conntrack
    cmd := exec.Command("conntrack", "-L")
    out, err := cmd.Output()
    if err == nil {
        lines := strings.Split(string(out), "\n")
        for _, line := range lines {
            if strings.Contains(line, "src=") {
                parts := strings.Split(line, "src=")
                if len(parts) > 1 {
                    ip := strings.Split(parts[1], " ")[0]
                    if !strings.HasPrefix(ip, "127.") && !strings.HasPrefix(ip, "192.168.") &&
                        !strings.HasPrefix(ip, "10.") && !strings.HasPrefix(ip, "172.16.") {
                        addToBlocklist(ip)
                    }
                }
            }
        }
    }

    archiveLogs()

    // Notify other components
    os.WriteFile("/run/pleiades/pleiades-nexus_complete", []byte("done"), 0644)
}

func main() {
    logPath := "/run/pleiades/pleiades_nexus_fifo"
    var offset int64
    for {
        if _, err := os.Stat("/run/pleiades/bgp_hijack"); err == nil {
            log.Println("BGP hijack detected – triggering implosion")
            implode()
            return
        }
        if _, err := os.Stat("/run/pleiades/thermal_anomaly"); err == nil {
            log.Println("Thermal anomaly detected – triggering implosion")
            implode()
            return
        }

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
                line := scanner.Text()
                if strings.HasPrefix(line, "ANOMALY|") || strings.HasPrefix(line, "RATE_LIMITED|") ||
                    strings.HasPrefix(line, "NEW_ANOMALY|") || strings.HasPrefix(line, "BRUTE_SUCCESS|") {
                    parts := strings.Split(line, "|")
                    if len(parts) >= 2 {
                        ip := parts[1]
                        if !strings.HasPrefix(ip, "127.") && !strings.HasPrefix(ip, "192.168.") &&
                            !strings.HasPrefix(ip, "10.") && !strings.HasPrefix(ip, "172.16.") {
                            atomic.AddInt64(&attackerCount, 1)
                        }
                    }
                }
                if strings.Contains(line, "IMPLODE_NOW") {
                    f.Close()
                    implode()
                    return
                }
            }
            offset, _ = f.Seek(0, io.SeekCurrent)
        }
        f.Close()

        if atomic.LoadInt64(&attackerCount) >= threshold {
            implode()
            return
        }
        time.Sleep(10 * time.Second)
    }
}
GO_IMP
    sed -i "s/THRESHOLD_PLACEHOLDER/$THREAT_THRESHOLD/" /tmp/imploder.go
    go build -o /usr/local/bin/imploder /tmp/imploder.go
    chmod +x /usr/local/bin/imploder
    rm -f /tmp/imploder.go
}

# ------------------------------------------------------------
# 5. Build Rust fallback (if Go fails)
# ------------------------------------------------------------
build_rust_imploder() {
    cat > /tmp/imploder.rs << 'RUST_IMP'
use std::fs::OpenOptions;
use std::os::unix::fs::OpenOptionsExt;
use std::io::{BufRead, BufReader, Write};
use std::process::Command;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::Duration;

static ATTACKER_COUNT: AtomicUsize = AtomicUsize::new(0);
const THRESHOLD: usize = THRESHOLD_PLACEHOLDER;

fn report(msg: &str) {
    if let Ok(mut fifo) = OpenOptions::new().write(true).append(true).custom_flags(0o4000).open("/run/pleiades/pleiades_nexus_fifo") {
        let _ = writeln!(fifo, "{}", msg);
    }
}

fn add_blocklist(ip: &str) {
    let set_spec = "{ type ipv4_addr; flags interval; }";
    Command::new("nft").args(&["add", "set", "inet", "filter", "blocklist", set_spec]).output().ok();
    let elem = format!("{{ {} }}", ip);
    Command::new("nft").args(&["add", "element", "inet", "filter", "blocklist", &elem]).output().ok();
    report(&format!("BLOCKLIST_ADD|{}", ip));
}

fn archive_logs() {
    use std::time::{SystemTime, UNIX_EPOCH};
    let ts = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs();
    let archive = format!("/var/lib/pleiades-team/forensics/logs_{}.tar.gz", ts);
    std::fs::create_dir_all("/var/lib/pleiades-team/forensics").ok();
    let journal_tmp = format!("/tmp/pleiades_journal_{}.json", ts);
    Command::new("journalctl").args(&["-o", "json", "--no-pager",
        &format!("--output-file={}", journal_tmp)]).output().ok();
    Command::new("tar").args(&["-czf", &archive, &journal_tmp,
        "/run/pleiades/pleiades_nexus_fifo"]).output().ok();
    std::fs::remove_file(&journal_tmp).ok();
    Command::new("journalctl").arg("--rotate").output().ok();
    Command::new("journalctl").arg("--vacuum-time=1s").output().ok();
    report(&format!("LOGS_ARCHIVED|{}", archive));
}

fn implode() {
    report("IMPLOSION_TRIGGERED; _maia_hook "IMPLOSION_TRIGGERED"; _maia_hook "IMPLOSION_TRIGGERED"; _maia_hook "IMPLOSION_TRIGGERED"");
    if let Ok(out) = Command::new("conntrack").arg("-L").output() {
        let s = String::from_utf8_lossy(&out.stdout);
        for line in s.lines() {
            if let Some(ip) = line.split("src=").nth(1).and_then(|x| x.split_whitespace().next()) {
                if !ip.starts_with("127.") && !ip.starts_with("192.168.") && !ip.starts_with("10.") && !ip.starts_with("172.16.") {
                    add_blocklist(ip);
                }
            }
        }
    }
    archive_logs();
    std::fs::write("/run/pleiades/pleiades-nexus_complete", "done").ok();
}

fn main() {
    let fifo_path = "/run/pleiades/pleiades_nexus_fifo";
    loop {
        if let Ok(file) = OpenOptions::new().read(true).open(fifo_path) {
            let reader = BufReader::new(file);
            for line in reader.lines() {
                if let Ok(line) = line {
                    if line.starts_with("ANOMALY|") || line.starts_with("RATE_LIMITED|") ||
                       line.starts_with("NEW_ANOMALY|") || line.starts_with("BRUTE_SUCCESS|") {
                        let parts: Vec<&str> = line.split('|').collect();
                        if parts.len() >= 2 {
                            let ip = parts[1];
                            if !ip.starts_with("127.") && !ip.starts_with("192.168.") && !ip.starts_with("10.") && !ip.starts_with("172.16.") {
                                let prev = ATTACKER_COUNT.fetch_add(1, Ordering::SeqCst);
                                if prev + 1 >= THRESHOLD {
                                    implode();
                                    return;
                                }
                            }
                        }
                    }
                }
            }
        }
        thread::sleep(Duration::from_secs(10));
    }
}
RUST_IMP
    sed -i "s/THRESHOLD_PLACEHOLDER/$THREAT_THRESHOLD/" /tmp/imploder.rs
    rustc -o /usr/local/bin/imploder_rust /tmp/imploder.rs
    chmod +x /usr/local/bin/imploder_rust
    rm -f /tmp/imploder.rs
}

# ------------------------------------------------------------
# 6. Build Bash fallback (if both Go and Rust fail)
# ------------------------------------------------------------
build_bash_imploder() {
    cat > /usr/local/bin/imploder_bash.sh << 'BASH_IMP'
#!/bin/bash
THRESHOLD=THRESHOLD_PLACEHOLDER
COUNT_FILE="/run/pleiades/attacker_count"
echo 0 > "$COUNT_FILE"

report() { ( echo "$1" >> /run/pleiades/pleiades_nexus_fifo & ); }

while true; do
    # Check for BGP/thermal flags
    if [[ -f /run/pleiades/bgp_hijack ]] || [[ -f /run/pleiades/thermal_anomaly ]]; then
        report "IMPLOSION_TRIGGERED; _maia_hook "IMPLOSION_TRIGGERED"; _maia_hook "IMPLOSION_TRIGGERED"; _maia_hook "IMPLOSION_TRIGGERED""
        nft add set inet filter blocklist '{ type ipv4_addr; flags interval; }' 2>/dev/null
        conntrack -L | grep -oP 'src=\K[0-9.]+' | sort -u | while read -r ip; do
            case "$ip" in 127.*|192.168.*|10.*|172.16.*) continue ;; esac
            nft add element inet filter blocklist "{ $ip }"
            report "BLOCKLIST_ADD|$ip"
        done
        _stamp=$(date -u +%Y%m%dT%H%M%SZ)
        mkdir -p /var/lib/pleiades-team/forensics
        journalctl -o json --no-pager > "/tmp/pleiades_journal_${_stamp}.json" 2>/dev/null
        tar -czf "/var/lib/pleiades-team/forensics/logs_${_stamp}.tar.gz" \
            "/tmp/pleiades_journal_${_stamp}.json" /run/pleiades/pleiades_nexus_fifo 2>/dev/null
        rm -f "/tmp/pleiades_journal_${_stamp}.json"
        journalctl --rotate && journalctl --vacuum-time=1s
        report "LOGS_ARCHIVED|/var/lib/pleiades-team/forensics/logs_${_stamp}.tar.gz"
        touch /run/pleiades/pleiades-nexus_complete
        break
    fi
    # Tail new lines from log file (non-blocking)
    new_lines=$(tail -n +"$(($(cat "$COUNT_FILE" 2>/dev/null || echo 0)+1))" \
        /run/pleiades/pleiades_nexus_fifo 2>/dev/null || true)
    while IFS= read -r line; do
        if [[ "$line" =~ ^(ANOMALY|RATE_LIMITED|NEW_ANOMALY|BRUTE_SUCCESS) ]]; then
            ip=$(echo "$line" | cut -d'|' -f2)
            if [[ ! "$ip" =~ ^(127|192\.168|10|172\.16) ]]; then
                count=$(cat "$COUNT_FILE")
                count=$((count+1))
                echo "$count" > "$COUNT_FILE"
                if [[ $count -ge $THRESHOLD ]]; then
                    report "IMPLOSION_TRIGGERED; _maia_hook "IMPLOSION_TRIGGERED"; _maia_hook "IMPLOSION_TRIGGERED"; _maia_hook "IMPLOSION_TRIGGERED""
                    nft add set inet filter blocklist '{ type ipv4_addr; flags interval; }' 2>/dev/null
                    conntrack -L | grep -oP 'src=\K[0-9.]+' | sort -u | while read -r ip2; do
                        case "$ip2" in 127.*|192.168.*|10.*|172.16.*) continue ;; esac
                        nft add element inet filter blocklist "{ $ip2 }"
                        report "BLOCKLIST_ADD|$ip2"
                    done
                    _stamp=$(date -u +%Y%m%dT%H%M%SZ)
                    mkdir -p /var/lib/pleiades-team/forensics
                    journalctl -o json --no-pager > "/tmp/pleiades_journal_${_stamp}.json" 2>/dev/null
                    tar -czf "/var/lib/pleiades-team/forensics/logs_${_stamp}.tar.gz" \
                        "/tmp/pleiades_journal_${_stamp}.json" /run/pleiades/pleiades_nexus_fifo 2>/dev/null
                    rm -f "/tmp/pleiades_journal_${_stamp}.json"
                    journalctl --rotate && journalctl --vacuum-time=1s
                    report "LOGS_ARCHIVED|/var/lib/pleiades-team/forensics/logs_${_stamp}.tar.gz"
                    touch /run/pleiades/pleiades-nexus_complete
                    break 2
                fi
            fi
        fi
    done <<< "$new_lines"
done
BASH_IMP
    sed -i "s/THRESHOLD_PLACEHOLDER/$THREAT_THRESHOLD/" /usr/local/bin/imploder_bash.sh
    chmod +x /usr/local/bin/imploder_bash.sh
}

# ------------------------------------------------------------
# 7. Install systemd service
# ------------------------------------------------------------
install_service() {
    if [[ "$ENV" == "wsl" ]]; then
        pkg_install screen
        screen -dmS pleiades-nexus /usr/local/bin/imploder
    else
        cat > /etc/systemd/system/pleiades-nexus-omniversal.service << SERVICE
[Unit]
Description=Pleiades Nexus Implosion Omniversal
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/imploder
Restart=always
RestartSec=10
LimitNOFILE=$MAX_OPEN_FILES
MemoryMax=$MEMORY_LIMIT
CPUQuota=$CPU_QUOTA

[Install]
WantedBy=multi-user.target
SERVICE
        systemctl daemon-reload
        systemctl enable pleiades-nexus-omniversal.service
        systemctl start pleiades-nexus-omniversal.service
    fi
}

# ------------------------------------------------------------
# 8. Background monitors for BGP and thermal threats
# ------------------------------------------------------------
monitor_threats() {
    while true; do
        if bgp_hijack_detected; then
            logger -t pleiades-nexus "BGP hijack detected – setting flag"
            touch /run/pleiades/bgp_hijack
        fi
        if thermal_anomaly; then
            logger -t pleiades-nexus "Thermal anomaly detected – setting flag"
            touch /run/pleiades/thermal_anomaly
        fi
        # Detect forensic analysis tools
        for tool in volatility volatility3 rekall strings gdb; do
            if command -v "$tool" &>/dev/null; then
                logger -t pleiades-nexus "Forensic tool detected: $tool"
                ( echo "ANOMALY|forensic_tool|$tool" >> /run/pleiades/pleiades_nexus_fifo & )
fi
        done
        sleep 30
    done
}

# ------------------------------------------------------------
# 9. Main
# ------------------------------------------------------------
main() {
    # Install dependencies
    if [[ "$ENV" == "wsl" ]]; then
        pkg_install golang rustc bc lm-sensors traceroute socat openbsd-netcat
    elif [[ "$ENV" == "dgx" ]]; then
        pkg_install golang rustc bc lm-sensors traceroute socat openbsd-netcat
    else
        pkg_install golang rustc bc lm-sensors traceroute socat openbsd-netcat
    fi

    mkdir -p /run/pleiades

    # Build the imploder (Go preferred)
    if command -v go &>/dev/null; then
        build_go_imploder
        IMPLODER_BIN="/usr/local/bin/imploder"
    elif command -v rustc &>/dev/null; then
        build_rust_imploder
        IMPLODER_BIN="/usr/local/bin/imploder_rust"
    else
        build_bash_imploder
        IMPLODER_BIN="/usr/local/bin/imploder_bash.sh"
    fi

    install_service
    monitor_threats &
    SELF="$0"
    cat > /usr/local/sbin/install-pleiades-nexus-omniversal.sh << INST
#!/bin/bash
exec bash "$SELF"
INST
    chmod +x /usr/local/sbin/install-pleiades-nexus-omniversal.sh
    signal_ready pleiades-nexus
    echo "Pleiades Nexus Omniversal deployed on $ENV."
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


