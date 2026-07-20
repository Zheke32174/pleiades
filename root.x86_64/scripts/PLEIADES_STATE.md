# Pleiades Public Runtime State — Sanitized Record

This file intentionally contains **no workstation usernames, home-directory paths, profile paths, credentials, machine-specific backup locations, private plugin locations, or private topology bindings**.

The former detailed local-session state was useful during early development, but it mixed portable architectural facts with identity-bearing deployment notes. Those private details belong in the private evidence and ecology spine, not in the public repository.

## Current public invariants

- Pleiades runs a defensive Gentoo `systemd-nspawn` substrate with a minimal host launcher and independent local recovery.
- Local kernels remain sovereign over local hardware.
- The host/container bridge is owner-authorized and observational by default.
- Decoy and defensive services must remain policy-gated.
- Shell, installation, firewall, network mutation, credential access, lateral movement, and script mutation are denied unless an exact promoted policy and authority grant explicitly permit the specific action.
- Consequential actions require provenance, bounded capability, evidence, and rollback.
- The persistent Pleiades Mind is the recurrent organization; no individual model or agent is the whole Mind.
- Repository or catalog membership never grants runtime authority.
- Current development-assistant approval rules do not define the deployed runtime's delegated machine autonomy.

## Portable implementation invariants

- Distinct decoy services must not silently collapse onto conflicting ports.
- Supervisors must create a fresh child-process command for every restart attempt.
- Long-running supervisory loops retain panic/error isolation so one child cannot terminate the complete defensive stack.
- Request brokers default to introspection-only allowlists.
- Optional external or alien sidecars remain advisory and authority-free until separately promoted.
- `/run` event surfaces are explicit state and evidence interfaces; their concrete deployment paths are local configuration, not public canon.
- Package/bootstrap behavior must avoid known host-environment failure modes and remain dry-run reviewable.
- Disaster-recovery tests are never initiated merely because a historical note mentions them.

## State handling rule

Public state documents may record:

- portable architecture;
- public service roles;
- deterministic contracts;
- test outcomes without local identity;
- non-sensitive design invariants;
- issue and commit references.

They must not record:

- usernames or profile directories;
- local absolute paths tied to a person or machine;
- passwords, tokens, private keys, or authentication material;
- private endpoint or network topology;
- private repository inventories or backup identities;
- private evidence locations.

## Private continuity

Exact workstation state, deployment-specific paths, backup lineage, and session continuity belong in the private Undergrowth/evidence surfaces. Public agents should use repository contracts, current Git history, issue trackers, and sanitized checkpoint documents instead of reconstructing private topology from historical blobs.

## History status

This current-tree redaction does not rewrite reachable Git history. Historical identity-bearing blobs remain governed by issue `github:Zheke32174/pleiades#42` and require a separately authorized coordinated history rewrite, force-update plan, affected-branch rebase, and post-rewrite rescan.
