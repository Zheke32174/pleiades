# Lean Release Scope

The public release artifact from this repository contains the supported `lean/` defensive runtime, its source-level verification code, and the public documentation needed to review it.

## Included

- `lean/` agents, libraries, policy, units, build helper, verification, and security-property documentation;
- public defensive-architecture documents under `docs/`;
- the lean security CI check and public-history scanner;
- repository legal, security, privacy, contribution, and release-verification files.

## Excluded

The release archive deliberately excludes:

- historical `root.x86_64/` runtime and migration material;
- `experimental/` owner-recovery experiments;
- unintegrated `modos/` and PDK branches or generated artifacts;
- private repositories, private topology, credentials, keys, certificates, evidence, logs, snapshots, databases, queues, or host state;
- a Gentoo stage3, root filesystem, WSL distribution, VM image, OCI image, or running service;
- automatic installation, service enablement, or host mutation.

Repository visibility does not make every historical file a supported release component. The exact archive contents are derived from `release/source-paths.txt`, recorded in the SPDX inventory and build receipt, and checked in CI.

## Deployment boundary

The archive is reviewed source, not a deployment receipt. Build and verification must run inside a disposable or explicitly scheduled Gentoo container before promotion. Host/container creation remains the responsibility of `pleiades-container`.

The stacked MODOS/PDK work remains a separate integration line. It must not be represented as part of this lean release until its authority-continuity chain, live-system gates, and integration review are complete.
