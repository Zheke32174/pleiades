# pleiades

Pleiades is the WSL2/Gentoo `systemd-nspawn` purple-team lab workspace.

This repository tracks the owner-visible deployment layer in `/workspaces/gentoo`
and the active polyglot purple-team scripts under
`root.x86_64/scripts/`. It intentionally does not track the full Gentoo rootfs,
raw VM images, stage3 archives, runtime caches, or timestamped backup copies.

Start with `PURPLE_STATE.md` before making changes. Runtime entrypoints are
provided by the host wrappers:

- `gentoo-up` starts the Gentoo `systemd-nspawn` container.
- `gentoo-shell` enters the running container with `nsenter`.

Back up files before every edit.
