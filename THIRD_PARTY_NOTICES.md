# Third-Party Notices

## No Vendored Source

This repository does not contain vendored third-party source code.

All external tools referenced by Pleiades scripts are:
- Cloned from their upstream repositories at setup time, OR
- Installed from official package registries (pip, cargo, apt, etc.)

No third-party source files are committed to this repository. Each external project remains entirely governed by its own license.

## Runtime Dependencies Cloned at Setup

The following projects are cloned or downloaded when the relevant `install-*.sh` scripts are run. They are never present in this repository.

| Project | Upstream URL | License |
|---------|-------------|---------|
| llama.cpp | https://github.com/ggerganov/llama.cpp | MIT |
| OpenHands | https://github.com/All-Hands-AI/OpenHands | MIT |
| Aider | https://github.com/paul-gauthier/aider | Apache-2.0 |
| box64 | https://github.com/ptitSeb/box64 | MIT |
| Wasmtime | https://github.com/bytecodealliance/wasmtime | Apache-2.0 |
| qemu-bsd-user-l4b | https://github.com/sobomax/qemu-bsd-user-l4b | MIT |

If you are running Pleiades and have cloned any of these tools, please review their individual licenses in their respective repositories before use in your context.

## License Compatibility

Pleiades scripts themselves are MIT-licensed. Because no third-party source is vendored, there are no GPL/AGPL mixing concerns in this repository. If you vendor any of the above tools into a derivative work, review the compatibility of their licenses with your distribution terms.
