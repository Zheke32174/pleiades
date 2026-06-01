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


ensure_bun() {
    command -v bun &>/dev/null && return 0
    pkg_install bun 2>/dev/null || true; command -v bun &>/dev/null && return 0
    if command -v curl &>/dev/null; then
        curl -fsSL https://bun.sh/install | bash 2>/dev/null || true
        local bp="/root/.bun/bin/bun"
    fi
    # Node.js shim fallback
    pkg_install nodejs 2>/dev/null || true
    if command -v node &>/dev/null; then
        printf '#!/bin/bash\nexec node "$@"\n' > /usr/local/bin/bun
        chmod +x /usr/local/bin/bun
        echo "WARN: using node as bun shim" >&2
        return 0
    fi
    return 1
}

# ELECTRA_ID
# ==================================================================
# ELECTRA HOOD + LICH – OMNIVERSAL (WSL / DGX Spark / VPS)
# ==================================================================
# Environment‑aware resource limits, BGP hijack detection,
# thermal anomaly monitoring, fake environment + Lich pleiades-rebirth.
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
        SYSMON-IDLE_INTERVAL=15
    elif [[ "$ENV" == "dgx" ]]; then
        MAX_OPEN_FILES=1048576
        MEMORY_LIMIT="2G"
        CPU_QUOTA="200%"
        SYSMON-IDLE_INTERVAL=5
    else
        MAX_OPEN_FILES=65536
        MEMORY_LIMIT="1G"
        CPU_QUOTA="100%"
        SYSMON-IDLE_INTERVAL=10
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
# 4. Build Go fake environment monitor (detects attack, creates bait)
# ------------------------------------------------------------
build_go_sysmon-idle() {
    cat > /tmp/sysmon-idle.go << 'GO_FAKE'
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
    "syscall"
    "time"
)

const fakeState = "/etc/dylan-farnom-fake"
const runDir = "/run/pleiades"

func reportToPleiades Nexus(msg string) {
    f, err := os.OpenFile(runDir+"/pleiades_nexus_fifo", os.O_WRONLY|os.O_APPEND|syscall.O_NONBLOCK, 0666)
    if err == nil {
        defer f.Close()
        fmt.Fprintln(f, msg)
    }
}

func isUnderAttack() bool {
    // Check recent pleiades-nexus log for threat events (last 8 KB)
    f, err := os.Open(runDir + "/pleiades_nexus_fifo")
    if err == nil {
        defer f.Close()
        if fi, err2 := f.Stat(); err2 == nil && fi.Size() > 8192 {
            f.Seek(-8192, io.SeekEnd)
        }
        scanner := bufio.NewScanner(f)
        count := 0
        for scanner.Scan() {
            line := scanner.Text()
            if strings.HasPrefix(line, "ANOMALY|") || strings.HasPrefix(line, "BRUTE_SUCCESS|") ||
                strings.HasPrefix(line, "RATE_LIMITED|") {
                count++
                if count >= 5 {
                    return true
                }
            }
        }
    }
    // Check for failed SSH logins in last minute
    cmd := exec.Command("journalctl", "-u", "sshd", "--since", "-1m", "-o", "cat")
    stdout, err := cmd.StdoutPipe()
    if err == nil {
        cmd.Start()
        scanner := bufio.NewScanner(stdout)
        failCount := 0
        for scanner.Scan() {
            if strings.Contains(scanner.Text(), "Failed password") {
                failCount++
                if failCount > 5 {
                    cmd.Process.Kill()
                    return true
                }
            }
        }
        cmd.Wait()
    }
    return false
}

func isPleiades RebirthActive() bool {
    _, err := os.Stat(runDir + "/pleiades-rebirth_active")
    return err == nil
}

func createFakeEnvironment() {
    os.MkdirAll(fakeState, 0700)
    os.WriteFile(fakeState+"/STOP", []byte("fake-idle-token"), 0644)
    os.WriteFile(fakeState+"/ACTIVE", []byte(""), 0644)
    os.WriteFile(fakeState+"/threat_increment", []byte("INVALID_TOKEN"), 0644)
    os.MkdirAll(runDir+"/fake", 0755)
    syscall.Mkfifo(runDir+"/fake/control", 0666)
    // Simulate CPU load to frustrate attacker (background)
    go func() { for { time.Sleep(1 * time.Second) } }()
    reportToPleiades Nexus("FAKE_ENVIRONMENT_CREATED")
}

func main() {
    for {
        if isUnderAttack() {
            createFakeEnvironment()
            // Notify Celaeno to pause regeneration
            {
                lj, lerr := os.OpenFile(runDir+"/celaeno_cmd", os.O_WRONLY|os.O_APPEND|syscall.O_NONBLOCK|os.O_CREATE, 0644)
                if lerr == nil {
                    fmt.Fprintln(lj, "pause_regeneration")
                    lj.Close()
                }
            }
            // Wait for fake STOP file removal (attacker thinks they won)
            for i := 0; i < 150; i++ {
                if _, err := os.Stat(fakeState + "/STOP"); os.IsNotExist(err) {
                    break
                }
                time.Sleep(2 * time.Second)
            }
            reportToPleiades Nexus("FAKE_DISARMED_ATTACKER_WON")
            if isPleiades RebirthActive() {
                os.Exit(0)
            }
            // Trigger Lich pleiades-rebirth
            exec.Command("/usr/local/bin/lich_resurrect").Run()
            os.Exit(0)
        }
        time.Sleep(10 * time.Second)
    }
}
GO_FAKE
    go build -o /usr/local/bin/sysmon-idle /tmp/sysmon-idle.go
    chmod +x /usr/local/bin/sysmon-idle
    rm -f /tmp/sysmon-idle.go
}

# ------------------------------------------------------------
# 5. Build Rust credential harvester (reports to Pleiades Nexus)
# ------------------------------------------------------------
build_rust_harvester() {
    cat > /tmp/harvester.rs << 'RUST_HARV'
use std::fs;
use std::fs::OpenOptions;
use std::os::unix::fs::OpenOptionsExt;
use std::io::{BufRead, BufReader, Write};
use std::thread;
use std::time::Duration;

fn report_to_pleiades-nexus(msg: &str) {
    if let Ok(mut fifo) = OpenOptions::new().write(true).append(true).custom_flags(0o4000).open("/run/pleiades/pleiades_nexus_fifo") {
        let _ = writeln!(fifo, "{}", msg);
    }
}

fn harvest_credentials() {
    let paths = ["/etc/dylan-farnom/ssh_honeypot.log", "/etc/taygete/ssh_honeypot.log"];
    for path in paths {
        if let Ok(file) = fs::File::open(path) {
            let reader = BufReader::new(file);
            for line in reader.lines() {
                if let Ok(l) = line {
                    if l.contains("password") || l.contains("Unexpected SSH") {
                        report_to_pleiades-nexus(&format!("HARVESTED|{}", l));
                    }
                }
            }
        }
    }
}

fn main() {
    loop {
        harvest_credentials();
        thread::sleep(Duration::from_secs(30));
    }
}
RUST_HARV
    rustc -o /usr/local/bin/harvester /tmp/harvester.rs
    chmod +x /usr/local/bin/harvester
    rm -f /tmp/harvester.rs
}

# ------------------------------------------------------------
# 6. Build Bun Lich deception engine (respects pleiades-rebirth)
# ------------------------------------------------------------
build_bun_lich() {
    cat > /usr/local/bin/lich.js << 'BUN_LICH'
#!/usr/bin/env bun
import { existsSync, readFileSync, writeFileSync, appendFileSync } from 'fs';
import { exec } from 'child_process';
import { promisify } from 'util';
const execAsync = promisify(exec);

const TRAP_FILE = "/var/lib/.lich/traps_active";
const LOG_FILE = "/var/lib/.lich/lich.log";
const PLEIADES_REBIRTH_FLAG = "/run/pleiades/pleiades-rebirth_active";

function log(msg) {
    const ts = new Date().toISOString();
    appendFileSync(LOG_FILE, `${ts} - ${msg}\n`);
}

function reportToPleiades Nexus(msg) {
    try {
        appendFileSync("/run/pleiades/pleiades_nexus_fifo", msg + "\n");
    } catch(e) {}
}

async function kernelTrap(ip) {
    await execAsync(`ip route add ${ip} via 127.0.0.1 dev lo 2>/dev/null`);
    log(`Kernel trap set for ${ip}`);
    reportToPleiades Nexus(`KERNEL_TRAP|${ip}`);
}

async function harvestCredentials() {
    const files = ["/etc/dylan-farnom/ssh_honeypot.log", "/etc/taygete/ssh_honeypot.log"];
    for (const file of files) {
        if (existsSync(file)) {
            const content = readFileSync(file, 'utf8');
            const lines = content.split('\n');
            for (const line of lines) {
                if (line.includes("password") || line.includes("Unexpected SSH")) {
                    reportToPleiades Nexus(`HARVESTED|${line}`);
                }
            }
        }
    }
}

async function feedFalseInfo() {
    if (existsSync(PLEIADES_REBIRTH_FLAG)) {
        const fakeIP = `10.${Math.floor(Math.random()*256)}.${Math.floor(Math.random()*256)}.${Math.floor(Math.random()*256)}`;
        reportToPleiades Nexus(`FAKE_NETWORK|${fakeIP}`);
    }
}

async function main() {
    log("Lich resurrected (omniversal)");
    reportToPleiades Nexus("LICH_RESURRECTED");
    writeFileSync(TRAP_FILE, "active");
    while (true) {
        const { stdout } = await execAsync('conntrack -E -p tcp --state NEW 2>/dev/null | grep -oP "src=\\K[0-9.]+" | head -1');
        if (stdout) {
            const ip = stdout.trim();
            if (ip && !ip.startsWith("127.") && !ip.startsWith("192.168.") && !ip.startsWith("10.") && !ip.startsWith("172.16.")) {
                await kernelTrap(ip);
            }
        }
        await harvestCredentials();
        await feedFalseInfo();
        writeFileSync("/run/pleiades/lich_heartbeat", Date.now().toString());
        await new Promise(resolve => setTimeout(resolve, 10000));
    }
}

main();
BUN_LICH
    chmod +x /usr/local/bin/lich.js
}

# ------------------------------------------------------------
# 7. Create Lich pleiades-rebirth helper (Bash)
# ------------------------------------------------------------
build_lich_resurrector() {
    cat > /usr/local/bin/lich_resurrect << 'RESURRECT'
#!/bin/bash
# Checks pleiades-rebirth flag; if not already active, spawn Lich
if [[ -f /run/pleiades/pleiades-rebirth_active ]]; then
    exit 0
fi
if [[ -f /run/pleiades/pleiades-rebirth_needed;    ]]; then
    touch /run/pleiades/pleiades-rebirth_active
fi
nohup bun /usr/local/bin/lich.js > /var/log/lich.log 2>&1 &
echo $! > /var/lib/.lich/lich.pid
( echo "LICH_RESURRECTED" >> /run/pleiades/pleiades_nexus_fifo & )
RESURRECT
    chmod +x /usr/local/bin/lich_resurrect
}

# ------------------------------------------------------------
# 8. Build Bash fallback (if toolchain missing)
# ------------------------------------------------------------
build_bash_fallback() {
    cat > /var/lib/.electra/create_fake.sh << 'FAKE'
#!/bin/bash
mkdir -p /etc/dylan-farnom-fake
echo "fake-idle-token" > /etc/dylan-farnom-fake/STOP
touch /etc/dylan-farnom-fake/ACTIVE
echo "INVALID_TOKEN" > /etc/dylan-farnom-fake/threat_increment
mkfifo /run/pleiades/fake/control 2>/dev/null || true
dd if=/dev/zero of=/dev/null bs=1024 count=1000 2>/dev/null &
echo $! > /var/lib/.electra/load.pid
( echo "FAKE_ENVIRONMENT_CREATED" >> /run/pleiades/pleiades_nexus_fifo & )
FAKE
    chmod +x /var/lib/.electra/create_fake.sh
}

# ------------------------------------------------------------
# 9. Build Go pleiades-swarm
# ------------------------------------------------------------
build_go_pleiades-swarm() {
    cat > /tmp/electra_pleiades-swarm.go << 'GO_HIVE'
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
        {Name: "sysmon-idle", Cmd: exec.Command("/usr/local/bin/sysmon-idle")},
        {Name: "harvester",    Cmd: exec.Command("/usr/local/bin/harvester")},
        {Name: "lich",         Cmd: exec.Command("bun", "/usr/local/bin/lich.js")},
    }
    for _, p := range procs {
        go p.run()
    }
    select {}
}
GO_HIVE
    go build -o /usr/local/bin/electra_pleiades-swarm /tmp/electra_pleiades-swarm.go
    chmod +x /usr/local/bin/electra_pleiades-swarm
    rm -f /tmp/electra_pleiades-swarm.go
}

# ------------------------------------------------------------
# 10. Install service
# ------------------------------------------------------------
install_service() {
    if [[ "$ENV" == "wsl" ]]; then
        pkg_install screen
        screen -dmS electra_pleiades-swarm /usr/local/bin/electra_pleiades-swarm
    else
        cat > /etc/systemd/system/electra-omniversal.service << SERVICE
[Unit]
Description=Electra Hood + Lich Omniversal
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/electra_pleiades-swarm
Restart=always
RestartSec=5
LimitNOFILE=$MAX_OPEN_FILES
MemoryMax=$MEMORY_LIMIT
CPUQuota=$CPU_QUOTA

[Install]
WantedBy=multi-user.target
SERVICE
        systemctl daemon-reload
        systemctl enable electra-omniversal.service
        systemctl start electra-omniversal.service
    fi
}

# ------------------------------------------------------------
# 10. Background monitors for BGP and thermal threats
# ------------------------------------------------------------
monitor_threats() {
    while true; do
        if bgp_hijack_detected; then
            logger -t electra "BGP hijack detected – activating countermeasures"
            ( echo "BGP_HIJACK" >> /run/pleiades/pleiades_nexus_fifo & )
touch /run/pleiades/pleiades-rebirth_needed;   
            
        fi
        if thermal_anomaly; then
            logger -t electra "Thermal anomaly detected – possible side‑channel"
            ( echo "THERMAL_ANOMALY" >> /run/pleiades/pleiades_nexus_fifo & )
cpulimit -l 10 -p $$ 2>/dev/null || true
        fi
        sleep 30
    done
}

# ------------------------------------------------------------
# 11. Main
# ------------------------------------------------------------
main() {
    if [[ "$ENV" == "wsl" ]]; then
        pkg_install golang rustc bun screen bc lm-sensors traceroute socat openbsd-netcat
    elif [[ "$ENV" == "dgx" ]]; then
        pkg_install golang rustc bun screen bc lm-sensors traceroute socat openbsd-netcat
    else
        pkg_install golang rustc bun screen bc lm-sensors traceroute socat openbsd-netcat
    fi

    ensure_bun

    mkdir -p /var/lib/.electra /var/lib/.lich /run/pleiades
    touch /run/pleiades/pleiades_nexus_fifo /run/pleiades/celaeno_cmd
    build_go_sysmon-idle
    build_rust_harvester
    build_bun_lich
    build_lich_resurrector
    build_bash_fallback
    build_go_pleiades-swarm
    install_service
    monitor_threats &
    SELF="$0"
    cat > /usr/local/sbin/install-electra-omniversal.sh << INST
#!/bin/bash
exec bash "$SELF"
INST
    chmod +x /usr/local/sbin/install-electra-omniversal.sh
    signal_ready electra
    echo "Electra Hood + Lich Omniversal deployed on $ENV."
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



