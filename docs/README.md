# SofiaX Purple Team Polyglot Suite

A highly resilient, multi-vector "Purple Team" persistence and auditing suite designed to survive extreme environments and active Tier 1 threat actor interference.

## Architecture
The suite operates on a "Mutual Persistence" or "Ouroboros" model. It consists of a master overseer (`SofiaX.sh`) and seven specialized polyglot modules. 

1.  **SofiaX (The Overseer):** Responsible for initial deployment, dependency fetching (Go, Rust, Bun), and maintaining the integrity of the cluster.
2.  **The Modules (Ava, Beryl, etc.):** Embedded with full Go/Rust/Bun source code, these scripts compile themselves on the fly. They execute specific tasks (like BGP monitoring, Thermal side-channel detection, and Honeypot hosting) while simultaneously acting as the "Immune System" for the overseer.

## Black-Level Defenses (Tier 1 Mitigation)

This suite has been stress-tested against extreme "Black-Level" attacks and incorporates advanced defenses:

*   **Verified Auditing (Anti-Lobotomy):** SofiaX does not blindly trust OS-provided hashing tools. It cross-references `sha256sum` against `openssl dgst -sha256` to detect if the underlying OS binaries have been hijacked.
*   **State-Aware Liveness Probing (Anti-Cryostasis):** The modules don't just check if the daemon PID exists; they analyze the process state. If the daemon is frozen via `SIGSTOP` (State `T`), the scripts will automatically resurrect it.
*   **Reality Anchors (Anti-Mirror):** To defeat mount-namespace hijacking (e.g., `mount --bind` masking the state directories), the scripts hold open File Descriptors (FDs) to canary files. If the path disappears but the FD remains accessible, the script detects the "Mirror Dimension" attack.
*   **Anti-Thundering Herd Resurrection:** If the daemon is killed, the modules use randomized jitter (0-30s) before attempting resurrection to prevent CPU spikes and duplicate deployments.
*   **Multi-Channel EFI Rehydration (Cold Boot Recovery):** Simulates a BIOS-level hook. If the entire filesystem is wiped, the rehydrator will poll both a remote `DEAD_DROP_URL` and a local `USB_DEAD_DROP` for a `RESURRECT` signal to autonomously rebuild the entire suite.

## Repository Structure
*   `/core/`: Contains the master overseer (`SofiaX.sh`) and the daemon shell.
*   `/modules/`: Contains the 7 specialized polyglot scripts (Ava, Beryl, Mariah, Zara, Vera, Artemis, Eris).
*   `/container/`: Contains the EFI rehydration scripts and Gentoo nspawn orchestration tools.

## Deployment
1.  Ensure the environment has basic networking.
2.  Execute `bash core/SofiaX.sh`.
3.  The suite will self-obfuscate, patch the modules, and deploy the resilient daemon.
