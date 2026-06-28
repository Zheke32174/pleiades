# Pleiades Agent Design Review — 2026-06-27

Full per-agent review of the 9 star agents, how they deploy, and a prioritized
plan to improve each. Companion to `pleiades-server-integration.md` and
`previous-device-inventory.md`. Chat summary is a condensation of this file.

---

## TL;DR — 5 systemic defects (apply to nearly every agent)

1. **Every shipped unit points at the wrong binary.** The units in
   `pleiades-container/systemd/system/*.service` set `ExecStart=/usr/local/bin/<x>_hivemind`,
   but the scripts build `<x>_pleiades-swarm` (or self-install *different* units at
   runtime). With `Restart=always` and **no rate limit**, each one crash-loops forever.
   **This is the runaway** — crash-loop storms, amplified by Celaeno's
   `while true; do systemctl restart …; sleep 2; done`, are what produced the
   "million wsl* folders." As packaged, the swarm cannot actually start.

2. **Pervasive error-masking = the "illusion of working."** Masked-error counts:
   Atlas **120×`|| true` + 88×`2>/dev/null`**, Maia **144**, Electra ~70+,
   Asterope 40+, Taygete ~21, Alcyone/Celaeno/Sterope ~20–25 each. Builds, nft rules,
   socket binds and installs fail silently, then the agent logs `ready/active`.
   They report success they never achieved.

3. **The container boundary is fiction.** Every agent probes `/mnt/c`, `/host`,
   `docker.sock` and writes `/var/lib/.maia` "owner copies." The agent that is
   *supposed* to be read-only recon (Alcyone) actively writes host paths, installs
   host systemd units, and mutates host sysctl. Maia writes a signed persistence
   implant to the EFI System Partition. Host contamination is by-design here.

4. **Runtime self-assembly.** Agents `curl | sh` Go/Rust/Bun toolchains and write
   their own systemd units at runtime — non-reproducible, the opposite of the clean
   stage3 substrate we just built. Result: two divergent copies of every unit
   (shipped vs self-written) that drift.

5. **Two agents are offensive; one erases its own evidence.** Sterope writes
   TTY-flood/harassment payloads aimed at "attacker IPs." Atlas's Nexus
   "append-only" log is a plain file it then wipes with `journalctl --vacuum-time=1s`.
   Plus shared cruft: a copy-pasted `load ameropege:` awk typo in **every** agent
   (thermal load always parses empty → flaky triggers), Termux shebangs
   (`#!/data/data/com.termux/...` — breaks on Gentoo), and Taygete's hardcoded
   `HTTP_TOKEN=7282972a…`.

### What genuinely works (worth keeping)
- **Maia's Ed25519 keygen/sign/verify** — real crypto, the trust root.
- **Taygete** actually binds `:2222` and logs attacker sessions.
- Electra/Alcyone/Celaeno/Sterope/Asterope **do compile real Go/Rust/Bun binaries**
  (not stubs) — they're just mis-wired, masked, and host-contaminating.
- **Merope's snapshot/restore is real and signature-gated** (resurrect requires a
  signed owner signal).

---

## Deployment model

- `pleiades-setup.sh` writes operator config only (`/etc/pleiades/operator.conf` from
  the GitHub identity; creates the private evidence repo + dead-drop). It does **not**
  install the agent binaries — each agent script self-builds + self-installs at runtime.
- Intended model: `root.x86_64/scripts/<Name>.sh` → installed to `/usr/local/bin/<name>_hivemind`
  → run as a systemd service **inside the container**, grouped under `pleiades.target`.
- Reality: the scripts build `*_pleiades-swarm` and write their own `*-omniversal.service`
  units, so the shipped `*_hivemind` units never match what exists.

### Unit-file bugs (visible without reading any agent)
- `After=/Requires=pleiades-nexus-omniversal.service` / `pleiades-atlas-omniversal.service`
  reference units that don't exist (actual: `pleiades-nexus.service` / `pleiades-atlas.service`)
  → ordering silently ignored.
- Corrupted metadata: `Description=Pleiades Forensic Description=Purple Forensic & Heuristic
  Anomaly Scanner Heuristic Anomaly Scanner` (sed-doubling) in forensic-scanner + telemetry units.
- `Restart=always` with no `StartLimitIntervalSec` / `StartLimitBurst` anywhere.

---

## Per-agent reports

### Maia — silent overseer; Ed25519 owner-escrow key custody, evidence signing
- **Deploy:** `pleiades-maia.service` → `/usr/local/sbin/maia_daemon.sh`, `Restart=always`.
- **Does (real):** Builds `maia_crypto` (Go): `ed25519.GenerateKey/Sign/Verify`, keys at
  `/var/lib/.maia/keys/ed25519.{priv,pub}`. Owner-escrow USB/dead-drop signals are
  genuinely signature-verified (`ed25519.Verify` gates `pleiades-rebirth_needed`).
  Owner-escrow persistence, dormancy protocol, AES-256 payload decrypt.
- **Issues:** **144 masked-error sites** (most of any agent) — the real crypto core is
  buried in `2>/dev/null || true`. Host contamination (`/host`, `/mnt/c`, docker.sock,
  `.maia` owner copy). **Writes a signed EFI-capsule persistence implant to the ESP**
  (`$esp/EFI/.$(openssl rand -hex 6)`) from inside the container — host-level persistence,
  boundary violation. Termux shebang.
- **Top improvements:** 1) Keep the Ed25519 core; strip the 144 masks around it so key/escrow
  failures surface. 2) Remove the ESP implant + host probing — persistence belongs in the
  signed evidence repo, not the firmware partition. 3) Fix shebang; isolate crypto into a
  small audited module the other agents call.
- **Verdict:** half-works — real crypto core, buried in masking + an ESP implant.

### Taygete — SSH honeypot (:2222) + credential/recon logger
- **Deploy:** Ships `pleiades-taygete.service` → `/usr/local/bin/taygete_hivemind` (missing);
  script writes `taygete-omniversal.service` → `taygete_pleiades-swarm`. `Restart=always`, `RestartSec=1`.
- **Does (real):** Genuinely binds — Bun `server.listen(2222,"0.0.0.0")` serving a fake
  Ubuntu shell, classifies + logs recon/commands/creds to the FIFO. Not illusion.
- **Issues:** ~21 masked-error sites. `host_bridge_capability_report` scans
  `/mnt/c/Windows/System32`, `/host`, docker.sock. **Hardcoded `HTTP_TOKEN=7282972a…`**.
  nc-fallback `while true; … sleep 0.1` tight spinner; Go supervisor respawns every 2s,
  no cap. `ameropege` typo. Two competing units / binary names.
- **Top improvements:** 1) Drop host-path probing; stay in-container. 2) Remove hardcoded
  token; reconcile to one unit + one binary name. 3) De-mask; add backoff to the nc loop.
- **Verdict:** works — but contaminates host and over-masks.

### Electra — honeypot/deception (decoy services, false-flag targets)
- **Deploy:** `pleiades-electra.service` → `/usr/local/bin/electra_hivemind` (script never
  builds it — builds `sysmon-daemon`, installs `machine-runtime-monitor.service`). Mismatch
  → unit dead on arrival. `Restart=always`, `RestartSec=5`, 512M/50% CPU.
- **Does (real):** Compiles real Go `sysmon-idle`, Rust `harvester`, Bun `lich.js`, Go
  supervisor. Decoys partly real (`/etc/imtherealsparticus`, kernel blackhole routes) BUT
  the credential "harvest" greps honeypot logs that **nothing here ever creates** — no SSH
  listener is ever bound. The advertised listener is illusory.
- **Top improvements:** 1) Fix unit/binary mismatch. 2) Actually bind the honeypot or stop
  logging it as deployed. 3) De-mask; fix `SYSMON-IDLE_INTERVAL=` (invalid bash) + shebang;
  gate `/mnt/c` access.
- **Verdict:** half-works — real binaries, honeypot listener is illusion.

### Alcyone — *supposed* read-only host-bridge recon
- **Deploy:** `pleiades-alcyone.service` → `/usr/local/bin/alcyone_hivemind` (script builds
  `alcyone_pleiades-swarm` → name mismatch, won't start). Self-installs `alcyone-omniversal.service`,
  `Restart=always`, `RestartSec=1`.
- **Does (real):** Compiles a Go multi-port honeypot, Rust conntrack scraper, bash forensics
  detector, socat/nc command socket, Go supervisor. This is an **active** agent, not recon.
- **Issues:** **READ-ONLY VIOLATED** — writes `/run/pleiades/attacker_ips`,
  `touch …/pleiades-rebirth_needed`, `/var/lib/.maia/…`, installs host units +
  `systemctl enable/start`, mutates host via `sysctl -w`, reads `/proc/1/root`, `cmd.exe`,
  `/mnt/c/Windows`. ≥18 masked errors. Hardcoded fake banners; duplicate case arms;
  `ameropege` typo; multiple unbounded `while true`.
- **Top improvements:** 1) Fix the binary name or it never runs. 2) Strip all host writes +
  active countermeasures → emit recon **state only**. 3) De-mask; fix typo + dup case arms.
- **Verdict:** illusion — wrong binary, masked errors, violates read-only.

### Celaeno — swarm watchdog (liveness, restart, hot-patch)
- **Deploy:** `pleiades-celaeno.service` → `/usr/local/bin/celaeno_hivemind`, `Restart=always`,
  `RestartSec=5`. Builds Go supervisor + Go health_monitor, Rust hotpatch, Bun cmd_processor.
- **Does (real):** Real liveness via `pgrep -f` / `systemctl is-active` / `screen -ls`; on
  "dead" runs an installer to "regenerate."
- **Issues:** **Restart storm** — health loop every 10s calls `regenerate()` with no backoff,
  no counter, no cap; a component whose installer doesn't satisfy `pgrep` reinstalls every 10s
  forever. **`hot_patch_watchdog_suspend()` spawns an unkillable
  `nohup … while true; do systemctl restart alcyone-watchdog taygete-watchdog; sleep 2; done`.**
  ~24 masked errors; every regenerate ignores its exit code. Host probing; `sysctl -w`.
- **Top improvements:** 1) Per-component restart budget + exponential backoff + circuit breaker;
  **delete the nested `while true; systemctl restart`.** 2) De-mask; check exec errors.
  3) Hand liveness/restart to systemd (`Restart=on-failure` + `StartLimitIntervalSec/Burst`).
- **Verdict:** half-works — real checks, storm-prone restart engine.

### Sterope — orchestrator / threat-scoring coordinator
- **Deploy:** **NO shipped unit.** Self-installs `atlas-omniversal.service` →
  `atlas_pleiades-swarm` at runtime. So Sterope itself is never deployed by the container.
- **Does (real):** Env detect, builds 3 Go binaries + 2 bash helpers, registers capability
  files, tails a FIFO for a threat score, switches modes via `taygete.sock`/`alcyone.sock`.
- **Issues:** **Offensive** — `build_go_thrall` writes TTY-flood scripts to attacker IPs
  ("BOBBY LONG" banner): retaliation, not defense. Host-bridge `/mnt/c` `/host` recon +
  `.maia` owner copy + hidden `_maia.sock` hook. ~25 masked errors. FIFO is a plain `touch`
  file read in 1s spin loops (not `mkfifo`). `wait_for … 2s` always `return 0`. `ameropege` typo.
- **Top improvements:** 1) **Delete the thrall/TTY-flood + host-bridge recon.** 2) Ship a real
  `pleiades-sterope.service`; stop runtime self-install + curl-pipe. 3) De-mask; use real `mkfifo`.
- **Verdict:** half-works — runs, but offensive and undeployed.

### Merope — threat detection + "rebirth" (snapshot restore)
- **Deploy:** `pleiades-rebirth.service` → `/usr/local/bin/rebirth_hivemind`; script builds
  `pleiades-rebirth_pleiades-swarm` + `pleiades-rebirth_keeper` + `beacon.sh`, self-installs
  `pleiades-rebirth-omniversal.service`. Binary mismatch → shipped unit dead.
- **Does (real):** `beacon.sh` `while true` (7200s) waits for a **signature-gated** resurrect
  signal (checks `ed25519.pub`) then restores from an AES-256 encrypted state snapshot. The
  destructive path is snapshot-restore, **not** from-scratch wipe — no `rm -rf /`, no mkfs, no
  efivar writes. Less destructive than feared.
- **Issues:** **Flaky triggers** — `bgp_hijack_detected` (trusts first-seen ASN) and
  `thermal_anomaly` (broken by `ameropege` typo) `touch …/pleiades-rebirth_needed`. 50 masked
  errors. Runtime unit self-install. Termux shebang.
- **Top improvements:** 1) Keep signature-gated restore; gate the `rebirth_needed` *trigger*
  behind a signed signal too, not flaky heuristics. 2) Fix the binary name + ship the unit.
  3) De-mask; fix the `ameropege` parse.
- **Verdict:** half-works — real signed restore, flaky triggers + binary mismatch.

### Atlas — Nexus containment + append-only event log
- **Deploy:** `pleiades-atlas.service` → `/usr/local/bin/atlas_hivemind` — **this binary is
  never built anywhere in the repo**, so the unit crash-loops forever. Script instead installs
  `containment_controller` via `pleiades-nexus.service`.
- **Does (real):** Nexus "FIFO" is a **plain file** (`touch …_fifo`, no `mkfifo`), `>>`-appended,
  **not** append-only (no `chattr +a`) → forgeable. `archiveLogs()` then runs
  `journalctl --vacuum-time=1s`, **destroying the evidence it just archived.** Containment
  parses `conntrack -L` and adds nft set elements — but the nft `inet filter` table is never
  created, so the adds silently fail.
- **Issues:** Orchestrator binary absent. **120 `|| true` + 88 `2>/dev/null`.** Host writes
  (`/host`, `/mnt/c`, `.maia`, reads host `powershell.exe`). Termux shebang; `ameropege` typo;
  `asterope`/`alien` "not-built-yet" placeholders.
- **Top improvements:** 1) Build/ship the real orchestrator binary (or point the unit at
  `containment_controller`). 2) Make Nexus a real `mkfifo` + `chattr +a` log; **drop the
  self-wipe.** 3) Create the nft table/set before adding; check exit codes.
- **Verdict:** illusion — orchestrator absent, containment silent no-ops, self-erasing log.

### Asterope — BSD compat + .pkg→.deb/.tbz2 cross-OS/ISA package builder ("ninth sister")
- **Deploy:** No pre-staged unit; writes `asterope-bsd-compat.service` at runtime →
  `/usr/local/bin/asterope_pleiades-swarm`, `Restart=on-failure`, `RestartSec=15`, 256M/25%.
- **Does (real):** Installs `alien-bsd`, FreeBSD strat via `brl import`, QEMU bsd-user, pkgsrc
  to `/opt/pkg`, a Go converter daemon watching `/run/pleiades/bsd-convert/inbox`, cross-ISA
  (box64/qemu) + wasmtime/jco.
- **Issues:** Termux shebang breaks startup. Host-bridge `/mnt/c` `/host` probing + `.maia`
  owner copy. **40+ masked errors** — every build step `|| true` then logs
  `all_steps_complete` regardless. `seen` map grows unbounded; per-file goroutine, no cap.
- **Top improvements:** 1) Fix shebang; drop Termux source. 2) Track real per-step success;
  gate the "ready" event on it. 3) Remove host-bridge probing; bound the goroutine fan-out.
- **Verdict:** half-works — real pipeline, masks failures, shebang breaks startup.

---

## Improvement plan

### Cross-cutting fixes (do once, apply to all)
1. **One canonical binary name per agent = the unit's ExecStart.** Ship the unit in the
   container tree. Stop runtime self-install + `curl | sh`.
2. **No crash-loop storms:** `Restart=on-failure` + `StartLimitIntervalSec`/`StartLimitBurst`;
   hand liveness to systemd; delete Celaeno's `while true; systemctl restart`.
3. **De-mask:** replace blanket `|| true` / `2>/dev/null` with checked errors that log and feed
   an honest status; gate every "ready/active" event on actual success.
4. **Seal the boundary:** remove all `/mnt/c` `/host` `docker.sock` probing, the `.maia` owner
   copies, and Maia's ESP implant. Read host telemetry only through ONE explicit read-only mount.
5. **Reproducible build:** bake toolchains + compiled agent binaries into the container image.
6. **Hygiene:** `#!/usr/bin/env bash`; fix the `ameropege` typo; remove hardcoded tokens; remove
   the offensive TTY-flood; real `mkfifo` + `chattr +a` for the Nexus log.

### Lean reintroduction order (one at a time, each verified for real)
1. **Maia** — crypto + policy trust root (mostly real). Clean first.
2. **Atlas/Nexus** — the real append-only event log everything reports into. Fix FIFO + drop self-wipe.
3. **Taygete** — first real sensor (already binds :2222).
4. **Celaeno** — reborn as systemd-native, not a restart loop.
5. Then **Electra, Alcyone (de-fanged to read-only), Merope, Sterope (de-offensified), Asterope**
   as later increments.
