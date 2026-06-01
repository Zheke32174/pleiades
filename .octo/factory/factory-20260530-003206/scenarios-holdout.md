# Factory Holdout Scenarios (4 of 20)

### Scenario 3: Initialization Failure Detection
**Behavior:** B1
**Type:** error-handling
**Given:** The system is in a state where the service payload will intentionally fail to start (e.g., port binding conflict).
**When:** The init script is executed.
**Then:** The `systemctl start` command fails, the script detects the failure, and does NOT exit with `0`.
**Verification:** Script exit code is `> 0` and `systemctl is-failed <service>` returns `failed`.


### Scenario 8: maia_crypto Tampered Payload Rejection
**Behavior:** B3
**Type:** error-handling
**Given:** A valid signature for a 1 KiB payload.
**When:** The payload is modified (tampered) by changing a single byte, and passed to the `verify` function alongside the original signature.
**Then:** The verify function detects the mismatch and rejects the payload.
**Verification:** The `verify` command exits `> 0`.


### Scenario 13: Pleiades Swarm Fails Closed on Missing Policy
**Behavior:** B4
**Type:** error-handling
**Given:** The Pleiades Swarm policy JSON file is deleted, corrupted, or unreadable.
**When:** A `.req` file of any class is submitted to the watched directory.
**Then:** The broker falls back to its fail-closed posture and rejects the request.
**Verification:** The decision output indicates `deny`, enforcing the `"default_request_decision": "deny"` rule.


### Scenario 18: Loopback Exemption Validation
**Behavior:** Network Anomaly / Firewall Constraint
**Type:** edge-case
**Given:** The network anomaly service is actively enforcing blocking policies.
**When:** Traffic originates from `127.0.0.1` or `::1`.
**Then:** The traffic is entirely exempt from blocking or rate-limiting rules.
**Verification:** Connection attempts from localhost succeed unconditionally, and firewall rules (`iptables`/`nftables`) explicitly define `isLoopback` exceptions.


