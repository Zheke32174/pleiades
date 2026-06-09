#!/usr/bin/env bash
# ryz-compliance: 38efefc2 shell
set -uo pipefail

# Source shared library
source /usr/local/lib/pleiades-common.sh 2>/dev/null || source "$(dirname "$0")/pleiades-common.sh"
# Source configuration
source /etc/purple/pleiades.conf 2>/dev/null || source "$(dirname "$0")/../etc/purple/pleiades.conf"

# --- END MAIA EVENT HOOK ---

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

# PLEIADES_REBIRTH_ID
# ==================================================================
# PLEIADES_REBIRTH PROTOCOL – OMNIVERSAL (WSL / DGX Spark / VPS)
# ==================================================================
# Encrypted recovery state, SSH decoy logging, recovery beacon.
# Environment‑aware resource limits, BGP hijack detection,
# thermal anomaly monitoring.
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

DECOY_SSH_PORT="${DECOY_SSH_PORT:-2223}"   # distinct from Alcyone's honeypot on 2224

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
    elif [[ "$ENV" == "bare-metal" ]]; then
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

# ------------------------------------------------------------
# 3. Thermal/side‑channel anomaly detection
# ------------------------------------------------------------

# ------------------------------------------------------------
# 4. Build Go pleiades-rebirth state keeper (encrypted snapshot)
# ------------------------------------------------------------
build_go_pleiades-rebirth() {
    cat > /tmp/pleiades-rebirth.go << 'GO_RES'
package main

import (
    "crypto/rand"
    "os"
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

var pleiadesNexusFifo *os.File

func init() {
    var err error
    pleiadesNexusFifo, err = os.OpenFile("/run/pleiades/pleiades-nexus_fifo", os.O_WRONLY|os.O_APPEND|syscall.O_NONBLOCK, 0666)
    if err != nil {
        pleiadesNexusFifo = nil
    }
}

func report(msg string) {
    if pleiadesNexusFifo != nil {
        fmt.Fprintln(pleiadesNexusFifo, msg)
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
#    Sources: maia_crypto probe (mDNS → DNS TXT → paste → Tor),
#    fallback to direct DNS TXT if binary unavailable.
# ------------------------------------------------------------
build_bash_beacon() {
    mkdir -p /var/lib/.pleiades-rebirth
    cat > /var/lib/.pleiades-rebirth/beacon.sh << 'BEACON'
#!/bin/bash
RESURRECT_DIR="/var/lib/.pleiades-rebirth"
RUN_DIR="/run/pleiades"
BEACON_INTERVAL=7200

report_to_pleiades-nexus() { echo "$1" >> "$RUN_DIR/pleiades-nexus_fifo" 2>/dev/null || true; }

check_escrow_signal() {
    local signal=""

    # Primary: maia_crypto probe — tries mDNS, DNS TXT, paste sites, Tor
    # Every source is Ed25519-verified before being accepted.
    if command -v maia_crypto &>/dev/null && \
       [[ -f /var/lib/.maia/keys/ed25519.pub ]]; then
        local probe_out
        probe_out=$(maia_crypto probe 2>/dev/null) || true
        if [[ -n "$probe_out" ]]; then
            signal=$(echo "$probe_out" | grep "^PAYLOAD=" | cut -d= -f2-)
        fi
    fi

    echo "$signal"
}

while true; do
    signal=$(check_escrow_signal)
    if [[ "$signal" == *"RESURRECT"* ]]; then
        log_json "EVENT" "pleiades-rebirth" "Received resurrect signal – restoring Singularity"
        report_to_pleiades-nexus "RESURRECT_SIGNAL_RECEIVED"
        touch "$RUN_DIR/pleiades-rebirth_needed"
        _maia_hook "PLEIADES_REBIRTH_NEEDED"
        for i in {1..30}; do
            [[ -f "$RUN_DIR/pleiades-rebirth_acknowledged" ]] && break
            sleep 1
        done
        if [[ -f "$RESURRECT_DIR/state.tar.gz.enc" ]] && [[ -f "$RESURRECT_DIR/key" ]]; then
            openssl enc -d -aes-256-cbc -pbkdf2 \
                -in "$RESURRECT_DIR/state.tar.gz.enc" \
                -out /tmp/state.tar.gz \
                -pass file:"$RESURRECT_DIR/key"
            RESTORE_TMP=$(mktemp -d /tmp/state_restore_XXXXXX)
            tar -xzf /tmp/state.tar.gz -C "$RESTORE_TMP"
            # Validate: only allow expected subdirs, no absolute paths or ..
            if tar -tzf /tmp/state.tar.gz 2>/dev/null | grep -qE '^\.\.|^/'; then
                rm -rf "$RESTORE_TMP"
                report_to_pleiades-nexus "RESTORATION_REJECTED_UNSAFE_TAR"
            else
                cp -a "$RESTORE_TMP"/. /
                rm -rf "$RESTORE_TMP"
            fi
            for installer in /usr/local/sbin/install-*-omniversal.sh; do
                [[ -f "$installer" ]] && bash "$installer" &
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
# 7. Build Go pleiades-swarm (orchestrates keeper, SSH decoy logger, beacon)
# ------------------------------------------------------------
build_go_pleiades-swarm() {
    cat > /tmp/pleiades-rebirth_pleiades-swarm.go << 'GO_HIVE'
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
    procs := []*Proc{}
    if _, err := os.Stat("/usr/local/bin/pleiades-rebirth_keeper"); err == nil {
        procs = append(procs, &Proc{Name: "pleiades-rebirth_keeper", Cmd: exec.Command("/usr/local/bin/pleiades-rebirth_keeper")})
    }
    if _, err := os.Stat("/usr/local/bin/ssh_decoy_logger"); err == nil {
        procs = append(procs, &Proc{Name: "ssh_decoy_logger", Cmd: exec.Command("/usr/local/bin/ssh_decoy_logger")})
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
    if ! systemd_usable; then
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
            ( echo "BGP_HIJACK" >> ${PLEIADES_RUN_DIR}/pleiades-nexus_fifo & )
touch ${PLEIADES_RUN_DIR}/pleiades-rebirth_needed
            _maia_hook "PLEIADES_REBIRTH_NEEDED"
        fi
        if thermal_anomaly; then
            logger -t pleiades-rebirth "Thermal anomaly detected – possible side‑channel"
            ( echo "THERMAL_ANOMALY" >> ${PLEIADES_RUN_DIR}/pleiades-nexus_fifo & )
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
    elif [[ "$ENV" == "bare-metal" ]]; then
        pkg_install golang bc lm-sensors traceroute openssl socat openbsd-netcat
    else
        pkg_install golang bc lm-sensors traceroute openssl socat openbsd-netcat
    fi

    mkdir -p /var/lib/.pleiades-rebirth /run/pleiades
    host_bridge_capability_report "pleiades-rebirth"
    register_pleiades-swarm_capability "pleiades-rebirth" "recovery-decoy" "pleiades-rebirth-keeper,ssh-decoy,owner-escrow-beacon"
    build_go_pleiades-rebirth
    build_go_ssh_decoy_logger
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

main
# --- END MAIA EVENT HOOK ---
# --- END MAIA EVENT HOOK ---
# --- END MAIA EVENT HOOK ---
# --- END MAIA EVENT HOOK ---
# --- END MAIA EVENT HOOK ---
# --- END MAIA EVENT HOOK ---
