# Changelog

## 0.2.0 — Unreleased

### Added

- Deterministic lean source packaging from an exact Git commit.
- SPDX source inventory, SHA-256 checksums, and a build receipt.
- Public-tree and reachable-history review checks.
- Privacy, security, attribution, release-scope, update, rollback, and removal documentation.

### Changed

- The supported distribution is the bounded `lean/` source tree.
- Release publication requires a version-matching immutable tag.
- Documentation distinguishes source packaging from installation and deployment.

### Removed

- Branch-triggered mutable release behavior.
- The obsolete package-container publication path.

### Remaining gates

- Exact-head pull-request validation must prove package reproducibility and report all history-scan findings.
- Disposable-host runtime validation remains separate.
- No tag or release is created by this draft.