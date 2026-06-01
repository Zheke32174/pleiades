# Factory Visible Scenarios (16 of 20)

### Scenario 1: First Run Service Initialization
**Behavior:** B1
**Type:** happy-path
**Given:** Root access in the Gentoo rootfs with systemd as PID 1, and the script has not been run previously.
**When:** Any of the 8 init scripts is executed for the first time.
**Then:** The service unit is created, configured, and started successfully within 60 seconds.
**Verification:** `systemctl is-active <service>` returns `active` and script execution time is ≤ 60 seconds.


### Scenario 2: Idempotent Second Run
**Behavior:** B1
**Type:** happy-path
**Given:** A service is already initialized and active from a previous successful run.
**When:** The init script is executed for a second time.
**Then:** The script detects the existing state, skips redundant setup, and completes in ≤ 5 seconds.
**Verification:** Script exit code is `0`, execution time is ≤ 5s, and systemd journal shows no unit restart events triggered by the script.


### Scenario 4: Bash Syntax Compliance
**Behavior:** Pre-deployment constraint
**Type:** happy-path
**Given:** The source code of all 8 initialization scripts.
**When:** `bash -n <script>` is executed for each script in the suite.
**Then:** The syntax check passes silently without any parsing errors.
**Verification:** Exit code is `0` for all 8 files.


### Scenario 5: Package Manager lm-sensors Exclusion
**Behavior:** B2
**Type:** edge-case
**Given:** The source code of the 7 scripts that require `lm-sensors`.
**When:** A static analysis is performed on the package manager invocation lines.
**Then:** `lm-sensors` is handled exclusively via a no-op shim and is never passed to `emerge`.
**Verification:** `grep -E "emerge.*lm-sensors" *.sh` returns 0 matches across the repository.


### Scenario 6: Go Toolchain curl-only Installation
**Behavior:** B1 (Go/Rust constraint)
**Type:** non-functional
**Given:** `Maia.sh` needs to compile `maia_crypto`.
**When:** The script attempts to install the Go toolchain.
**Then:** Go is downloaded and extracted via `curl` and `tar`, explicitly bypassing the `emerge` package manager.
**Verification:** `grep "emerge.*go" Maia.sh` returns 0 matches, and Go is successfully installed in the target path.


### Scenario 7: maia_crypto Valid Signature Round-Trip
**Behavior:** B3
**Type:** happy-path
**Given:** `maia_crypto` binary is compiled and an Ed25519 key pair exists.
**When:** A known 1 KiB payload is signed with the private key, and the resulting signature is passed to the verify function with the public key.
**Then:** The signature is generated successfully and the verify function accepts it.
**Verification:** The `verify` command exits `0`.


### Scenario 9: Ed25519 Hex-Encoded Transport
**Behavior:** B3 (Ed25519 transport constraint)
**Type:** integration
**Given:** `maia_crypto` signs a payload or exports a key.
**When:** The output is captured and inspected.
**Then:** The output is strictly hex-encoded to ensure wire-safety.
**Verification:** Regex validation confirms the output string contains only `[0-9a-fA-F]` characters, and no raw binary data is emitted.


### Scenario 10: maia_crypto Performance Latency
**Behavior:** B3 (Latency constraint)
**Type:** non-functional
**Given:** The `maia_crypto` binary and an initialized Ed25519 key pair.
**When:** A 1 KiB message is signed and subsequently verified.
**Then:** The entire round-trip operation (sign + verify) completes within the latency budget.
**Verification:** Measured wall-clock time for the round-trip is ≤ 500ms.


### Scenario 11: Pleiades Swarm Allows Permitted Request
**Behavior:** B4
**Type:** happy-path
**Given:** The Pleiades Swarm broker is running and the policy JSON explicitly lists `capabilities` in `allowed_request_classes`.
**When:** A `.req` file for the `capabilities` class is submitted to the watched directory.
**Then:** The broker processes the file and generates an explicit allow decision.
**Verification:** The resulting decision file contains an `allow` status.


### Scenario 12: Pleiades Swarm Denies Restricted Request
**Behavior:** B4
**Type:** happy-path
**Given:** The Pleiades Swarm broker is running and the policy JSON lists `script-modify` in `denied_request_classes`.
**When:** A `.req` file for the `script-modify` class is submitted to the watched directory.
**Then:** The broker processes the file and generates an explicit deny decision.
**Verification:** The resulting decision file contains a `deny` status.


### Scenario 14: Pleiades Swarm Broker Decision Latency
**Behavior:** B4 (Latency constraint)
**Type:** non-functional
**Given:** The Pleiades Swarm broker is idle.
**When:** A `.req` file is written to the monitored directory.
**Then:** The broker detects, parses, and decides on the request rapidly.
**Verification:** Timestamp difference between `.req` file creation and decision file creation is ≤ 2.0 seconds.


### Scenario 15: Taygete SSH Concurrent Capacity
**Behavior:** Taygete.sh (Taygete constraint)
**Type:** non-functional
**Given:** The Taygete SSH honeypot is active on port 2222.
**When:** 50 simultaneous SSH probe connections are initiated in parallel against the port.
**Then:** The service handles all 50 connections without crashing, dropping, or restarting.
**Verification:** `systemctl is-active taygete` remains `active`, the system journal shows no OOM kills, and all 50 connections are logged.


### Scenario 16: Pleiades Nexus FIFO Write Latency
**Behavior:** Atlas.sh (Pleiades Nexus constraint)
**Type:** integration
**Given:** The Pleiades Nexus containment layer is active.
**When:** A threat event is triggered by a sensor service.
**Then:** The event is serialized and appended to the Pleiades Nexus event FIFO stream in near-realtime.
**Verification:** Time elapsed between the event trigger and the successful FIFO append is ≤ 1.0 second.


### Scenario 17: Service Idle Memory Footprint
**Behavior:** Container Resource Constraint
**Type:** non-functional
**Given:** All 8 services have been successfully initialized and are currently in an idle state.
**When:** The RSS memory usage of each service's primary process is sampled.
**Then:** The memory footprint remains strictly within the budgeted limits.
**Verification:** `ps -o rss -p <PID>` reports ≤ 65536 KB (64 MiB) for every individual service.


### Scenario 19: Container Heartbeat Bridge Update
**Behavior:** Heartbeat Constraint
**Type:** integration
**Given:** The `pleiades-gentoo-heartbeat.sh` bridge is running between WSL2 and the container.
**When:** A measurable state change occurs inside the container.
**Then:** The bridge status file is updated to reflect the new state to prevent the container from appearing dead.
**Verification:** The status file modification timestamp is updated within ≤ 10 seconds of the state change.


### Scenario 20: Regression Suite Runtime Limit
**Behavior:** CI/CD Constraint
**Type:** non-functional
**Given:** The complete Pleiades-Team container stack is active.
**When:** The `pleiades-regression.sh` test suite is executed.
**Then:** The entire suite completes testing without hanging or timing out.
**Verification:** Measured execution time (`time ./pleiades-regression.sh`) is ≤ 5 minutes (300 seconds).
</external-cli-output>

