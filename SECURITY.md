# Security Policy

## Supported scope

The proposed `0.2.0` release covers the source files listed by `release/source-paths.txt`, centered on the `lean/` defensive runtime.

Security reports are especially useful for defects involving:

- lean service sandboxing, resource bounds, socket activation, or unit-to-executable identity;
- Nexus queue, inflight recovery, hash chaining, signature generation, or verification;
- event loss, replay ambiguity, evidence corruption, or silent success;
- key initialization, permissions, replacement, exposure, or unsafe recovery behavior;
- Merope snapshot confidentiality, signatures, restore guards, or key separation;
- public decoy input handling, resource exhaustion, unintended command execution, or data disclosure;
- installer actions outside the documented Gentoo-container boundary;
- source archive scope, reproducibility, SPDX/receipt accuracy, or release identity mutation;
- credentials, signing material, private topology, evidence, or personal paths exposed in the current tree or reachable Git history.

Historical `root.x86_64/`, experimental recovery material, and unintegrated MODOS/PDK branches remain reviewable repository content but are not represented as supported lean release components.

## Reporting

Report vulnerabilities privately through [GitHub Security Advisories](https://github.com/Zheke32174/pleiades/security/advisories).

Include the minimum safe reproducer, affected commit or release asset, expected boundary, observed behavior, and whether the result required a live service or was found through source inspection.

Do not open public issues containing:

- real credentials, tokens, certificates, private keys, or signing seeds;
- private event logs, evidence archives, snapshots, databases, or recovery material;
- personal information, user-specific paths, private addresses, tailnet names, or third-party host details;
- working exploit chains against live systems;
- information that would expose an unrelated system owner.

## Release verification

A legitimate lean release must:

- be created from an immutable version tag matching `VERSION`;
- contain the named `pleiades-lean-<version>.tar.gz` asset;
- include `SHA256SUMS.txt`, SPDX 2.3 inventory, and an exact-commit build receipt;
- match the reviewed `release/source-paths.txt` scope;
- exclude historical runtime, experimental recovery, MODOS/PDK, runtime state, evidence, credentials, keys, stage3/rootfs, and container/VM images;
- pass lean invariants and complete reachable-history sensitivity review before publication;
- refuse to edit an existing release identity.

GitHub's automatically generated repository archives are not substitutes for the manifest-scoped release asset.

## Deployment boundary

The release is source, not a deployment receipt. Build and live verification belong inside a disposable or explicitly scheduled Gentoo container. Host and container lifecycle belong to `pleiades-container`.

`lean/build.sh` requires root inside the container because it installs system files. It does not authorize host mutation, create the surrounding container, or enable services. Operators must review units, sockets, listening surfaces, keys, and data paths before activation.

Public-facing deception services must be deployed only on systems and networks the operator owns or is explicitly authorized to administer. They must not be used as a pretext for unauthorized collection, retaliation, persistence, reconnaissance, credential access, or lateral movement.

## Evidence and key handling

Never commit or publish:

- `.env` files or local environment configuration;
- API keys, OAuth tokens, GitHub credentials, or service passwords;
- SSH, TLS, Ed25519, or recovery private keys;
- real certificates when they identify private infrastructure;
- Nexus ledgers, spools, event captures, forensic bundles, or databases containing live data;
- private snapshot archives, escrow material, or recovery receipts;
- host-specific operator configuration.

Evidence failures must remain visible. Do not vacuum, truncate, rewrite, or delete evidence merely to conceal activity or force a green status.

## Dependencies and platform

The lean archive does not vendor Gentoo, systemd, OpenSSL, a container runtime, or third-party research tools. Review the security and licensing posture of the actual operating-system packages and external services used in each deployment.

The historical stack may reference additional research projects, but those references do not make them lean runtime dependencies or approved release contents.

## Disclosure expectations

Maintainers will validate the report, determine whether current source, history, release assets, or downstream deployments are affected, and coordinate remediation. Public disclosure should wait until affected maintainers have had a reasonable opportunity to correct the issue and rotate or retire any exposed material.
