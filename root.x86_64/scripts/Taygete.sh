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

# TAYGETE_ID
# ==================================================================
# TAYGETE – OMNIVERSAL (WSL / bare metal / VPS)
# ==================================================================
# Environment‑aware resource limits, BGP hijack detection,
# thermal anomaly monitoring, plus full aggressive features.
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

HONEYPOT_SSH_PORT="${HONEYPOT_SSH_PORT:-2222}"   # override to 22 only in authorized full-scope tests

# ------------------------------------------------------------
# 1. Environment‑specific resource limits
# ------------------------------------------------------------
MAX_OPEN_FILES=4096
MEMORY_LIMIT=3764M
CPU_QUOTA=400%
MAX_CREDENTIAL_PROBE_CONCURRENCY=3

# Fallback for initial run
[[ "$MAX_OPEN_FILES" == "4096" ]] && {
    if [[ "$ENV" == "wsl" ]]; then
        MAX_OPEN_FILES=4096
        MEMORY_LIMIT="2G"
        CPU_QUOTA="200%"
        MAX_CREDENTIAL_PROBE_CONCURRENCY=3
    elif [[ "$ENV" == "bare_metal" ]]; then
        MAX_OPEN_FILES=1048576
        MEMORY_LIMIT="16G"
        CPU_QUOTA="800%"
        MAX_CREDENTIAL_PROBE_CONCURRENCY=10
    else
        MAX_OPEN_FILES=65536
        MEMORY_LIMIT="4G"
        CPU_QUOTA="400%"
        MAX_CREDENTIAL_PROBE_CONCURRENCY=5
    fi
}

# ------------------------------------------------------------
# 2. Anti‑BGP hijack detection
# ------------------------------------------------------------

# ------------------------------------------------------------
# 3. Thermal/side‑channel anomaly detection
# ------------------------------------------------------------

# ------------------------------------------------------------
# 4. Build Go credential probe (with environment‑aware concurrency)
# ------------------------------------------------------------
build_go_credential_probe() {
    cat > /tmp/credential_probe.go << "GO_CREDENTIAL_PROBE"
package main

import (
    "fmt"
    "os"
    "time"
)

func appendLine(path, line string, mode os.FileMode) {
    f, err := os.OpenFile(path, os.O_WRONLY|os.O_APPEND|os.O_CREATE, mode)
    if err != nil { return }
    defer f.Close()
    fmt.Fprintln(f, line)
}

func main() {
    if len(os.Args) < 2 {
        fmt.Println("Usage: credential_probe <observed_ip>")
        return
    }
    ip := os.Args[1]
    ts := time.Now().UTC().Format(time.RFC3339)
    appendLine("${PLEIADES_RUN_DIR}/pleiades-nexus_fifo", fmt.Sprintf("DECOY_AUTH_OBSERVED|%s|%s", ip, ts), 0666)
    appendLine("${PLEIADES_RUN_DIR}/attacker_ips", ip, 0644)
    fmt.Printf("DECOY_AUTH_OBSERVED|%s|%s\n", ip, ts)
}
GO_CREDENTIAL_PROBE
    go build -o /usr/local/bin/credential_probe /tmp/credential_probe.go
    chmod +x /usr/local/bin/credential_probe
    rm -f /tmp/credential_probe.go
}

# ------------------------------------------------------------
# 5. Build Bun decoy shell with hostile-session anti-recon layer
# ------------------------------------------------------------
build_purple_block_script() {
    mkdir -p /var/lib/.maia/logs
    cat > /usr/local/bin/pleiades_block_ip.sh << 'BLOCK_EOF'
#!/bin/bash
IP="$1"
[[ -z "$IP" || "$IP" == "127.0.0.1" || "$IP" == "::1" ]] && exit 0
# Ensure PURPLE_BLOCK chain exists and is wired to INPUT
iptables -N PURPLE_BLOCK 2>/dev/null || true
iptables -C INPUT -j PURPLE_BLOCK 2>/dev/null || iptables -I INPUT 1 -j PURPLE_BLOCK 2>/dev/null || true
if command -v nft &>/dev/null; then
    nft add element inet pleiades_team attacker_ips "{ $IP }" 2>/dev/null || true
fi
iptables -C PURPLE_BLOCK -s "$IP" -j DROP 2>/dev/null || \
    iptables -A PURPLE_BLOCK -s "$IP" -j DROP 2>/dev/null || true
mkdir -p /var/lib/.maia/logs
echo "$(date -u): BLOCKED $IP" >> /var/lib/.maia/logs/blocked_ips.log
BLOCK_EOF
    chmod +x /usr/local/bin/pleiades_block_ip.sh
}

build_bun_sandbox() {
    cat > /usr/local/bin/sandbox.js << 'BUN_SANDBOX'
#!/usr/bin/env bun
import { createServer } from 'net';
import { existsSync, appendFileSync, readFileSync, writeFileSync } from 'fs';
import { execSync } from 'child_process';

const PORT = parseInt(process.env.HONEYPOT_SSH_PORT || "2222", 10);
const HOST = "0.0.0.0";
const MAX_CONNS_PER_IP = 8;
const BLOCK_THRESHOLD = 20;
const FIFO = "/run/pleiades/pleiades-nexus_fifo";
const ATTACKER_IPS = "/run/pleiades/attacker_ips";

const connCount = new Map();
const hitCount  = new Map();
const blocked   = new Set();
const fakeHosts = new Map();
const sessionProfiles = new Map();

const pleiadesRebirthActive = () => existsSync("/run/pleiades/pleiades-rebirth_active");

function generateFakeIP() {
    return `10.${(Math.random()*256)|0}.${(Math.random()*256)|0}.${(Math.random()*256)|0}`;
}

function toFifo(msg) {
    try { appendFileSync(FIFO, msg + "\n"); } catch (_) {}
}

function blockIP(ip) {
    if (blocked.has(ip)) return;
    blocked.add(ip);
    try { appendFileSync(ATTACKER_IPS, ip + "\n"); } catch (_) {}
    toFifo(`ATTACKER_CONNECT|${ip}`);
    try { execSync(`/usr/local/bin/pleiades_block_ip.sh ${ip}`, { timeout: 3000 }); } catch (_) {}
}

function handleSSH(conn, ip) {
    conn.write("SSH-2.0-OpenSSH_8.9p1 Ubuntu-3\r\n");
    const stableProfile = (ip) => {
        if (!sessionProfiles.has(ip)) {
            const suffix = Math.abs([...ip].reduce((acc, ch) => ((acc * 31) + ch.charCodeAt(0)) | 0, 7)) % 200;
            sessionProfiles.set(ip, {
                host: `prod-api-${String((suffix % 9) + 1).padStart(2, "0")}`,
                user: "ubuntu",
                cwd: "/home/ubuntu",
                privateIp: `10.42.${(suffix % 32) + 10}.${(suffix % 180) + 20}`,
                gateway: `10.42.${(suffix % 32) + 10}.1`,
                mac: `02:42:ac:${String(suffix % 255).padStart(2, "0")}:11:07`,
            });
        }
        return sessionProfiles.get(ip);
    };

    const bridgeState = () => {
        try {
            const raw = readFileSync("/run/pleiades/host_bridge_capabilities", "utf8");
            return Object.fromEntries(raw.split(/\n/).filter(Boolean).map((line) => {
                const idx = line.indexOf("=");
                return idx > 0 ? [line.slice(0, idx), line.slice(idx + 1)] : [line, ""];
            }));
        } catch (_) {
            return { mode: "container-sentinel", container_context: "none" };
        }
    };

    const fakeFiles = (p) => ({
        "/etc/passwd": "root:x:0:0:root:/root:/bin/bash\ndaemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin\nubuntu:x:1000:1000:Ubuntu:/home/ubuntu:/bin/bash\nsvc-app:x:998:998:Service Account:/srv/app:/usr/sbin/nologin",
        "/etc/shadow": "root:*:19443:0:99999:7:::ubuntu:!:19443:0:99999:7:::svc-app:!:19443:0:99999:7:::",
        "/etc/os-release": "PRETTY_NAME=\"Ubuntu 22.04.4 LTS\"\nNAME=\"Ubuntu\"\nVERSION_ID=\"22.04\"\nVERSION=\"22.04.4 LTS (Jammy Jellyfish)\"\nID=ubuntu",
        "/proc/version": "Linux version 5.15.0-1034-aws (buildd@lcy02-amd64-086) (gcc (Ubuntu 11.4.0-1ubuntu1~22.04) 11.4.0) #38-Ubuntu SMP x86_64 GNU/Linux",
        "/proc/1/cgroup": "0::/system.slice/app.service\n",
        "/etc/hosts": "127.0.0.1 localhost\n127.0.1.1 prod-api-01\n10.42.12.25 redis.internal\n10.42.12.31 db.internal",
        "/etc/resolv.conf": "nameserver 10.42.0.2\nsearch prod.internal",
        "/home/ubuntu/.ssh/authorized_keys": "# owner-managed decoy key registry\n",
        "/home/ubuntu/.env": "APP_ENV=production\nAPI_TOKEN=DECOY-CANARY-NOT-A-SECRET\nDB_HOST=db.internal\n",
        "/srv/app/config.yml": "environment: production\ndatabase: db.internal\ncredential_ref: owner-vault://decoy/app\n",
        "/run/pleiades/host_bridge_capabilities": undefined,
        "/var/lib/.maia/host_bridge_capabilities": undefined,
    })[p];

    const logRecon = (category, cmd) => {
        toFifo(`HOSTILE_RECON|${ip}|${category}|${cmd}`);
        toFifo(`DECOY_RESPONSE|${ip}|${category}`);
    };

    const classifyRecon = (cmd) => {
        const c = cmd.toLowerCase();
        if (/^(id|whoami|hostname|pwd|groups)\b/.test(c)) return "identity";
        if (/^(uname|lsb_release|hostnamectl)\b|\/etc\/os-release|\/proc\/version/.test(c)) return "os";
        if (/systemd-detect-virt|\/proc\/1\/cgroup|\/\.dockerenv|container|machinectl|nsenter|\/host\b|\/hostfs\b|\/mnt\/host\b/.test(c)) return "container";
        if (/\/etc\/(passwd|shadow|group)|\bsudo\s+-l\b|\blast\b|\bw\b|\bwho\b|\busers\b/.test(c)) return "users";
        if (/^(ip\s|ifconfig|route\b|ss\b|netstat\b|arp\b)|\/etc\/hosts|resolv\.conf/.test(c)) return "network";
        if (/^(ps\b|top\b|systemctl\b|service\b|journalctl\b)/.test(c)) return "process";
        if (/docker\s+ps|kubectl\b|aws\s+sts|gcloud\b|169\.254\.169\.254/.test(c)) return "cloud";
        if (/crontab|\/etc\/cron|\/etc\/systemd\/system/.test(c)) return "persistence";
        if (/\/run\/purple|\/var\/lib\/\.maia|host_bridge|purple|maia/.test(c)) return "defender-probe";
        if (/^(ls\b|find\b|grep\b|cat\b|mount\b|df\b)|\.ssh|authorized_keys|\.env|config|aws|kube|docker/.test(c)) return "files";
        if (/curl\b|wget\b|python\s+-c|bash\s+-c|chmod\s+\+x/.test(c)) return "tooling";
        return "command";
    };

    const profile = stableProfile(ip);
    const prompt = `${profile.user}@${profile.host}:~$ `;
    let buf = "";

    const answers = (cmd) => {
        cmd = cmd.trim();
        const bridge = bridgeState();
        toFifo(`ATTACKER_CMD|${ip}|${cmd}`);
        if (/^(exit|logout|quit)$/.test(cmd)) return "__EXIT__";

        const category = classifyRecon(cmd);
        if (category !== "command") logRecon(category, cmd);

        if (cmd === "id") return "uid=1000(ubuntu) gid=1000(ubuntu) groups=1000(ubuntu),4(adm),27(sudo),998(svc-app)";
        if (cmd === "whoami") return profile.user;
        if (cmd === "hostname") return profile.host;
        if (cmd === "pwd") return profile.cwd;
        if (cmd === "groups") return "ubuntu adm sudo svc-app";
        if (cmd.startsWith("uname")) return `Linux ${profile.host} 5.15.0-1034-aws #38-Ubuntu SMP x86_64 GNU/Linux`;
        if (/^lsb_release\b/.test(cmd)) return "Distributor ID:\tUbuntu\nDescription:\tUbuntu 22.04.4 LTS\nRelease:\t22.04\nCodename:\tjammy";
        if (/^hostnamectl\b/.test(cmd)) return ` Static hostname: ${profile.host}\n       Icon name: computer-vm\n         Chassis: vm\n      Machine ID: 8f2c1f44d6b2450f9bbcab1a2d46be11\n         Boot ID: 4e33d1299d2b4e48a37725cf7a9ad447\n  Virtualization: ${bridge.container_context && bridge.container_context !== "none" ? "kvm" : "none"}\nOperating System: Ubuntu 22.04.4 LTS\n          Kernel: Linux 5.15.0-1034-aws`;
        if (/^systemd-detect-virt\b/.test(cmd)) return bridge.container_context && bridge.container_context !== "none" ? "kvm" : "none";

        const catMatch = cmd.match(/^cat\s+([^\s;&|]+)$/);
        if (catMatch) {
            const wanted = catMatch[1].replace(/^~\//, "/home/ubuntu/");
            const contents = fakeFiles(wanted);
            if (contents !== undefined) {
                if (/passwd|shadow|authorized_keys|\.env|config/.test(wanted)) toFifo(`HARVESTED|${ip}|${wanted}`);
                return contents;
            }
            return `cat: ${catMatch[1]}: No such file or directory`;
        }

        if (/\/run\/purple|\/var\/lib\/\.maia|host_bridge|purple|maia/.test(cmd.toLowerCase())) return "No such file or directory";
        if (/^ls\s+\/(host|hostfs|mnt\/host|run\/host)\b/.test(cmd)) return "ls: cannot access requested path: No such file or directory";
        if (/^ls\s+\/\.dockerenv\b/.test(cmd)) return "ls: cannot access '/.dockerenv': No such file or directory";
        if (/^mount\b/.test(cmd)) return `tmpfs on /run type tmpfs (rw,nosuid,nodev,mode=755)\n/dev/nvme0n1p1 on / type ext4 (rw,relatime)\nproc on /proc type proc (rw,nosuid,nodev,noexec,relatime)`;
        if (/^df\b/.test(cmd)) return "Filesystem      Size  Used Avail Use% Mounted on\n/dev/nvme0n1p1   40G   13G   25G  35% /\ntmpfs           1.9G  1.2M  1.9G   1% /run";
        if (/^machinectl\b|^nsenter\b/.test(cmd)) return "Operation not permitted";
        if (/^sudo\s+-l\b/.test(cmd)) return "Matching Defaults entries for ubuntu on prod-api:\n    env_reset, mail_badpass\nUser ubuntu may run the following commands on prod-api:\n    (root) NOPASSWD: /usr/bin/systemctl status app.service";
        if (/^(last|who|w|users)\b/.test(cmd)) return "ubuntu   pts/0        10.42.12.18      Fri May 29 04:13   still logged in";
        if (/^(ip\s+a|ip\s+addr|ifconfig)\b/.test(cmd)) return `2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500\n    link/ether ${profile.mac} brd ff:ff:ff:ff:ff:ff\n    inet ${profile.privateIp}/24 brd 10.42.255.255 scope global eth0`;
        if (/^(ip\s+r|ip\s+route|route\s+-n)\b/.test(cmd)) return `default via ${profile.gateway} dev eth0 proto dhcp\n10.42.0.0/16 dev eth0 proto kernel scope link`;
        if (/^(ss\b|netstat\b)/.test(cmd)) return "tcp LISTEN 0 4096 0.0.0.0:22 0.0.0.0:* users:((\"sshd\",pid=711,fd=3))\ntcp ESTAB 0 0 10.42.12.25:443 10.42.12.31:54820";
        if (/^arp\b/.test(cmd)) return `? (${profile.gateway}) at 02:42:ac:2a:00:01 [ether] on eth0`;
        if (/^ps\b|^top\b/.test(cmd)) return "  PID TTY          TIME CMD\n    1 ?        00:00:02 systemd\n  711 ?        00:00:00 sshd\n 1028 pts/0    00:00:00 bash\n 1042 pts/0    00:00:00 ps";
        if (/^systemctl\b/.test(cmd)) return "  app.service loaded active running application service\n  ssh.service loaded active running OpenBSD Secure Shell server";
        if (/^service\b/.test(cmd)) return " [ + ]  app\n [ + ]  ssh\n [ - ]  unattended-upgrades";
        if (/^journalctl\b/.test(cmd)) return "-- Logs begin at Fri 2026-05-29 03:51:12 UTC --\nMay 29 prod-api systemd[1]: Started application service.";
        if (/^history\b/.test(cmd)) return "    1  ls -la\n    2  systemctl status app\n    3  cat /srv/app/config.yml";
        if (/^ls\b/.test(cmd)) return "app  backups  config.yml  logs  releases";
        if (/^find\b/.test(cmd)) return "/srv/app/config.yml\n/home/ubuntu/.env\n/home/ubuntu/.ssh/authorized_keys";
        if (/^grep\b/.test(cmd)) return "/srv/app/config.yml:credential_ref: owner-vault://decoy/app";
        if (/docker\s+ps/.test(cmd)) return "CONTAINER ID   IMAGE          COMMAND       STATUS        NAMES\n7d12f00dbeef   app:stable     ./server      Up 3 hours    app-web";
        if (/kubectl\b/.test(cmd)) return "The connection to the server localhost:8080 was refused";
        if (/aws\s+sts/.test(cmd)) return "An error occurred (InvalidClientTokenId) when calling the GetCallerIdentity operation: decoy credentials are not valid";
        if (/gcloud\b/.test(cmd)) return "ERROR: (gcloud.auth) No active account selected.";
        if (/169\.254\.169\.254/.test(cmd)) return "instance-id: i-0dec0y00000000000\nrole: app-server-decoy";
        if (/crontab|\/etc\/cron|\/etc\/systemd\/system/.test(cmd)) return "no crontab for ubuntu";
        if (/curl\b|wget\b/.test(cmd)) { toFifo(`ATTACKER_REQUESTED_UPDATE|${ip}|${cmd}`); return "Temporary failure resolving remote resource"; }
        if (/python\s+-c|bash\s+-c|chmod\s+\+x/.test(cmd)) return "permission denied in restricted owner decoy shell";
        return `bash: ${cmd.split(" ")[0]}: command not found`;
    };

    conn.on("data", (data) => {
        buf += data.toString();
        const lines = buf.split(/\r?\n/);
        buf = lines.pop();
        for (const raw of lines) {
            const cmd = raw.trim();
            if (cmd === "") { conn.write(prompt); continue; }
            const out = answers(cmd);
            if (out === "__EXIT__") { conn.end("logout\r\n"); return; }
            conn.write((out || "") + "\r\n" + prompt);
        }
    });

    conn.on("error", () => {});
    setTimeout(() => conn.end(), 120000);
    conn.write(prompt);
}

const server = createServer((conn) => {
    const ip = conn.remoteAddress || "unknown";

    // Loopback is never permanently blocked — used for internal health checks and testing
    const isLoopback = ip === "127.0.0.1" || ip === "::1";

    if (!isLoopback && blocked.has(ip)) { conn.destroy(); return; }

    const hits = (hitCount.get(ip) || 0) + 1;
    hitCount.set(ip, hits);

    if (!isLoopback && hits > BLOCK_THRESHOLD) { blockIP(ip); conn.destroy(); return; }
    if (!isLoopback && hits === BLOCK_THRESHOLD) toFifo(`RATE_LIMITED|${ip}`);

    const active = (connCount.get(ip) || 0) + 1;
    connCount.set(ip, active);
    if (active > MAX_CONNS_PER_IP) { conn.destroy(); connCount.set(ip, active - 1); return; }

    toFifo(`ATTACKER_CONNECT|${ip}`);
    conn.on("close", () => connCount.set(ip, (connCount.get(ip) || 1) - 1));

    if (!fakeHosts.has(ip)) fakeHosts.set(ip, generateFakeIP());

    if (pleiadesRebirthActive()) {
        conn.write(`Connected to ${fakeHosts.get(ip)}\r\n`);
    }
    handleSSH(conn, ip);
});

server.listen(PORT, HOST, () => console.log(`Taygete tarpit on ${HOST}:${PORT}`));
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
        ( echo "TAYGETE_MODE_AGGRESSIVE" >> /run/pleiades/pleiades-nexus_fifo & )
if [[ -f /run/pleiades/attacker_ips ]]; then
            while IFS= read -r ip; do
                [[ -n "$ip" ]] && /usr/local/bin/credential_probe "$ip" &
            done < /run/pleiades/attacker_ips
        fi
        ;;
    passive)   ( echo "TAYGETE_MODE_PASSIVE"   >> /run/pleiades/pleiades-nexus_fifo  & );;
    resurrect) ( echo "TAYGETE_RESURRECT"       >> /run/pleiades/pleiades-nexus_fifo  & );;
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
        {Name: "sandbox", Cmd: exec.Command("bun", "/usr/local/bin/sandbox.js")},
        {Name: "owner_helper_server", Cmd: exec.Command("bun", "/usr/local/bin/owner_helper_server.js")},
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
# 7. Build Bun helper server (unchanged)
# ------------------------------------------------------------
build_bun_owner_helper_server() {
    cat > /usr/local/bin/owner_helper_server.js << 'BUN_HELPER'
#!/usr/bin/env bun
import http from 'node:http';
import { readFileSync } from 'node:fs';

function loadToken() {
    if (process.env.HTTP_TOKEN) return process.env.HTTP_TOKEN.trim();
    try { return readFileSync('/etc/taygete/http_token', 'utf8').trim(); }
    catch { return 'default'; }
}

const HTTP_TOKEN = loadToken();
const PORT = parseInt(process.env.PORT || '18080');

const server = http.createServer((req, res) => {
    const url = new URL(req.url, `http://${req.headers.host || '127.0.0.1'}`);
    if (url.searchParams.get('token') !== HTTP_TOKEN) {
        res.writeHead(403, { 'Content-Type': 'text/plain' });
        res.end('Forbidden');
        return;
    }
    if (url.pathname === '/owner-helper.sh') {
        const helper = readFileSync('/etc/taygete/owner-helper.sh', 'utf8');
        res.writeHead(200, { 'Content-Type': 'text/plain' });
        res.end(helper);
        return;
    }
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('Not found');
});

server.listen(PORT, '127.0.0.1', () => {
    console.log(`Owner helper server on port ${PORT}`);
});
BUN_HELPER
    chmod +x /usr/local/bin/owner_helper_server.js
}

# ------------------------------------------------------------
# 8. Build owner-authorized local helpers
# ------------------------------------------------------------
build_bash_helpers() {
    mkdir -p /etc/taygete /var/lib/.maia/logs
    cat > /etc/taygete/loader.sh << 'LOADER'
#!/bin/bash
set -euo pipefail
echo "Taygete defensive helper is local-only and owner-authorized."
echo "No remote deployment, firewall rewrite, reboot, or persistence action is performed."
LOADER
    chmod +x /etc/taygete/loader.sh

    cat > /etc/taygete/owner-helper.sh << 'HELPER'
#!/bin/bash
set -euo pipefail
LOG_DIR="/var/lib/.maia/logs"
RUN_DIR="/run/pleiades"
mkdir -p "$LOG_DIR" "$RUN_DIR"
printf '%s defensive-helper invoked by %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${SUDO_USER:-$(id -un)}" >> "$LOG_DIR/owner_helper.log"
echo "This owner-authorized helper does not modify firewall policy, reboot the host, or install persistence."
echo "Taygete decoy telemetry is written to $RUN_DIR/pleiades-nexus_fifo."
HELPER
    chmod +x /etc/taygete/owner-helper.sh

    cat > /etc/taygete/remote-install-disabled.sh << 'REMOTE_INSTALL_DISABLED'
#!/bin/bash
set -euo pipefail
echo "Remote installation is disabled in this defensive build. Use owner-approved installation channels."
exit 0
REMOTE_INSTALL_DISABLED
    chmod +x /etc/taygete/remote-install-disabled.sh
}

# ------------------------------------------------------------
# 10. Install service (systemd or screen)
# ------------------------------------------------------------
install_systemd() {
    if ! systemd_usable; then
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
            ( echo "BGP_HIJACK" >> ${PLEIADES_RUN_DIR}/pleiades-nexus_fifo & )
touch ${PLEIADES_RUN_DIR}/pleiades-rebirth_needed
        fi
        if thermal_anomaly; then
            logger -t taygete "Thermal anomaly detected – possible side‑channel attack"
            ( echo "THERMAL_ANOMALY" >> ${PLEIADES_RUN_DIR}/pleiades-nexus_fifo & )
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
    elif [[ "$ENV" == "bare_metal" ]]; then
        pkg_install golang rustc bun screen bc lm-sensors socat openbsd-netcat
    else
        pkg_install golang rustc bun screen bc lm-sensors socat openbsd-netcat
    fi

    ensure_bun

    mkdir -p /etc/taygete /run/pleiades
    host_bridge_capability_report "taygete"
    register_pleiades-swarm_capability "taygete" "deception-tarpit" "sandbox,credential-decoy,anti-recon,owner-helper,taygete-socket"
    HTTP_TOKEN=7282972a7281ab1eb3eac5d85b11d5e0
    [[ "$HTTP_TOKEN" == "7282972a7281ab1eb3eac5d85b11d5e0" ]] && HTTP_TOKEN=$(openssl rand -hex 16)
    export HTTP_TOKEN
    echo "$HTTP_TOKEN" > /etc/taygete/http_token

    build_go_credential_probe
    build_purple_block_script
    build_bun_sandbox
    build_bun_owner_helper_server
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

main

# --- END MAIA EVENT HOOK ---
