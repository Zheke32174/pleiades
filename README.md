# Pleiades

Pleiades is an owner-operated defensive research system for deception services, host telemetry, tamper-evident evidence, recovery testing, and bounded defensive automation.

The supported release component is the clean `lean/` runtime for a reviewed Gentoo `systemd-nspawn` lab. Historical code remains visible for migration and provenance, but it is not bundled in the lean release and is not the recommended deployment path.

Pleiades is not intended for unauthorized deployment, credential theft, lateral movement, retaliation, or reconnaissance on systems you do not own or administer.

## Release status

Version `0.2.0` is the first proposed verified **lean source** release.

The release artifact is deliberately narrow. It contains the lean runtime, its direct verification and security contracts, and public documentation. It is **not**:

- a Gentoo stage3, root filesystem, WSL distribution, OCI image, VM image, or running service;
- an evidence archive, credential bundle, signing-key bundle, private topology, or host configuration;
- the historical `root.x86_64/` runtime;
- the `experimental/` recovery material;
- the still-stacked MODOS/PDK authority implementation.

See [RELEASE_SCOPE.md](RELEASE_SCOPE.md) for the exact boundary.

## Download and verify

From GitHub Releases, download all four assets for the same version:

```text
pleiades-lean-0.2.0.tar.gz
pleiades-lean-0.2.0.spdx.json
pleiades-lean-0.2.0.build-receipt.json
SHA256SUMS.txt
```

Verify before extraction:

```bash
sha256sum -c SHA256SUMS.txt
```

The build receipt records the exact repository commit, source-scope digest, included file count, source timestamp, archive and SPDX hashes, and explicit exclusions. The archive is built twice in CI and must be byte-identical.

## Requirements

The lean source expects:

- a reviewed Gentoo Linux container using systemd;
- Bash, OpenSSL, and standard core utilities;
- root only for installation inside that container;
- explicit operator review before enabling any socket, service, or timer;
- a separate host/container lifecycle supplied by [`pleiades-container`](https://github.com/Zheke32174/pleiades-container).

The source release does not create the container, install a Gentoo stage3, start services, or modify the host.

## Architecture

```text
Sensor and deception plane
        |
Authenticated event intake
        v
Evidence plane -> signed ledger -> independent archive
        |
Knowledge and retrieval plane
        |
Non-authoritative cognitive plane
        |
Typed capability proposals
        v
Deterministic authority broker
        |
Authoritative host kernel and services
```

The current lean container is a staging substrate for this separation. The host remains deterministic and must continue operating when the cognitive plane is unavailable. AI workers may interpret, correlate, retrieve, prioritize, and propose; they do not receive ambient host authority.

See [docs/DEFENSIVE_ARCHITECTURE.md](docs/DEFENSIVE_ARCHITECTURE.md) for the target trust-plane design.

## Lean runtime

`lean/` enforces:

- one canonical executable and systemd unit per component;
- no runtime self-install or `curl | sh` toolchain assembly;
- systemd-owned supervision and bounded restart behavior;
- no in-process infinite polling loops;
- hardened service sandboxes and a shared resource slice;
- explicit failures rather than masked success;
- unique event IDs and a hash-chained, Ed25519-signed Nexus ledger;
- observe-first defensive behavior;
- separately guarded recovery actions.

| Component | Current role |
|---|---|
| Maia | Key initialization, checkpointing, and Nexus sealing |
| Nexus | Tamper-evident ledger verification |
| Taygete | Socket-activated SSH deception sensor |
| Electra | Socket-activated HTTP and telnet decoys |
| Alcyone | Read-only listener and connection posture |
| Celaeno | systemd failure-alert recording |
| Merope | Encrypted and signed snapshots with a separate restore guard |
| Sterope | Observe-only threat scoring and posture summary |

Detailed runtime documentation lives in [lean/README.md](lean/README.md).

## Review and install

Extract the verified archive into a review directory. Run source-level checks before copying it into the container:

```bash
bash -n lean/agents/*/*.sh lean/ops/*.sh lean/build.sh
bash ci/check-lean-security.sh lean
```

Inside the booted Gentoo container, place the reviewed source at a stable location such as `/opt/pleiades-build`, then install:

```bash
cd /opt/pleiades-build
sudo bash lean/build.sh
```

`lean/build.sh` installs files and runs `systemctl daemon-reload`; it does not enable or start the runtime. It refuses missing unit targets, agents with infinite loops, `Restart=always`, evidence-vacuuming commands, runtime `curl | sh`, and services outside `pleiades.slice`.

After reviewing the installed units and intended listening surfaces, enable only the components approved for that lab. The example release-track set is documented in [lean/README.md](lean/README.md).

## Verify

Static source verification:

```bash
bash ci/check-lean-security.sh lean
```

Full live verification inside the scheduled lab environment:

```bash
bash lean/ops/verify-full.sh
```

The live verifier exercises trust-root initialization, socket sensors, Nexus sealing, sandbox behavior, failure alerts, snapshot guards, threat scoring, and ledger validation. Any failed assertion exits nonzero.

A green source-release workflow is not a deployment receipt. Promotion still requires a freshly built disposable container and reviewed live verification output.

## Update and rollback

Treat each release as an immutable source snapshot:

1. verify the new archive and receipt;
2. extract it into a new versioned review directory;
3. run static checks before installation;
4. preserve the previous reviewed source tree and installed configuration;
5. install during a scheduled maintenance window;
6. run full verification before retiring the previous source snapshot.

The current installer is idempotent but does not provide transactional package-manager rollback. Container snapshots and independently retained evidence/recovery material should provide the rollback boundary. Do not overwrite the only known-good source tree or recovery copy.

## Stop and remove

This repository does not claim ownership of the surrounding Gentoo container or host and therefore does not provide a generic destructive uninstall command.

For a reviewed lab teardown:

1. stop and disable the Pleiades services, sockets, and timers through systemd;
2. preserve evidence, keys, snapshots, and recovery records required by policy;
3. inspect the installed file list from `lean/build.sh`;
4. remove those program and unit files through the operator's normal system-management process;
5. run `systemctl daemon-reload`;
6. delete the container only through the separately reviewed `pleiades-container` lifecycle.

Do not erase evidence to conceal activity. See [PRIVACY.md](PRIVACY.md) for data handling and retention boundaries.

## Development lines

The public repository currently has two distinct review lines:

- the lean defensive runtime and this source-release checkpoint;
- the stacked MODOS/PDK authority chain, which remains separate until its authority-continuity, integration, and live-system gates are complete.

A release of the lean runtime must not imply that the MODOS/PDK line has been integrated or deployed.

## Security reporting

Report vulnerabilities privately through [GitHub Security Advisories](https://github.com/Zheke32174/pleiades/security/advisories). Do not post real credentials, signing material, private evidence, personal data, third-party host details, or working exploit chains in public issues.

See [SECURITY.md](SECURITY.md) for the supported reporting scope.

## AI assistance

Documentation and scaffolding were partly drafted with Claude and ChatGPT. Maintainers remain responsible for testing, attribution, licensing, and security review.

## License

MIT — see [LICENSE](LICENSE). Platform and dependency notices are recorded in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
