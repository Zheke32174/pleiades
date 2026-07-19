# Privacy and Local Data

Pleiades is self-hosted defensive research software. This repository does not operate a hosted telemetry service and the lean release contains no user data, credentials, event records, or runtime state.

## Runtime data

A deployed lean runtime may create local operational data such as:

- connection and decoy observations;
- Nexus spool, inflight, and signed-ledger records;
- component status files;
- encrypted snapshots, signatures, and recovery metadata;
- operator configuration and locally generated signing material.

These records can contain hostnames, addresses, timestamps, service observations, and other sensitive evidence. The operator is responsible for lawful collection, retention, access control, backup, and deletion.

## Network behavior

The release archive itself performs no network request. Individual deployed services may listen on explicitly configured defensive or decoy sockets. Private-repository and recovery integrations require separate operator configuration and credentials and are not bundled in the release.

## Retention and deletion

Do not delete evidence merely to conceal activity. For ordinary lab teardown, stop and disable the deployed units, preserve any evidence or recovery material required by policy, then remove the installed program files and local state through the operator's reviewed system-management process.

No generic destructive uninstall script is provided by this repository. The release is source and does not claim ownership of the surrounding Gentoo container, host, private archives, or offsite recovery plane.

## Public reports

Do not put real event data, credentials, private topology, personal information, or third-party host details in public issues. Use GitHub Security Advisories for security reports and provide only the minimum reproducer required.
