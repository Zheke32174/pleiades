# NLSpec: omnipkg-to-gentoo — Universal Package Ecosystem → Gentoo Converter

## Purpose
Convert packages from **every major package ecosystem** into Gentoo binary packages (`.tbz2` with XPAK),
pipe them into a systemd-nspawn Gentoo container, and install them with `emerge --usepkgonly`.
All source formats are first compressed to minimum footprint before transfer.

Extends the existing `alien-bsd` tool (FreeBSD/pkgsrc → deb/tbz2) into a universal converter
covering: FreeBSD pkg, pkgsrc tgz, Debian deb, RPM, Alpine apk, Arch pkg.tar.zst,
Python wheels, npm tarballs, Cargo crates, Go modules, Nix store paths, Homebrew bottles.

## Actors
- **omnipkg**: Orchestrator CLI that discovers, compresses, and pipelines packages
- **alien-bsd**: Existing BSD converter (FreeBSD .pkg → .deb + .tbz2); extended by this spec
- **alien-universal**: New multi-ecosystem backend plugging into alien-bsd's XPAK builder
- **Gentoo container**: systemd-nspawn rootfs at `/workspaces/gentoo/root.x86_64`
- **asterope_pleiades-swarm**: Existing daemon supervising the BSD compat layer; extended to supervise omnipkg
- **pleiadesctl**: Existing operator CLI; gains `omnipkg-status`, `omnipkg-convert`, `omnipkg-install` subcommands

## Behaviors

### B1 — Source format detection
Given a file or directory, omnipkg identifies the package ecosystem from magic bytes and filename extension.
Supported: `.deb`, `.rpm`, `.apk` (Alpine), `.pkg.tar.zst` / `.pkg.tar.xz` (Arch), `.pkg` / `.txz` (FreeBSD),
`.tgz` (pkgsrc), `.whl` (Python wheel), `.tgz` npm tarball with `package.json`, Cargo `.crate`,
Go module zip, Nix store path, Homebrew bottle `.tar.gz`.

### B2 — Compression minimization before transfer
Before piping to the container, each package is recompressed to minimum size:
- Binary packages: `zstd -19` for transfer; bzip2 for the XPAK `.tbz2` (Portage requirement)
- Text-heavy packages (wheels, npm): deduplicate via hard-link tree, then tar+zstd
- Compression ratio and bytes-saved reported per package

### B3 — Gentoo .tbz2 + XPAK generation (all ecosystems)
Each source format is converted to a valid Gentoo binary package:
- Correct CATEGORY, PN, PV, SLOT, KEYWORDS, RDEPEND in Portage atom format
- CONTENTS with md5+mtime for every installed file
- Path remapping: ecosystem-specific prefixes → Linux FHS (`/usr/lib`, `/usr/bin`, etc.)
- `ALIEN_SRC_ECOSYSTEM` XPAK field marks the origin (e.g. `deb`, `rpm`, `wheel`, `npm`)

### B4 — Dependency translation
For each ecosystem, best-effort dependency name → Gentoo atom mapping:
- deb/rpm: use existing `DEP_MAP` from alien-bsd, extended with 50+ common Linux libs
- Python wheel: `install_requires` → `dev-python/<name>` atoms
- npm: `dependencies` → `dev-nodejs/<name>` atoms (advisory only; mark as `# npm-dep:`)
- Cargo: `[dependencies]` section → `dev-rust/<name>` atoms (advisory)
- Conflicts logged, not fatal; operator reviews `RDEPEND` in generated packages

### B5 — Pipeline into Gentoo container
Converted `.tbz2` packages are staged to `/run/pleiades/bsd-convert/outbox/` (existing pipeline),
then rsync'd or bind-mounted into the container's Portage binary package dir
(`/var/cache/binpkgs/<CATEGORY>/<PF>.tbz2`).
Installation: `nsenter` into container PID → `emerge --usepkgonly --oneshot <atom>`.
All installs are logged to `/var/log/pleiades/omnipkg-installs.log`.

### B6 — Conflict detection before install
Before `emerge --usepkgonly`, check if the atom is already satisfied in the container.
If a newer version is installed: skip and log. If a conflicting slot is present: warn operator.
Never silently overwrite a Gentoo-native package with an alien-converted one.

### B7 — Batch mode and queue processing
`omnipkg --batch <dir>` processes all recognized packages in a directory in dependency order.
Packages with unsatisfied deps (within the batch) are deferred and retried once.
Progress reported via append to `/run/pleiades/pleiades_nexus_fifo` (BSD_OMNIPKG events).

### B8 — pleiadesctl integration
`pleiadesctl omnipkg-status` — show queue depth, last conversion, last install
`pleiadesctl omnipkg-convert <pkg>` — trigger conversion, output to outbox
`pleiadesctl omnipkg-install <atom>` — install already-converted atom into container
`pleiadesctl omnipkg-list` — list all alien-installed atoms in container

### B9 — lm-sensors invariant
`lm-sensors` is never passed to any package manager. If encountered in a dependency list,
it is silently dropped (shim, no-op).

### B10 — Ecosystem-specific metadata extraction
| Ecosystem | Metadata source | Version field |
|-----------|----------------|---------------|
| deb | `DEBIAN/control` | `Version:` |
| rpm | `.spec` or cpio `%pre/%post` | `Version:` |
| Alpine apk | `APKINDEX` / `.PKGINFO` | `pkgver=` |
| Arch | `.PKGINFO` in tar | `pkgver=` |
| FreeBSD pkg | `+MANIFEST` JSON | `version` |
| pkgsrc tgz | `+CONTENTS` | `@name` |
| Python wheel | `*.dist-info/METADATA` | `Version:` |
| npm | `package/package.json` | `version` |
| Cargo crate | `Cargo.toml` | `version` |
| Nix | `nix-store --query --binding name` | derivation hash |

## Constraints

- **C1**: Never use emerge for Go, Rust, or bun installation (curl-only installers).
- **C2**: Never overwrite `/workspaces/gentoo/root.x86_64` live rootfs without operator approval.
- **C3**: Conversion must succeed without network access (all deps bundled in the source package).
- **C4**: Temporary staging dirs cleaned up on exit via trap.
- **C5**: FIFO events use `>>` append only — never `>` truncate.
- **C6**: lm-sensors is always a no-op shim in pkg_install.
- **C7**: Minimum Python 3.8 — no walrus operator or 3.10+ match/case in alien-bsd.
- **C8**: Compressed transfer size must be ≤ source size (no inflation).
- **C9**: All XPAK strings must be UTF-8; binary paths replaced with hex-escaped equivalents.

## Acceptance Criteria

- AC1: `alien-bsd` successfully converts a `.deb`, `.rpm`, `.apk`, `.pkg`, and `.whl` to `.tbz2`
- AC2: Each `.tbz2` passes `qxpak` inspection (valid XPAK block)
- AC3: `omnipkg --batch /tmp/test-pkgs/` processes a 10-package mixed-ecosystem directory
- AC4: At least one converted package installs cleanly via `emerge --usepkgonly` in container
- AC5: Compression ratio reported per package; compressed size ≤ original
- AC6: `pleiadesctl omnipkg-status` returns parseable output
- AC7: lm-sensors dropped silently from all dependency lists
- AC8: No files written to live rootfs during conversion (staging only)

## Satisfaction Target
0.80

## Complexity
high

## Tags
gentoo, package-conversion, alien, multi-ecosystem, compression, nspawn, pleiades-team
