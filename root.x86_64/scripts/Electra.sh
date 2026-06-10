#!/usr/bin/env bash
# ryz-compliance: c0f42724 shell
set -uo pipefail
# Source shared library
source /usr/local/lib/pleiades-common.sh 2>/dev/null || source "$(dirname "$0")/pleiades-common.sh"

# Source configuration
source /etc/purple/pleiades.conf 2>/dev/null || source "$(dirname "$0")/../etc/purple/pleiades.conf"

# ELECTRA_ID
# ==================================================================
# ELECTRA HOOD + LICH – OMNIVERSAL (WSL / bare metal / VPS)
# ==================================================================
# Environment‑aware resource limits, BGP hijack detection,
# thermal anomaly monitoring, fake environment + Lich pleiades-rebirth.
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
        MEMORY_LIMIT="512M"
        CPU_QUOTA="50%"
        SYSMON_IDLE_INTERVAL=15
    elif [[ "$ENV" == "bare_metal" ]]; then
        MAX_OPEN_FILES=1048576
        MEMORY_LIMIT="2G"
        CPU_QUOTA="200%"
        SYSMON_IDLE_INTERVAL=5
    else
        MAX_OPEN_FILES=65536
        MEMORY_LIMIT="1G"
        CPU_QUOTA="100%"
        SYSMON_IDLE_INTERVAL=10
    fi
}

# ------------------------------------------------------------
# 2. Anti‑BGP hijack detection
# ------------------------------------------------------------
# (handled by pleiades-common.sh)
# ------------------------------------------------------------
# 3. Thermal/side‑channel anomaly detection
# ------------------------------------------------------------
# (handled by pleiades-common.sh)

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
    "os"
    "os/exec"
    "strings"
    "syscall"
    "time"
)

const fakeState = "/etc/imtherealsparticus"
const runDir = "/run/pleiades"

func reportToPleiadesNexus(msg string) {
    f, err := os.OpenFile(runDir+"/pleiades-nexus_fifo", os.O_WRONLY|os.O_APPEND|syscall.O_NONBLOCK, 0666)
    if err == nil {
        defer f.Close()
        fmt.Fprintln(f, msg)
    }
}

func isUnderAttack() bool {
    // Check recent pleiades-nexus log for threat events (last 8 KB)
    f, err := os.Open(runDir + "/pleiades-nexus_fifo")
    if err == nil {
        defer f.Close()
        if fi, err2 := f.Stat(); err2 == nil && fi.Size() > 8192 {
            f.Seek(-8192, io.SeekEnd)
        }
        scanner := bufio.NewScanner(f)
        count := 0
        for scanner.Scan() {
            line := scanner.Text()
            if strings.HasPrefix(line, "ANOMALY|") || strings.HasPrefix(line, "CREDENTIAL_FINDING|") ||
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

func isPleiadesRebirthActive() bool {
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
    reportToPleiadesNexus("FAKE_ENVIRONMENT_CREATED")
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
            reportToPleiadesNexus("FAKE_DISARMED_ATTACKER_WON")
            if isPleiadesRebirthActive() {
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

fn report_to_pleiades_nexus(msg: &str) {
    if let Ok(mut fifo) = OpenOptions::new().write(true).append(true).custom_flags(0o4000).open("/run/pleiades/pleiades-nexus_fifo") {
        let _ = writeln!(fifo, "{}", msg);
    }
}

fn harvest_credentials() {
    let paths = ["/etc/imtherealsparticus/ssh_honeypot.log", "/etc/taygete/ssh_honeypot.log"];
    for path in paths {
        if let Ok(file) = fs::File::open(path) {
            let reader = BufReader::new(file);
            for line in reader.lines() {
                if let Ok(l) = line {
                    if l.contains("password") || l.contains("Unexpected SSH") {
                        report_to_pleiades_nexus(&format!("HARVESTED|{}", l));
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

function reportToPleiadesNexus(msg) {
    try {
        appendFileSync("/run/pleiades/pleiades-nexus_fifo", msg + "\n");
    } catch(e) {}
}

async function kernelTrap(ip) {
    await execAsync(`ip route add ${ip} via 127.0.0.1 dev lo 2>/dev/null`);
    log(`Kernel trap set for ${ip}`);
    reportToPleiadesNexus(`KERNEL_TRAP|${ip}`);
}

async function harvestCredentials() {
    const files = ["/etc/imtherealsparticus/ssh_honeypot.log", "/etc/taygete/ssh_honeypot.log"];
    for (const file of files) {
        if (existsSync(file)) {
            const content = readFileSync(file, 'utf8');
            const lines = content.split('\n');
            for (const line of lines) {
                if (line.includes("password") || line.includes("Unexpected SSH")) {
                    reportToPleiadesNexus(`HARVESTED|${line}`);
                }
            }
        }
    }
}

async function feedFalseInfo() {
    if (existsSync(PLEIADES_REBIRTH_FLAG)) {
        const fakeIP = `10.${Math.floor(Math.random()*256)}.${Math.floor(Math.random()*256)}.${Math.floor(Math.random()*256)}`;
        reportToPleiadesNexus(`FAKE_NETWORK|${fakeIP}`);
    }
}

async function main() {
    log("Lich resurrected (omniversal)");
    reportToPleiadesNexus("LICH_RESURRECTED");
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
if [[ -f /run/pleiades/pleiades-rebirth_needed ]]; then
    touch /run/pleiades/pleiades-rebirth_active
fi
nohup bun /usr/local/bin/lich.js > /var/log/lich.log 2>&1 &
echo $! > /var/lib/.lich/lich.pid
( echo "LICH_RESURRECTED" >> /run/pleiades/pleiades-nexus_fifo & )
RESURRECT
    chmod +x /usr/local/bin/lich_resurrect
}

# ------------------------------------------------------------
# 8. Build Bash fallback (if toolchain missing)
# ------------------------------------------------------------
build_bash_fallback() {
    cat > /var/lib/.electra/create_fake.sh << 'FAKE'
#!/bin/bash
mkdir -p /etc/imtherealsparticus
echo "fake-idle-token" > /etc/imtherealsparticus/STOP
touch /etc/imtherealsparticus/ACTIVE
echo "INVALID_TOKEN" > /etc/imtherealsparticus/threat_increment
mkfifo /run/pleiades/fake/control 2>/dev/null || true
dd if=/dev/zero of=/dev/null bs=1024 count=1000 2>/dev/null &
echo $! > /var/lib/.electra/load.pid
( echo "FAKE_ENVIRONMENT_CREATED" >> /run/pleiades/pleiades-nexus_fifo & )
FAKE
    chmod +x /var/lib/.electra/create_fake.sh
}

# ------------------------------------------------------------
# 9. Build Go pleiades-swarm
# ------------------------------------------------------------
build_go_pleiades-swarm() {
    cat > /tmp/sysmon_daemon.go << 'GO_HIVE'
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
    go build -o /usr/local/bin/sysmon-daemon /tmp/sysmon_daemon.go
    chmod +x /usr/local/bin/sysmon-daemon
    rm -f /tmp/sysmon_daemon.go
}

# ------------------------------------------------------------
# 10. Install service
# ------------------------------------------------------------
install_service() {
    if ! systemd_usable; then
        pkg_install screen
        screen -dmS sysmon_daemon /usr/local/bin/sysmon-daemon
    else
        cat > /etc/systemd/system/electra-omniversal.service << SERVICE
[Unit]
Description=Electra Omniversal Runtime Monitor
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/sysmon-daemon
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
            log_json "EVENT" "electra" "BGP hijack detected – activating countermeasures"
            ( echo "BGP_HIJACK" >> ${PLEIADES_RUN_DIR}/pleiades-nexus_fifo & )
touch ${PLEIADES_RUN_DIR}/pleiades-rebirth_needed
            _maia_hook "PLEIADES_REBIRTH_NEEDED"
        fi
        if thermal_anomaly; then
            log_json "EVENT" "electra" "Thermal anomaly detected – possible side‑channel"
            ( echo "THERMAL_ANOMALY" >> ${PLEIADES_RUN_DIR}/pleiades-nexus_fifo & )
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
    elif [[ "$ENV" == "bare_metal" ]]; then
        pkg_install golang rustc bun screen bc lm-sensors traceroute socat openbsd-netcat
    else
        pkg_install golang rustc bun screen bc lm-sensors traceroute socat openbsd-netcat
    fi

    ensure_bun

    mkdir -p /var/lib/.electra /var/lib/.lich /run/pleiades
    host_bridge_capability_report "electra"
    register_pleiades-swarm_capability "electra" "fake-environment" "fake-monitor,harvester,lich,electra-pleiades-swarm"
    touch ${PLEIADES_RUN_DIR}/pleiades-nexus_fifo ${PLEIADES_RUN_DIR}/celaeno_cmd
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

main










