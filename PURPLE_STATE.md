# PURPLE STATE — Defense Stack Status

## Last Updated
2026-05-31T05:05:00Z — Sweep Rounds Complete

## Scanner Architecture
- **purple-forensic-scanner.sh** (60s cycle) — Deep heuristic scanner with adaptive thresholds
- **purple-quick-check.sh** (15s cycle) — Transient attack detector (fork bombs, memory spikes, new listeners)
- **purple-forensic-extensions.sh** — Wraps chkrootkit + unhide + auditd + pspy
- **purple-attack-simulator.sh** — 10 attack type simulator
- **purple-coordinated-round.sh** — Integrated smoke test: all attacks in one shot
- **mem-hog.py** — Python memory pressure utility (for testing)

## Detection Coverage (Round 1 Verified)
| Attack Type | Quick-Check | Forensic Scanner |
|---|---|---|
| Fork Bomb (proc spawn) | RAPID_PROC_SPAWN ✅ | PROC_SPIKE ✅ |
| Memory Pressure | RAPID_MEM_ALLOC ✅ | MEMORY_SPIKE ✅ |
| Auth Brute Force (signals) | — | AUTH_FAIL_SPIKE ✅ |
| Rogue Listener | NEW_LISTENER_QUICK ✅ | UNKNOWN_LISTENER ✅ |
| FD Exhaustion | — | FD_SPIKE ✅ |
| Promiscuous Mode | — | PROMISCUOUS_MODE ✅ |
| /tmp File Burst | — | TMP_FILE_BURST ✅ |

## Three-Tier Tool Strategy
- **T1 (installed)**: pspy, chkrootkit, unhide, auditd
- **T2 (deferred — too heavy)**: osquery, suricata, samhain, aide, sysdig
- **T3 (future — host bridge)**: snort4, bettercap, falco

## Known Gaps
- Auth detection uses signal files (/run/purple/decisions/*.auth_alert) not journald
- ARP poisoning requires NET_ADMIN (unavailable in nspawn)
- Kernel module detection requires insmod (unavailable in nspawn)
- Container has no /var/log/auth.log (systemd journal only, timestamp skew)
- Memory pressure <100MB is below noise floor against 5.9GB RAM

## Thresholds (Tuned)
- Proc delta: >20 (quick-check), >30 + abs 500 (scanner)
- Mem delta: >8% (quick-check), >15% (scanner), abs >70%
- FD delta: >80 (scanner), abs >80%
- Auth new fails: >2 (scanner)
- /tmp new files: >15 (scanner)

## Services
- purple-quick-check.service: active (CPUQuota=20%, MemoryMax=30M)
- purple-forensic-scanner.service: active

## Repos
- Zheke32174/pleiades — Suite repo with devcontainer, CI/CD
- Zheke32174/underhall — Infra repo with installation scripts
