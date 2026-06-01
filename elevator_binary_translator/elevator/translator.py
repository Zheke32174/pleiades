"""
elevator/translator.py — Main translation orchestrator.

Abstract flow:
  1. Multi-interpret every byte (interpreter.py)
  2. Build multi-interpretation CFG (cfg.py)
  3. Prune paths leading to abnormal termination (pruner.py)
  4. For each live OPCODE node, emit AArch64 via tile selector (tiles.py)
  5. Assemble and return output (keystone or text)
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from .cfg import CFGBuilder, InterpCFG
from .interpreter import MultiInterpretationDisassembler
from .pruner import Pruner
from .tiles import FirstMatchSelector, TileContext
from .x86_to_aarch64 import REG_MAP, default_tile_set

try:
    import keystone
    HAS_KEYSTONE = True
except ImportError:
    HAS_KEYSTONE = False


@dataclass
class TranslationResult:
    """Output of one Elevator translation run."""
    source_path:  str
    base_address: int
    cfg:          InterpCFG
    asm_lines:    list[str]    # emitted AArch64 assembly (text)
    pruned_count: int
    live_count:   int
    # [UNSPECIFIED] Output binary bytes; requires keystone assembler.
    binary:       bytes | None = None


class Translator:
    """
    Orchestrate the full Elevator pipeline for one binary.

    [UNSPECIFIED] How the entry address is determined without debug info.
    Using: ELF entry point parsed from the ELF header.
    Alternatives: first byte of .text section, user-provided address.
    """

    def __init__(self, tile_selector=None):
        tiles = default_tile_set()
        self.selector = tile_selector or FirstMatchSelector(tiles)

    def translate_bytes(
        self,
        binary: bytes,
        base_address: int = 0x400000,
        entry_address: int | None = None,
    ) -> TranslationResult:
        """
        Translate raw x86-64 bytes to AArch64 assembly text.

        Parameters
        ----------
        binary        : raw bytes of the x86-64 .text section (or full binary)
        base_address  : virtual address of the first byte
        entry_address : VA of the entry point; defaults to base_address
        """
        if entry_address is None:
            entry_address = base_address

        # Stage 1: multi-interpretation disassembly
        dis = MultiInterpretationDisassembler(binary, base_address)

        # Stage 2: build CFG
        builder = CFGBuilder(dis)
        cfg = builder.build(entry_address)

        # Stage 3: prune
        pruner = Pruner(cfg, entry_address)
        pruned_count = pruner.run()

        # Stage 4: emit tiles
        asm_lines = self._emit_assembly(cfg, base_address)

        # Stage 5: assemble (optional — requires keystone)
        binary_out = None
        if HAS_KEYSTONE:
            binary_out = self._assemble(asm_lines)

        live = len(cfg.live_nodes())
        return TranslationResult(
            source_path="<bytes>",
            base_address=base_address,
            cfg=cfg,
            asm_lines=asm_lines,
            pruned_count=pruned_count,
            live_count=live,
            binary=binary_out,
        )

    def translate_file(self, path: str | Path) -> TranslationResult:
        """
        Translate an x86-64 ELF binary file.

        [UNSPECIFIED] How Elevator handles the full ELF structure, relocations,
        PLT, GOT, and dynamic linking. We extract only .text for demonstration.
        """
        path = Path(path)
        raw = path.read_bytes()

        base_address, entry_address, text_bytes = self._extract_elf(raw)

        result = self.translate_bytes(text_bytes, base_address, entry_address)
        result.source_path = str(path)
        return result

    # ── internal ──────────────────────────────────────────────────────────

    def _emit_assembly(self, cfg: InterpCFG, base_address: int) -> list[str]:
        """
        Walk live OPCODE nodes in address order and emit AArch64 lines.

        [UNSPECIFIED] Output format, label generation, section directives.
        Using: flat .text section, .L{addr} labels, GNU assembler syntax.
        """
        lines: list[str] = [
            ".arch armv8-a",
            ".text",
            f"// Elevator translation — base {base_address:#010x}",
            f"// [UNSPECIFIED] Full ELF structure not reconstructed.",
            "",
        ]

        ctx = TileContext(
            source_address=base_address,
            reg_map=REG_MAP,
        )

        opcode_nodes = sorted(cfg.opcode_nodes(), key=lambda n: n.address)
        seen_addrs: set[int] = set()

        for node in opcode_nodes:
            addr = node.address
            if addr in seen_addrs:
                continue
            seen_addrs.add(addr)

            ctx.source_address = addr
            label = ctx.label_for(addr)
            lines.append(f"{label}:")

            instr = node.interpretation.instr
            if instr is not None:
                mnemonic = getattr(instr, "mnemonic", "?")
                op_str   = getattr(instr, "op_str",   "")
                lines.append(f"  // x86: {addr:#010x}  {mnemonic} {op_str}")
                emitted = self.selector.emit(instr, ctx)
                lines.extend(f"  {l}" for l in emitted)
            lines.append("")

        return lines

    def _assemble(self, asm_lines: list[str]) -> bytes | None:
        """
        Assemble AArch64 text → bytes using keystone.

        [UNSPECIFIED] Keystone is not part of the Elevator paper;
        it's used here as a convenience assembler.
        """
        if not HAS_KEYSTONE:
            return None
        try:
            ks = keystone.Ks(keystone.KS_ARCH_ARM64, keystone.KS_MODE_LITTLE_ENDIAN)
            asm_text = "\n".join(asm_lines)
            encoding, _ = ks.asm(asm_text)
            return bytes(encoding)
        except Exception as e:
            print(f"WARNING: keystone assembly failed: {e}")
            return None

    @staticmethod
    def _extract_elf(raw: bytes) -> tuple[int, int, bytes]:
        """
        Minimal ELF64 parser: extract base, entry, .text bytes.

        [UNSPECIFIED] Full binary structure handling.
        Using: parse ELF header only; fall back to treating whole binary as .text.
        """
        if raw[:4] != b"\x7fELF":
            return 0x400000, 0x400000, raw

        try:
            import struct
            # ELF64 header fields
            e_entry  = struct.unpack_from("<Q", raw, 0x18)[0]
            e_phoff  = struct.unpack_from("<Q", raw, 0x20)[0]
            e_phnum  = struct.unpack_from("<H", raw, 0x38)[0]
            e_phsize = struct.unpack_from("<H", raw, 0x36)[0]

            # Find PT_LOAD segment with executable flag (PF_X = 0x1)
            base_addr = e_entry & ~0xFFF   # page-align
            text_bytes = b""

            for i in range(e_phnum):
                off = e_phoff + i * e_phsize
                p_type  = struct.unpack_from("<I", raw, off)[0]
                p_flags = struct.unpack_from("<I", raw, off + 4)[0]
                p_offset = struct.unpack_from("<Q", raw, off + 8)[0]
                p_filesz = struct.unpack_from("<Q", raw, off + 32)[0]
                if p_type == 1 and (p_flags & 0x1):   # PT_LOAD + PF_X
                    text_bytes = raw[p_offset: p_offset + p_filesz]
                    break

            if not text_bytes:
                text_bytes = raw

            return base_addr, e_entry, text_bytes

        except Exception:
            return 0x400000, 0x400000, raw
