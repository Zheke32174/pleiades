# Third-Party and Platform Notices

The lean source release does not vendor a Gentoo stage3, Linux kernel, systemd, OpenSSL, PHP, container runtime, model, or third-party research-tool checkout.

## Expected platform components

The reviewed source is designed for a Gentoo Linux environment using systemd and ordinary operating-system packages. Runtime scripts may invoke platform tools such as Bash, OpenSSL, systemctl, journalctl, socket activation, and core utilities. Those components remain governed by their own licenses and distribution terms.

## Related Pleiades repositories

- `Zheke32174/pleiades-container` creates and supervises the Linux/Gentoo container substrate. It is not embedded in this archive.
- `Zheke32174/pleiades-factory-stack` catalogs separately reviewed research-source projects. Those projects are not embedded in this archive.
- Private evidence, factory, topology, and recovery repositories are not included.

## Historical and research material

Historical scripts and research references remaining elsewhere in the repository are outside the lean release archive. Their presence in repository history does not make them supported runtime dependencies or grant permission to redistribute third-party material without reviewing the applicable upstream license.

The old broad stack may reference projects such as llama.cpp, OpenHands, Aider, box64, Wasmtime, and qemu-bsd-user-l4b. They are not required by `lean/build.sh`, are not bundled in the lean source release, and remain governed by their upstream licenses.

## Downstream responsibility

The SPDX inventory identifies the exact first-party source files included in each release candidate. Downstream distributors remain responsible for reviewing the licenses of the operating system, packages, and external services they combine with Pleiades. Do not infer license compatibility merely from the absence of vendored source.
