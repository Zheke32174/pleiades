#!/usr/bin/env bash
set -uo pipefail

# Source shared library
source /usr/local/lib/pleiades-common.sh 2>/dev/null || source "$(dirname "$0")/pleiades-common.sh"
# Source configuration
source /etc/purple/pleiades.conf 2>/dev/null || source "$(dirname "$0")/../etc/purple/pleiades.conf"

# ALCYONE_ID
# ==================================================================
# ALCYONE – OMNIVERSAL (WSL / bare metal / VPS)
# ==================================================================
# Detects environment, adjusts resource limits, adds BGP hijack
# detection via looking glass, and thermal anomaly monitoring.
# ==================================================================

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "Must be run as root." >&2; exit 1
fi

# ------------------------------------------------------------
# 0. Environment detection
# ------------------------------------------------------------
ENV="unknown"
IS_WSL=false
IS_BARE_METAL=false
IS_VPS=false

if grep -qi microsoft /proc/version 2>/dev/null; then
    ENV="wsl"
    IS_WSL=true
elif [[ -d /sys/firmware/efi ]] && ! systemd-detect-virt --container -q 2>/dev/null && ! systemd-detect-virt --vm -q 2>/dev/null; then
    ENV="bare_metal"
    IS_BARE_METAL=true
else
    # Detect VPS by presence of virtio or hypervisor
    if dmidecode -s system-manufacturer 2>/dev/null | grep -qiE "kvm|xen|vmware|virtualbox"; then
        ENV="vps"
        IS_VPS=true
    else
        ENV="bare_metal"
        IS_BARE_METAL=true
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
        MEMORY_LIMIT="1G"
        CPU_QUOTA="100%"
    elif [[ "$ENV" == "bare_metal" ]]; then
        MAX_OPEN_FILES=1048576
        MEMORY_LIMIT="8G"
        CPU_QUOTA="800%"
    else
        MAX_OPEN_FILES=65536
        MEMORY_LIMIT="2G"
        CPU_QUOTA="200%"
    fi
}

# ------------------------------------------------------------
# 2. Anti‑BGP hijack detection (looking glass)
# ------------------------------------------------------------
# (handled by pleiades-common.sh)
# ------------------------------------------------------------
# 3. Thermal/side‑channel anomaly detection
# ------------------------------------------------------------
# (handled by pleiades-common.sh)
# ------------------------------------------------------------
# 4. Build Go honeypot (multi-port, stdlib only)
# ------------------------------------------------------------
build_go_honeypot() {
    cat > /tmp/alcyone_honeypot.go << 'GO_HONEY'
package main

import (
    "bufio"
    "fmt"
    "net"
    "os"
    "syscall"
    "strings"
    "time"
)

func reportToPleiadesNexus(msg string) {
    f, err := os.OpenFile("/run/pleiades/pleiades-nexus_fifo", os.O_WRONLY|os.O_APPEND|syscall.O_NONBLOCK|os.O_CREATE, 0666)
    if err == nil {
        defer f.Close()
        fmt.Fprintln(f, msg)
    }
}

func setAttackerIP(ip string) {
    f, err := os.OpenFile("/run/pleiades/attacker_ips", os.O_WRONLY|os.O_APPEND|syscall.O_NONBLOCK|os.O_CREATE, 0644)
    if err == nil {
        fmt.Fprintln(f, ip)
        f.Close()
    }
}

func isPrivate(ip string) bool {
    for _, pfx := range []string{"127.", "10.", "192.168.", "172.16.", "172.17.", "172.18.",
        "172.19.", "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
        "172.25.", "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31."} {
        if strings.HasPrefix(ip, pfx) {
            return true
        }
    }
    return false
}

func handleConn(conn net.Conn, port string) {
    defer conn.Close()
    conn.SetDeadline(time.Now().Add(30 * time.Second))
    remoteIP := conn.RemoteAddr().(*net.TCPAddr).IP.String()
    if isPrivate(remoteIP) {
        return
    }
    var banner string
    switch port {
    case "22", "2222":
        banner = "SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.7\r\n"
    case "8080":
        banner = "HTTP/1.1 200 OK\r\nServer: Apache/2.4.54\r\nContent-Length: 0\r\n\r\n"
    case "8443":
        banner = "HTTP/1.1 400 Bad Request\r\nServer: nginx/1.24.0\r\nContent-Length: 0\r\n\r\n"
    }
    if banner != "" {
        conn.Write([]byte(banner))
    }
    scanner := bufio.NewScanner(conn)
    var lines []string
    for scanner.Scan() {
        lines = append(lines, scanner.Text())
        if len(lines) >= 3 {
            break
        }
    }
    event := fmt.Sprintf("ANOMALY|%s|port=%s", remoteIP, port)
    if len(lines) > 0 {
        event += "|data=" + strings.Join(lines[:min(2, len(lines))], ";")
    }
    reportToPleiadesNexus(event)
    setAttackerIP(remoteIP)
}

func min(a, b int) int {
    if a < b {
        return a
    }
    return b
}

func listenOn(port string) {
    ln, err := net.Listen("tcp", ":"+port)
    if err != nil {
        return
    }
    defer ln.Close()
    for {
        conn, err := ln.Accept()
        if err != nil {
            time.Sleep(time.Second)
            continue
        }
        go handleConn(conn, port)
    }
}

func main() {
    sshPort := os.Getenv("HONEYPOT_SSH_PORT")
    if sshPort == "" {
        sshPort = "2224"
    }
    for _, p := range []string{sshPort, "8080", "8443"} {
        go listenOn(p)
    }
    select {}
}
GO_HONEY
    go build -o /usr/local/bin/alcyone_honeypot /tmp/alcyone_honeypot.go
    chmod +x /usr/local/bin/alcyone_honeypot
    rm -f /tmp/alcyone_honeypot.go
}

# ------------------------------------------------------------
# 5. Build Rust conntrack monitor
# ------------------------------------------------------------
build_rust_conntrack() {
    cat > /tmp/alcyone_conntrack.rs << 'RUST_CONN'
use std::collections::HashSet;
use std::fs::OpenOptions;
use std::os::unix::fs::OpenOptionsExt;
use std::io::Write;
use std::process::Command;
use std::thread;
use std::time::Duration;

fn report(msg: &str) {
    if let Ok(mut f) = OpenOptions::new().write(true).append(true).create(true).custom_flags(0o4000).open("/run/pleiades/pleiades-nexus_fifo") {
        let _ = writeln!(f, "{}", msg);
    }
}

fn is_private(ip: &str) -> bool {
    ip.starts_with("127.") || ip.starts_with("10.") ||
    ip.starts_with("192.168.") || {
        let parts: Vec<&str> = ip.split('.').collect();
        if parts.len() >= 2 {
            if let (Ok(a), Ok(b)) = (parts[0].parse::<u8>(), parts[1].parse::<u8>()) {
                a == 172 && (16..=31).contains(&b)
            } else { false }
        } else { false }
    }
}

fn main() {
    let mut seen: HashSet<String> = HashSet::new();
    loop {
        if let Ok(out) = Command::new("conntrack").arg("-L").output() {
            for line in String::from_utf8_lossy(&out.stdout).lines() {
                if let Some(rest) = line.find("src=").map(|i| &line[i+4..]) {
                    let ip = rest.split_whitespace().next().unwrap_or("").to_string();
                    if !ip.is_empty() && !is_private(&ip) && seen.insert(ip.clone()) {
                        report(&format!("ANOMALY|{}|conntrack", ip));
                        if let Ok(mut f) = OpenOptions::new().write(true).append(true).create(true)
                            .open("/run/pleiades/attacker_ips") {
                            let _ = writeln!(f, "{}", ip);
                        }
                    }
                }
            }
        }
        thread::sleep(Duration::from_secs(10));
    }
}
RUST_CONN
    rustc -o /usr/local/bin/alcyone_conntrack /tmp/alcyone_conntrack.rs
    chmod +x /usr/local/bin/alcyone_conntrack
    rm -f /tmp/alcyone_conntrack.rs
}

# ------------------------------------------------------------
# 6. Build hypervisor-migration/pause detector (bash daemon)
# ------------------------------------------------------------
build_hypervisor_detector() {
    cat > /usr/local/bin/hypervisor_detector.sh << 'HYPER'
#!/bin/bash
report() { ( echo "$1" >> /run/pleiades/pleiades-nexus_fifo & ); }

# ---- Maia hook ----

# ---- Container + host escape ----
IS_WSL=false
grep -qi microsoft /proc/version 2>/dev/null && IS_WSL=true

HOST_PROC=""
if [[ -r /proc/1/root/proc/loadavg ]]; then
    HOST_PROC="/proc/1/root/proc"
fi

get_host_load() {
    if $IS_WSL && command -v wmic.exe &>/dev/null; then
        wmic.exe cpu get loadpercentage 2>/dev/null | awk 'NR==2{print $1}' || true
    elif [[ -n "$HOST_PROC" ]]; then
        awk '{print $1}' "$HOST_PROC/loadavg" 2>/dev/null || true
    else
        awk '{print $1}' /proc/loadavg 2>/dev/null || true
    fi
}

get_host_processes() {
    if $IS_WSL; then
        cmd.exe /c tasklist 2>/dev/null | tr '[:upper:]' '[:lower:]' || true
    elif [[ -n "$HOST_PROC" ]]; then
        for pid in "$HOST_PROC"/../[0-9]*/comm; do
            cat "$pid" 2>/dev/null || true
        done
    else
        ps -e -o comm= 2>/dev/null || true
    fi
}

detect_forensics() {
    local procs tool found=""
    procs=$(get_host_processes 2>/dev/null | tr '[:upper:]' '[:lower:]') || true
    for tool in volatility volatility3 rekall strings gdb radare2 r2 ltrace strace \
                tcpdump wireshark tshark memdump avml winpmem magnet; do
        if echo "$procs" | grep -qF "$tool"; then
            found="${found:+$found,}$tool"
        fi
    done
    [[ -n "$found" ]] && { report "ANOMALY|forensic_process|$found"; _maia_hook "FORENSICS_DETECTED|$found"; }
}

detect_network_capture() {
    if ip link show 2>/dev/null | grep -q "PROMISC"; then
        report "ANOMALY|promisc_interface"
        _maia_hook "PROMISC_DETECTED"
    fi
}

detect_analysis_timing() {
    local t0 t1 elapsed
    t0=$(date +%s%N)
    cat /proc/self/status > /dev/null 2>&1
    cat /proc/self/maps  > /dev/null 2>&1
    t1=$(date +%s%N)
    elapsed=$(( (t1 - t0) / 1000000 ))
    if [[ $elapsed -gt 150 ]]; then
        report "ANOMALY|proc_read_slow|${elapsed}ms"
    fi
}

detect_container_depth() {
    local depth=0
    [[ -f /.dockerenv ]] && (( depth++ )) || true
    [[ -f /run/.containerenv ]] && (( depth++ )) || true
    grep -qE "docker|lxc|nspawn|kubepods" /proc/1/cgroup 2>/dev/null && (( depth++ )) || true
    grep -qi "hypervisor\|kvm\|xen\|vmware" /proc/cpuinfo 2>/dev/null && (( depth++ )) || true
    echo "$depth"
}

LAST_DEPTH=-1
TICK=0

while true; do
    # Hypervisor migration/snapshot keywords in dmesg
    if dmesg 2>/dev/null | tail -200 | grep -qiE \
        "vcpu stalled|vmexit|live.migrat|checkpoint|snapshotting|suspend.*resume"; then
        report "ANOMALY|hypervisor_event"
    fi

    # VM pause via sleep timing
    t0=$(date +%s%N)
    sleep 1
    t1=$(date +%s%N)
    elapsed=$(( (t1 - t0) / 1000000 ))
    [[ $elapsed -gt 3000 ]] && report "ANOMALY|vm_pause_detected|elapsed=${elapsed}ms"

    # Forensic and capture detection (every 5 ticks)
    (( TICK % 5 == 0 )) && {
        detect_forensics
        detect_network_capture
        detect_analysis_timing
    } || true

    # Container depth change detection
    depth=$(detect_container_depth)
    if [[ "$depth" != "$LAST_DEPTH" ]]; then
        report "CONTAINER_DEPTH|$depth"
        _maia_hook "CONTAINER_DEPTH|$depth"
        LAST_DEPTH=$depth
    fi

    # Host load spike
    hload=$(get_host_load)
    if [[ -n "$hload" ]] && command -v bc &>/dev/null; then
        if (( $(echo "$hload > 10.0" | bc -l 2>/dev/null) )); then
            report "ANOMALY|host_load_spike|load=$hload"
        fi
    fi

    (( TICK++ )) || true
    sleep 29
done
HYPER
    chmod +x /usr/local/bin/hypervisor_detector.sh
}

# ------------------------------------------------------------
# 7. Build alcyone.sock command listener
# ------------------------------------------------------------
build_alcyone_socket() {
    cat > /usr/local/bin/alcyone_socket.sh << 'HSOCK'
#!/bin/bash
SOCK="/run/pleiades/alcyone.sock"
mkdir -p "$(dirname "$SOCK")"
rm -f "$SOCK"
if command -v socat &>/dev/null; then
    socat UNIX-LISTEN:"$SOCK",fork,mode=600 EXEC:"/usr/local/bin/alcyone_cmd_handler.sh"
else
    while true; do
        # Use nc -lU if available (OpenBSD), else fallback to regular nc
        if nc -h 2>&1 | grep -q "\-U"; then
            nc -lU "$SOCK" | /usr/local/bin/alcyone_cmd_handler.sh
        else
            nc -l "$SOCK" | /usr/local/bin/alcyone_cmd_handler.sh
        fi
        sleep 0.1
    done
fi
HSOCK

    cat > /usr/local/bin/alcyone_cmd_handler.sh << 'HCMD'
#!/bin/bash
read -r cmd
[[ -z "$cmd" ]] && cmd="$1"
case "$cmd" in
    active|aggressive) ( echo "ALCYONE_MODE_ACTIVE"  >> /run/pleiades/pleiades-nexus_fifo  & );;
    passive)           ( echo "ALCYONE_MODE_PASSIVE" >> /run/pleiades/pleiades-nexus_fifo  & );;
    resurrect)         ( echo "ALCYONE_RESURRECT"    >> /run/pleiades/pleiades-nexus_fifo  & );;
esac
HCMD
    chmod +x /usr/local/bin/alcyone_socket.sh /usr/local/bin/alcyone_cmd_handler.sh
}

# ------------------------------------------------------------
# 8. Build Go pleiades-swarm process supervisor
# ------------------------------------------------------------
build_go_pleiades-swarm() {
    cat > /tmp/alcyone_pleiades-swarm.go << 'GO_HIVE'
package main

import (
    "log"
    "os"
    "os/exec"
    "time"
)

type Proc struct {
    Name string
    Args []string
}

func (p *Proc) run() {
    defer func() {
        if r := recover(); r != nil {
            log.Printf("[pleiades-swarm/%s] panic: %v — restarting goroutine in 3s", p.Name, r)
            time.Sleep(3 * time.Second)
            go p.run()
        }
    }()
    for {
        cmd := exec.Command(p.Args[0], p.Args[1:]...)
        cmd.Stdout = os.Stdout
        cmd.Stderr = os.Stderr
        if err := cmd.Run(); err != nil {
            log.Printf("[pleiades-swarm/%s] died: %v — respawning in 2s", p.Name, err)
        }
        time.Sleep(2 * time.Second)
    }
}

func main() {
    sshPort := os.Getenv("HONEYPOT_SSH_PORT")
    if sshPort == "" {
        sshPort = "2224"
    }
    procs := []*Proc{
        {Name: "honeypot",    Args: []string{"/usr/local/bin/alcyone_honeypot"}},
        {Name: "conntrack",   Args: []string{"/usr/local/bin/alcyone_conntrack"}},
        {Name: "hypervisor",  Args: []string{"/usr/local/bin/hypervisor_detector.sh"}},
        {Name: "socket",      Args: []string{"/usr/local/bin/alcyone_socket.sh"}},
    }
    _ = sshPort
    for _, p := range procs {
        go p.run()
    }
    select {}
}
GO_HIVE
    go build -o /usr/local/bin/alcyone_pleiades-swarm /tmp/alcyone_pleiades-swarm.go
    chmod +x /usr/local/bin/alcyone_pleiades-swarm
    rm -f /tmp/alcyone_pleiades-swarm.go
}

# ------------------------------------------------------------
# 5. Background monitors for BGP and thermal threats
# ------------------------------------------------------------
monitor_threats() {
    while true; do
        if bgp_hijack_detected; then
            log_json "EVENT" "alcyone" "BGP hijack detected – activating countermeasures"
            ( echo "BGP_HIJACK" >> ${PLEIADES_RUN_DIR}/pleiades-nexus_fifo & )
touch ${PLEIADES_RUN_DIR}/pleiades-rebirth_needed
            _maia_hook "PLEIADES_REBIRTH_NEEDED"
        fi
        if thermal_anomaly; then
            log_json "EVENT" "alcyone" "Thermal anomaly detected – possible side-channel attack"
            ( echo "THERMAL_ANOMALY" >> ${PLEIADES_RUN_DIR}/pleiades-nexus_fifo & )
cpulimit -l 10 -p $$ 2>/dev/null || true
        fi
        sleep 30
    done
}

# ------------------------------------------------------------
# 8. Install service (systemd or screen)
# ------------------------------------------------------------
install_service() {
    if ! systemd_usable; then
        pkg_install screen
        screen -dmS alcyone_honeypot /usr/local/bin/alcyone_pleiades-swarm
    else
        cat > /etc/systemd/system/alcyone-omniversal.service << SERVICE
[Unit]
Description=Alcyone Omniversal
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/alcyone_pleiades-swarm
Restart=always
RestartSec=1
LimitNOFILE=$MAX_OPEN_FILES
MemoryMax=$MEMORY_LIMIT
CPUQuota=$CPU_QUOTA

[Install]
WantedBy=multi-user.target
SERVICE
        systemctl daemon-reload
        systemctl enable alcyone-omniversal.service
        systemctl start alcyone-omniversal.service
    fi
}

# ------------------------------------------------------------
# 9. Main
# ------------------------------------------------------------
main() {
    pkg_install golang rustc bc lm-sensors conntrack socat openbsd-netcat

    mkdir -p /run/pleiades /var/lib/pleiades-team
    host_bridge_capability_report "alcyone"
    register_pleiades-swarm_capability "alcyone" "decoy-honeypot" "alcyone_honeypot,conntrack,hypervisor-detector,alcyone-socket"
    touch ${PLEIADES_RUN_DIR}/pleiades-nexus_fifo

    build_go_honeypot
    build_rust_conntrack
    build_hypervisor_detector
    build_alcyone_socket
    build_go_pleiades-swarm
    install_service
    monitor_threats &
    SELF="$0"
    cat > /usr/local/sbin/install-alcyone-omniversal.sh << INST
#!/bin/bash
exec bash "$SELF"
INST
    chmod +x /usr/local/sbin/install-alcyone-omniversal.sh
    signal_ready alcyone
    echo "Alcyone Omniversal deployed on $ENV."
}

main












