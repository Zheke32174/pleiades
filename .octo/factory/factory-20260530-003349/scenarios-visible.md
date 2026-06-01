# Factory Visible Scenarios (14 of 18)

### Scenario 1: Initial deployment and service activation
**Behavior:** B1
**Type:** happy-path
**Given:** A clean Gentoo rootfs mounted via systemd-nspawn on WSL2 with root privileges.
**When:** The 8 service initialization scripts (e.g., `Sterope.sh`, `Maia.sh`) are executed for the first time.
**Then:** All scripts complete within 60 seconds each, and `systemctl is-active` returns `active` for all 8 corresponding systemd units.
**Verification:** Time the execution of each script. Run `systemctl is-active <service>` for all 8 services and assert the output is exactly `active`.


### Scenario 2: Idempotent service initialization
**Behavior:** B1
**Type:** edge-case
**Given:** All 8 services are already initialized and running successfully.
**When:** The 8 service initialization scripts are executed a second time.
**Then:** The scripts must exit with code 0 in ≤ 5 seconds per script, without altering the existing configuration or restarting the active systemd units.
**Verification:** Time the execution of the second run. Verify exit codes are 0. Compare the process uptimes (`ActiveEnterTimestamp` from systemctl) before and after the run to ensure units were not restarted.


### Scenario 4: Package manager shim for lm-sensors
**Behavior:** B2
**Type:** integration
**Given:** The execution context of any of the 7 scripts that require `lm-sensors`.
**When:** The scripts invoke their internal package installation logic.
**Then:** The `lm-sensors` package is intercepted by a shim, silently skipped, and never passed to `emerge`, `apt`, or `pacman`.
**Verification:** Run `grep -Ei "emerge.*lm-sensors|apt.*lm-sensors|pacman.*lm-sensors" *.sh`. The result must be exactly zero matches. Verify the shim logic exists and logs/skips the package instead.


### Scenario 5: Toolchain installation compliance
**Behavior:** Constraint (Go/Rust installation)
**Type:** edge-case
**Given:** A clean Gentoo container without Go or Rust installed.
**When:** `Maia.sh` runs to compile the `maia_crypto` binary.
**Then:** The Go toolchain is downloaded and installed via `curl` and tarball extraction. `emerge` is not used for Go.
**Verification:** Search the script source: `grep "emerge.*go" Maia.sh` must return 0 matches. Verify Go is installed in `/usr/local/go` or similar via curl.


### Scenario 6: Cryptographic signature round-trip
**Behavior:** B3
**Type:** happy-path
**Given:** `maia_crypto` is compiled and a valid Ed25519 key pair exists on disk.
**When:** A 1 KiB test message is passed to `maia_crypto sign`, and the resulting signature is passed to `maia_crypto verify` along with the original message.
**Then:** The signature is generated as a hex-encoded string, the verification process exits with code 0, and the entire round-trip completes in ≤ 500ms.
**Verification:** Wrap the sign/verify pipeline in `time`. Assert exit code 0. Assert the signature string matches the regex `^[0-9a-fA-F]+$`.


### Scenario 8: Hexadecimal encoding enforcement
**Behavior:** Constraint (Ed25519 key transport)
**Type:** non-functional
**Given:** The `maia_crypto` binary is actively signing events.
**When:** The signature outputs are written to the event streams and log files.
**Then:** Absolutely no raw binary output is emitted; all cryptographic payloads are strictly hex-encoded.
**Verification:** Inspect the output files using `file` or a hex editor to ensure they contain only ASCII text representations of hex strings, with no unprintable characters.


### Scenario 9: Pleiades Swarm permits allowed operations
**Behavior:** B4
**Type:** happy-path
**Given:** The Pleiades Swarm broker is running, and `/etc/pleiades/pleiades-swarm-policy.json` contains `allowed_request_classes: ["capabilities"]`.
**When:** A request file `test_cap.req` representing a `capabilities` action is dropped into the broker directory.
**Then:** The broker processes the file within 2 seconds and outputs a decision file indicating `allow`.
**Verification:** Create the `.req` file, start a timer, wait for the decision file to appear, stop the timer (must be <= 2s), and `jq` the decision file to assert `decision == "allow"`.


### Scenario 10: Pleiades Swarm denies restricted operations
**Behavior:** B4
**Type:** error-handling
**Given:** The Pleiades Swarm broker is running.
**When:** A request file `test_mod.req` representing a `script-modify` action is submitted to the broker directory.
**Then:** The broker processes the file and outputs a decision file indicating `deny`.
**Verification:** Submit the `.req` file, wait for processing, and parse the resulting decision file to assert `decision == "deny"`.


### Scenario 12: Taygete honeypot concurrent capacity
**Behavior:** Constraint (Taygete concurrent capacity)
**Type:** non-functional
**Given:** The Taygete service (Node.js SSH decoy) is active and listening on port 2222.
**When:** 50 simultaneous SSH connection attempts are initiated against port 2222 by an adversarial recon simulator.
**Then:** The Node.js service does not crash, accepts all connections, and processes the handshakes without dropping the listener.
**Verification:** Use a tool like `nmap`, `hydra`, or a custom bash loop with `nc` or `ssh` to spawn 50 parallel background connections. Verify `systemctl status taygete` shows active/running during and after the test.


### Scenario 13: Service memory footprint enforcement
**Behavior:** Constraint (Memory per service)
**Type:** non-functional
**Given:** All 8 services have been initialized, started, and have reached an idle state for at least 60 seconds.
**When:** The resident set size (RSS) memory consumption is measured for the primary process of each service.
**Then:** No single service exceeds 64 MiB of RSS memory.
**Verification:** Run `ps -o rss= -p <PID>` for each of the 8 main service processes. Assert that every returned value is ≤ 65536 (KB).


### Scenario 14: Pleiades Nexus event stream latency
**Behavior:** Constraint (Pleiades Nexus FIFO latency)
**Type:** non-functional
**Given:** The Pleiades Nexus threat aggregation service is active.
**When:** A simulated threat event is triggered in the system.
**Then:** The event is appended to the Pleiades Nexus FIFO stream within 1 second of the trigger.
**Verification:** Emit a test event, record the high-precision timestamp, tail the FIFO stream, record the timestamp when the event appears, and assert the delta is ≤ 1000ms.


### Scenario 16: Local network loopback exemption
**Behavior:** Constraint (Loopback exemption)
**Type:** integration
**Given:** The network anomaly containment rules are active and blocking suspicious traffic.
**When:** The `pleiades-regression.sh` suite connects to the local services via `127.0.0.1` or `::1`.
**Then:** The traffic is evaluated against the `isLoopback` definition and is explicitly permitted, never blocked by the containment layer.
**Verification:** Inject a strict block-all rule into the anomaly engine. Run `curl 127.0.0.1:2222` (Taygete port) from within the container. Assert the connection is established and not timed out or actively rejected.


### Scenario 17: Bash syntax integrity gate
**Behavior:** Constraint (Bash syntax validation)
**Type:** happy-path
**Given:** The complete source code of all 8 initialization scripts.
**When:** The `bash -n <script>` command is executed against each file.
**Then:** All checks return silently with an exit code of 0, proving there are no syntax errors prior to runtime.
**Verification:** Run `for f in *.sh; do bash -n "$f" || exit 1; done`. Assert the loop completes successfully.


### Scenario 18: Regression suite performance bound
**Behavior:** Constraint (Regression suite runtime)
**Type:** non-functional
**Given:** The Pleiades-Team container is fully operational and idle.
**When:** `pleiades-regression.sh` is executed to validate the deployment.
**Then:** The entire suite of tests completes from start to finish in ≤ 5 minutes.
**Verification:** Run `time ./pleiades-regression.sh`. Assert the `real` execution time output is ≤ 300 seconds.
</external-cli-output>

