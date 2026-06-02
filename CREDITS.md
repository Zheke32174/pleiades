# Credits and Third-Party Attribution

Every external project, developer, or organization whose work is used, installed, wrapped, or referenced by Pleiades scripts is listed here.

**No third-party source code is vendored in this repository.** All external tools are cloned or installed from their upstream source at setup time. See `THIRD_PARTY_NOTICES.md` for the formal statement.

---

## AI Agents

| Project | Author / Org | License | Source URL | Usage | Vendored? | Modified? | Local path |
|---------|-------------|---------|-----------|-------|-----------|-----------|------------|
| Aider | paul-gauthier (Paul Gauthier) | Apache-2.0 | https://github.com/paul-gauthier/aider | installed via pip/pipx by `install-ai-agents.sh` | No | No | N/A |
| OpenHands | All-Hands-AI | MIT | https://github.com/All-Hands-AI/OpenHands | cloned at setup time by `install-ai-agents.sh` | No | No | N/A |

## LLM Inference

| Project | Author / Org | License | Source URL | Usage | Vendored? | Modified? | Local path |
|---------|-------------|---------|-----------|-------|-----------|-----------|------------|
| llama.cpp | ggerganov (Georgi Gerganov) | MIT | https://github.com/ggerganov/llama.cpp | cloned and compiled by `install-llm-stack.sh` | No | No | N/A |
| Mistral 7B weights | Mistral AI | Apache-2.0 | https://huggingface.co/mistralai/Mistral-7B-v0.1 | downloaded GGUF model by `install-llm-stack.sh` | No | No | N/A |
| Mistral 7B GGUF quantization | TheBloke | Apache-2.0 | https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.3-GGUF | GGUF format provided by TheBloke | No | No | N/A |

## MCP / API Integration

| Project | Author / Org | License | Source URL | Usage | Vendored? | Modified? | Local path |
|---------|-------------|---------|-----------|-------|-----------|-----------|------------|
| fastmcp | jlowin (Jeremiah Lowin) | Apache-2.0 | https://github.com/jlowin/fastmcp | `pleiades-mcp-converters.sh` generates Python that uses the fastmcp API | No | No | N/A |
| fastapi_mcp | tadata-org | MIT | https://github.com/tadata-org/fastapi_mcp | wrapped by `pleiades-mcp-converters.sh` | No | No | N/A |
| openapi-mcp-codegen | cnoe-io | Apache-2.0 | https://github.com/cnoe-io/openapi-mcp-codegen | wrapped by `pleiades-mcp-converters.sh` | No | No | N/A |
| jcodemunch-mcp | jgravelle | MIT | https://github.com/jgravelle/jcodemunch-mcp | referenced by `pleiades-mcp-converters.sh` | No | No | N/A |

## Code Analysis

| Project | Author / Org | License | Source URL | Usage | Vendored? | Modified? | Local path |
|---------|-------------|---------|-----------|-------|-----------|-----------|------------|
| paper2code | PrathamLearnsToCode | MIT | https://github.com/PrathamLearnsToCode/paper2code | wrapped by `pleiades-mcp-converters.sh` (paper2mcp) | No | No | N/A |

## Binary Reverse Engineering

| Project | Author / Org | License | Source URL | Usage | Vendored? | Modified? | Local path |
|---------|-------------|---------|-----------|-------|-----------|-----------|------------|
| Ghidra | NSA / National Security Agency | Apache-2.0 | https://github.com/NationalSecurityAgency/ghidra | binary called by `pleiades-re.sh` | No | No | N/A |
| angr | angr project | BSD-2-Clause | https://github.com/angr/angr | binary/library called by `pleiades-re.sh` | No | No | N/A |
| remill | Trail of Bits | Apache-2.0 | https://github.com/lifting-bits/remill | binary called by `pleiades-re.sh` | No | No | N/A |
| ddisasm | GrammaTech | **AGPL-3.0** | https://github.com/GrammaTech/ddisasm | binary called by `pleiades-re.sh` — **AGPL; only binary is called, no source vendored** | No | No | N/A |
| RetroWrite | HexHive (EPFL) | MIT | https://github.com/HexHive/retrowrite | binary called by `pleiades-re.sh` | No | No | N/A |
| rev.ng | rev.ng Labs | **GPL-2.0** | https://github.com/revng/revng | binary called by `pleiades-re.sh` — **GPL-2.0; only binary called, no source vendored** | No | No | N/A |

## Cross-ISA Emulation

| Project | Author / Org | License | Source URL | Usage | Vendored? | Modified? | Local path |
|---------|-------------|---------|-----------|-------|-----------|-----------|------------|
| Box64 | ptitSeb (Sebastian Chevalier) | MIT | https://github.com/ptitSeb/box64 | cloned or downloaded by `install-cross-isa.sh` | No | No | N/A |
| Wasmtime | Bytecode Alliance | Apache-2.0 | https://github.com/bytecodealliance/wasmtime | binary downloaded by `install-cross-isa.sh` | No | No | N/A |
| QEMU | QEMU project | **GPL-2.0+** | https://www.qemu.org | installed as system binary by `install-cross-isa.sh` and `Asterope.sh` — **GPL-2.0+; only binary installed, no source vendored** | No | No | N/A |

## BSD Compatibility Layer (Asterope.sh)

| Project | Author / Org | License | Source URL | Usage | Vendored? | Modified? | Local path |
|---------|-------------|---------|-----------|-------|-----------|-----------|------------|
| qemu-bsd-user-l4b | sobomax (Maksym Sobolyev) | MIT | https://github.com/sobomax/qemu-bsd-user-l4b | cloned by `Asterope.sh` for BSD user emulation | No | No | N/A |
| FreeBSD base system | The FreeBSD Project | BSD-2-Clause | https://www.freebsd.org | base.txz downloaded by `Asterope.sh` for BSD stratum | No | No | N/A |
| pkgsrc | The NetBSD Foundation | BSD-2-Clause | https://pkgsrc.org | bootstrap tarball downloaded by `Asterope.sh` | No | No | N/A |

## Framework References

| Project | Author / Org | License | Source URL | Usage | Vendored? | Modified? | Local path |
|---------|-------------|---------|-----------|-------|-----------|-----------|------------|
| agents-best-practices | DenisSergeevitch | MIT | https://github.com/DenisSergeevitch/agents-best-practices | structural reference for `pleiades-integrate-tools.sh` — no source copied | No | No | N/A |

---

## Copyleft / AGPL Notice

The following tools called by Pleiades scripts carry copyleft licenses. In all cases, Pleiades only calls the installed binary — no source is vendored, modified, or redistributed:

| Project | License | Risk level | Handling |
|---------|---------|------------|---------|
| ddisasm | AGPL-3.0 | Medium — network-use copyleft may apply to modifications | Binary-only use; no source vendored |
| QEMU | GPL-2.0+ | Medium — copyleft applies to modifications | Binary-only use via apt/system package |
| rev.ng | GPL-2.0 | Medium — copyleft applies to modifications | Binary-only use; no source vendored |

If you modify or redistribute any of these tools as part of a derivative work, review their license terms carefully before distribution.

---

## AI-Generated Code Notice

Several agent scripts embed Go, Rust, or Bun source that compiles at runtime inside the container. This code was generated as part of the Pleiades project. Where generated scaffolding closely follows an upstream project's structure, that project is credited above. If any embedded snippet is found to substantially reproduce upstream work, it will be credited, replaced, or removed before release.

---

## No Vendored Third-Party Source

This repository does not vendor source code from any third-party project. Every external tool listed above is cloned, downloaded, or installed from its upstream source at setup time. See `THIRD_PARTY_NOTICES.md`.
