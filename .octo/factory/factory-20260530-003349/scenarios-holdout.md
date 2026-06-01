# Factory Holdout Scenarios (4 of 18)

### Scenario 3: Initialization failure propagation
**Behavior:** B1
**Type:** error-handling
**Given:** A misconfigured Gentoo environment where `systemd` cannot successfully start the Taygete service unit.
**When:** `Taygete.sh` is executed.
**Then:** The `systemctl start` command fails, and `Taygete.sh` must propagate the failure by exiting with a non-zero status code.
**Verification:** Intentionally sabotage the Taygete unit file, run `Taygete.sh`, and assert `echo $?` is > 0. Check the script's output for systemd failure logs.


### Scenario 7: Cryptographic rejection of tampered payloads
**Behavior:** B3
**Type:** error-handling
**Given:** A valid hex-encoded Ed25519 signature for a specific message payload.
**When:** One byte of the message payload is altered, and it is passed to `maia_crypto verify` with the original signature.
**Then:** The verification process must fail and exit with a non-zero status code.
**Verification:** Capture the valid signature, mutate the message string, run `maia_crypto verify <mutated_msg> <signature>`, and assert the exit code is > 0.


### Scenario 11: Pleiades Swarm fail-closed posture
**Behavior:** B4 / Constraint (Default deny)
**Type:** edge-case
**Given:** The Pleiades Swarm broker is running.
**When:** A request file `test_unknown.req` containing an undefined or unlisted request class (e.g., `unknown-action`) is submitted.
**Then:** The broker defaults to a fail-closed posture and outputs a decision file indicating `deny`.
**Verification:** Submit a maliciously crafted or unknown `.req` class. Parse the resulting decision file and assert `decision == "deny"` (or `default_request_decision == "deny"`).


### Scenario 15: Heartbeat bridge vitality
**Behavior:** Constraint (Heartbeat interval)
**Type:** integration
**Given:** The `pleiades-gentoo-heartbeat.sh` script is managing host bridges.
**When:** A container state change occurs (e.g., a service restarts or network state shifts).
**Then:** The bridge status file on the host must be updated to reflect the new state within 10 seconds.
**Verification:** Touch a trigger file simulating a state change. `stat -c %Y` the host bridge status file in a loop. Assert the modification time updates within 10 seconds of the trigger.


