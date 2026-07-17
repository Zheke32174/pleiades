# Pleiades

Pleiades is an owner-operated defensive research system for deception services, host telemetry, tamper-evident evidence, recovery testing, and bounded defensive automation.

The current release-track runtime is the clean `lean/` rebuild inside a Gentoo `systemd-nspawn` lab. The longer-term architecture separates public-facing sensors, evidence, knowledge, cognition, authority, and recovery so compromise of one layer cannot silently contaminate the others.

Pleiades is not intended for unauthorized deployment, credential theft, lateral movement, retaliation, or reconnaissance on systems you do not own or administer.

## Current status

The original multi-script stack remains in the repository as historical and migration material. It is not the canonical production path.

The supported implementation is `lean/`, which enforces:

- one binary and one systemd unit per component;
- no runtime self-install or `curl | sh` toolchain assembly;
- systemd-owned supervision and rate limits;
- no in-process infinite polling loops;
- hardened service sandboxes and a shared resource slice;
- honest status reporting rather than masked failures;
- unique event IDs and a hash-chained, Ed25519-signed Nexus ledger;
- observe-first defensive behavior;
- explicit owner approval for recovery operations.

See [`lean/README.md`](lean/README.md) for deployment details and [`docs/DEFENSIVE_ARCHITECTURE.md`](docs/DEFENSIVE_ARCHITECTURE.md) for the target trust-plane design.

## Repository map

| Repository | Status | Purpose |
|---|---|---|
| [`pleiades`](https://github.com/Zheke32174/pleiades) | Release track | Lean runtime, host scripts, architecture, tests |
| [`pleiades-container`](https://github.com/Zheke32174/pleiades-container) | Release track | Gentoo container bootstrap and launcher |
| [`pleiades-factory-stack`](https://github.com/Zheke32174/pleiades-factory-stack) | Research track | Tooling, AI/LLM integration, cross-platform helpers |
| `pleiades-factory` | Private staging | Future orchestration work |
| `pleiades-evidence` | Private | Forensic evidence archive; never public |

## Defensive planes

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

The host remains deterministic and must continue operating when the cognitive plane is unavailable. AI workers may interpret, correlate, retrieve, prioritize, and propose; they do not receive ambient host authority.

## Lean component map

| Component | Current role |
|---|---|
| Maia | Node trust root, checkpointing, Nexus sealing |
| Nexus | Tamper-evident operational ledger and verifier |
| Taygete | Socket-activated SSH deception sensor |
| Electra | Socket-activated HTTP and telnet decoys |
| Alcyone | Read-only listener and connection posture |
| Celaeno | systemd `OnFailure` alert handling |
| Merope | Encrypted, signed snapshots with explicit restore guard |
| Sterope | Observe-only threat scoring and posture summary |

## Quick start

```bash
# Authenticate GitHub CLI if recovery or private-repository features are needed.
gh auth login

# Operator setup writes /etc/pleiades/operator.conf.
sudo bash root.x86_64/scripts/pleiades-setup.sh

# Validate source-level invariants.
bash -n lean/agents/*/*.sh lean/ops/*.sh
bash ci/check-lean-security.sh lean

# Build inside the booted Gentoo container.
sudo bash lean/build.sh
```

For container creation and startup, use [`pleiades-container`](https://github.com/Zheke32174/pleiades-container). Review scripts and use dry-run support before applying changes to a live host.

## Verification

The full lean verification entrypoint is:

```bash
bash lean/ops/verify-full.sh
```

A nonzero failure count returns a nonzero process status. Missing or empty evidence is reported distinctly from a valid ledger.

Security properties and adversarial tests are documented in [`lean/docs/SECURITY_PROPERTIES.md`](lean/docs/SECURITY_PROPERTIES.md).

## Security reporting

Report vulnerabilities privately through [GitHub Security Advisories](https://github.com/Zheke32174/pleiades/security/advisories). Do not post real credentials, private evidence, personal data, third-party host details, or working exploit chains in public issues.

## AI assistance

Documentation and scaffolding were partly drafted with Claude and ChatGPT. Maintainers remain responsible for testing, attribution, licensing, and security review.

---

[LICENSE](LICENSE) · [SECURITY.md](SECURITY.md) · [DISCLAIMER.md](DISCLAIMER.md) · [CONTRIBUTING.md](CONTRIBUTING.md)
