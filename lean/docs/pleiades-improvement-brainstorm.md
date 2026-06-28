# Pleiades — Improvement Brainstorm + Production Forensics — 2026-06-27

Companion to `pleiades-design-review.md` (per-agent) and `pleiades-server-integration.md`.
This file: (1) what OneDrive proves actually broke in production, (2) a broad
improvement brainstorm across 8 categories.

---

## Part 1 — Production forensics (what OneDrive proves)

The previous device's entire home dir is synced to OneDrive. Evidence of how it failed:

- **640 `wsl*` directories** at the OneDrive root — the runaway, quantified. Empty/near-empty
  temp dirs from `mktemp -d`-style calls fired in a crash/restart loop. This is the literal
  artifact of defect #1 (wrong-binary units + `Restart=always`, no rate limit) and Celaeno's
  `while true; systemctl restart`.
- **`pleiades-bak-archive`** — a frozen record of a frantic **6/1–6/2/2026** editing spree:
  - Same files re-backed-up within hours (e.g. `pleiades-regression-lib.sh` twice **44 s apart**;
    `Maia.sh` at 00:14 and 07:21; `Celaeno.sh`, `Taygete.sh`, `Electra.sh`, `Sterope.sh` all
    twice in one morning). Signature of fighting the same bug in circles.
  - `.bak.$(date +%s)` convention (mandated by AGENTS.md) produced dozens of copies — inline
    backups standing in for version control. Even `LICENSE.bak.1781004396` exists — the
    purple→pleiades rename sed touched *everything*.
- **`purple-to-pleiades-rename-archive-20260601` + `Pleiades-rename-backup`** — a mass
  "purple-team" → "pleiades" rename on 2026-06-01. This is almost certainly the origin of the
  corrupted `Description=Pleiades Forensic Description=Purple … Scanner` unit metadata — a
  global sed that doubled lines.
- **`pleiades-workspace`** reveals deployment paths beyond the nspawn clone we have:
  `build-pleiades-vm.sh` / `run-pleiades-vm.sh` (a full **VM** deploy path beside nspawn),
  `pleiades-host-process-sensor.sh`, `pleiades-backup.sh`, `pleiades-factory-tools.sh`,
  `security-baseline.json`, `tool-manifest.json`, `toolchain-catalog.json`, `PLEIADES_MCP.md`.
  → The project sprawled across **three** runtimes (nspawn, VM, Termux phone) at once on a
  5.8 GB box. Over-scope is the root cause behind every specific bug.

**The illusion engine, confirmed in code:** `pleiades-regression.sh` + `-lib.sh` gate every
meaningful test behind `if ! container_up; then skip; return`, and `container_up` keys on
`machinectl show pleiades-dr`. A `--register=no` boot never registers that name, so the real
tests (broker deny-matrix, crypto round-trip, crash-loop budget, port liveness) **skip on every
normal run**, leaving only 8 `bash -n` syntax checks — and `FAIL=0` reports green. "Zero
failures" meant "almost nothing ran."

---

## Part 2 — Improvement brainstorm (8 categories)

### A. Deployment & build — make it reproducible
- **One source of truth for units.** Ship ONE canonical unit set in the repo; delete the
  runtime self-install of `*-omniversal.service`. No first-boot `curl | sh`.
- **Build binaries at image-build time, not first boot.** A `Makefile`/`justfile`:
  extract stage3 → compile every agent binary with **pinned** toolchains
  (use the existing `toolchain-catalog.json`) → install the one unit set → run the regression
  *inside* → emit a versioned `root.x86_64` tarball. Red build = no ship.
- **Kill the `scripts/` vs `/usr/local/bin/` divergence.** `scripts/` = source; build compiles
  to binaries; never two editable copies that drift.
- Consider a declarative build (`mkosi`/OCI image) over imperative bash that mutates itself.

### B. Supervision & anti-runaway — let systemd own it
- **Delete every bespoke supervisor** (the Go respawn loops, `screen -dmS`, and especially
  Celaeno's `nohup … while true; systemctl restart …; sleep 2`).
- Every unit: `Restart=on-failure` + `StartLimitIntervalSec=300` + `StartLimitBurst=5` +
  backoff `RestartSec`. Flap 5×/5 min → unit stops and alerts. **No infinite loops, ever.**
- **mktemp discipline:** all scratch under systemd `RuntimeDirectory=` (`/run/pleiades/tmp`),
  `trap … EXIT` cleanup. This is the direct fix for the 640 `wsl*` dirs.
- A **swarm circuit-breaker:** if N agents are flapping, drop the whole swarm to PASSIVE and
  stop respawning until an owner-signed reset.
- One `pleiades.slice` with a hard `MemoryMax` so the swarm can never starve the DC.

### C. Error handling — kill the illusion
- **Ban blanket `|| true` / `2>/dev/null`.** Replace with a shared `require()`/`try()` that
  logs the failing command + rc to the Nexus and flips the agent to `DEGRADED`.
- **One shared `lib/pleiades-common.sh`** (log, require, nexus_emit, register_capability,
  host-bridge readers). Every agent sources it. Fixes the copy-pasted `ameropege` typo and the
  duplicated host-probe code in one place.
- Each agent writes an **honest status JSON** (`/run/pleiades/state/<agent>.json`:
  `{status, last_error, since}`). Emit `ready` only when every step actually succeeded.

### D. Observability & the Nexus — real, tamper-evident, retained
- Make the Nexus a **real** append-only log: persist to a `chattr +a` file, or just use the
  **systemd journal** with `SYSLOG_IDENTIFIER=pleiades` + structured json. Stop hand-rolling a
  forgeable flat file.
- **Never `journalctl --vacuum-time=1s`** (Atlas's self-erase). Retain ≥30 days; rotate by size.
- **Hash-chain + sign each record** with Maia's Ed25519 (each entry signs `prev_hash`) →
  tamper-evident forensic log. This is the project's actual purpose — make it real.
- Surface Nexus → the **Command Deck** dashboard (see `pleiades-server-integration.md`).

### E. Security model & boundary — defensive, not offensive
- **Read-only host bridge only.** Keep the designed `ro` `/host/*` binds; remove ALL host
  write-backs (`.maia` owner copies) and Alcyone's host-unit installs / `sysctl -w`.
- **Drop Maia's ESP/EFI implant.** Persistence belongs in the signed evidence repo (GitHub),
  not the firmware partition — cleaner and far less risky.
- **Broker = crown jewel:** keep default-deny; make the policy a **Maia-signed** versioned JSON
  the broker verifies on load (reject tampered policy); log every decision to the Nexus.
- **Remove offensive code** (Sterope's TTY-flood/"thrall"). Retaliation turns a defensive box
  into a legal + tactical liability. Posture = **observe → sign → report**, never strike back.
- **Trustworthy triggers:** the `bgp_hijack` (first-seen ASN) and `thermal` (typo-broken)
  heuristics are too flaky to gate containment/rebirth. Heuristics raise **alerts**; destructive
  actions (rebirth) require **Maia-signed owner approval** only.

### F. Testing — make green mean green
- **Fix `container_up`** to use the pid-namespace detection we proved works (find the `systemd`
  whose pid-ns ≠ host), not `machinectl pleiades-dr`.
- **A SKIP is a failed guarantee.** CI passes only if the container actually booted AND every
  in-container test ran AND passed. Disallow `--skip-container` in CI.
- Add the tests that would have caught these bugs:
  1. every shipped unit's `ExecStart` binary exists;
  2. masked-error budget per agent (`grep -c '|| true'` under a cap);
  3. no `/host` or `/mnt/c` **writes**;
  4. no `journalctl --vacuum`;
  5. crash-loop budget per agent (already written — just make it run).
- Run the regression **inside the build** before publishing the image.

### G. Scope — right-size for a 7.7 GB shared box
- **Lean profile first:** Maia + Nexus + Taygete + Celaeno (systemd-native). Add others as
  verified increments.
- **Defer the luxuries:** LLM stack (llama-cli + >1 GB model), RE pipeline, BSD-compat /
  cross-ISA / pkgsrc (Asterope), and the VM build path. Huge surface, low value here.
- Uniform resource caps (`MemoryMax`, `CPUQuota`) on every unit.

### H. Hygiene & consistency
- `#!/usr/bin/env bash`; delete the `PLEIADES_TERMUX_LIB` source lines (no Termux here).
- Fix `load ameropege:` → `load average:` (in the shared lib — fixes all 9 at once).
- Remove hardcoded tokens (Taygete's `HTTP_TOKEN`); generate per-boot, `0600`.
- Use **git** for history, not `.bak.$(date +%s)` inline backups (that churn produced the
  bak-archive sprawl).
- Clean up the 640 `wsl*` dirs (one-time).

---

## Suggested first concrete step
Build the **reproducible build harness** (category A) around the lean profile (category G):
a `Makefile` that compiles Maia + Nexus + Taygete + Celaeno into the container image with the
fixed shared lib (C, H), the one canonical systemd-native unit set (B), and a regression that
actually runs in-container (F). That single harness institutionalizes the fixes so we can't
regress into the old chaos as we reintroduce the rest.
