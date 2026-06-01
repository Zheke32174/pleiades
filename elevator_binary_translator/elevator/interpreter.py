"""
elevator/interpreter.py — Multi-interpretation byte analysis.

Abstract §1: "Any byte may be interpreted as data, an opcode, or an opcode
argument; we generate separate control flow paths for all interpretations,
pruning only those leading to abnormal termination."

REPRODUCTION NOTE: The paper PDF was unavailable at time of implementation.
All implementation decisions below derive from the abstract only. Internal
data structures, algorithm details, and the tile grammar are UNSPECIFIED.
Every [UNSPECIFIED] choice is flagged with alternatives.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Iterator

try:
    import capstone
    HAS_CAPSTONE = True
except ImportError:
    HAS_CAPSTONE = False
    print("WARNING: capstone not installed. Install with: pip install capstone")
    print("         Falling back to stub disassembler.")


class ByteRole(enum.Enum):
    """
    Abstract §1 — three possible roles for any byte in the binary.
    The paper names these roles explicitly.
    """
    DATA        = "data"        # byte is (only) data; not executed as code
    OPCODE      = "opcode"      # byte is the first byte of an instruction
    OPCODE_ARG  = "opcode_arg"  # byte is an interior byte of a longer instruction


@dataclass(frozen=True)
class ByteInterpretation:
    """
    One specific hypothesis about a single byte.

    address : int   — VA in the source binary
    role    : ByteRole
    instr   : object | None   — capstone CsInsn if role==OPCODE, else None
    instr_start : int | None  — address of enclosing instruction if role==OPCODE_ARG
    """
    address:     int
    role:        ByteRole
    instr:       object = field(default=None, compare=False, repr=False)
    instr_start: int | None = None


class MultiInterpretationDisassembler:
    """
    Abstract §1: "Elevator considers all possible interpretations of every
    byte and produces a separate translation for each feasible one ahead of time."

    For each byte at address A we generate up to three ByteInterpretation
    objects (DATA, OPCODE, OPCODE_ARG).  Feasibility is determined by whether
    capstone can decode a valid x86-64 instruction starting at that byte.

    [UNSPECIFIED] The paper does not describe how many bytes of lookahead are
    used when deciding feasibility, or whether it uses a formal grammar or a
    pure disassembler.
    Using: capstone CS_MODE_64 with AT&T syntax disabled.
    Alternatives: XED (Intel), Zydis, hand-written prefix table.
    """

    # [UNSPECIFIED] Maximum instruction length to consider when checking
    # whether a byte can be an opcode argument.
    # x86-64 max instruction length is 15 bytes per the ISA manual.
    MAX_X86_INSTR_LEN = 15

    def __init__(self, binary: bytes, base_address: int = 0):
        self.binary       = binary
        self.base_address = base_address
        self._offset      = {base_address + i: i for i in range(len(binary))}

        if HAS_CAPSTONE:
            # [UNSPECIFIED] Syntax choice has no semantic effect on decoding.
            self._cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
            self._cs.skipdata = True   # treat undecodable bytes as data (1 byte)
        else:
            self._cs = None

    # ── public API ────────────────────────────────────────────────────────

    def interpretations_at(self, address: int) -> list[ByteInterpretation]:
        """
        Return all feasible interpretations for the byte at `address`.
        Abstract §1 — every byte gets all feasible roles.
        """
        result: list[ByteInterpretation] = []

        # Role 1: DATA is always feasible.
        result.append(ByteInterpretation(address=address, role=ByteRole.DATA))

        # Role 2: OPCODE — feasible iff capstone decodes a valid instruction here.
        instr = self._try_decode_at(address)
        if instr is not None:
            result.append(ByteInterpretation(
                address=address, role=ByteRole.OPCODE, instr=instr,
            ))

        # Role 3: OPCODE_ARG — feasible iff address falls inside an instruction
        # that starts within [address - MAX_X86_INSTR_LEN, address).
        enclosing = self._find_enclosing_instr(address)
        for start_addr in enclosing:
            result.append(ByteInterpretation(
                address=address,
                role=ByteRole.OPCODE_ARG,
                instr_start=start_addr,
            ))

        return result

    def all_interpretations(self) -> Iterator[tuple[int, list[ByteInterpretation]]]:
        """Yield (address, [interpretations]) for every byte in the binary."""
        for offset in range(len(self.binary)):
            addr = self.base_address + offset
            yield addr, self.interpretations_at(addr)

    # ── internal helpers ──────────────────────────────────────────────────

    def _try_decode_at(self, address: int) -> object | None:
        """Attempt to decode one x86-64 instruction starting at `address`."""
        if self._cs is None:
            return _StubInstruction(address)   # fallback stub
        offset = self._offset.get(address)
        if offset is None:
            return None
        chunk = self.binary[offset: offset + self.MAX_X86_INSTR_LEN]
        instrs = list(self._cs.disasm(chunk, address, count=1))
        if not instrs:
            return None
        instr = instrs[0]
        # [UNSPECIFIED] Paper doesn't define which instructions count as
        # "decodable" vs "leading to abnormal termination" at decode time.
        # Using: treat capstone skipdata pseudo-instructions as non-decodable.
        if instr.id == 0:   # capstone CS_GRP_INVALID / skipdata marker
            return None
        return instr

    def _find_enclosing_instr(self, address: int) -> list[int]:
        """
        Find start addresses of valid instructions that contain `address`
        as an interior byte (OPCODE_ARG role).

        [UNSPECIFIED] Paper does not specify search strategy.
        Using: scan backward up to MAX_X86_INSTR_LEN bytes.
        """
        enclosing = []
        start = max(self.base_address, address - self.MAX_X86_INSTR_LEN + 1)
        for probe in range(start, address):
            instr = self._try_decode_at(probe)
            if instr is None:
                continue
            instr_len = getattr(instr, "size", 1)
            if probe < address < probe + instr_len:
                enclosing.append(probe)
        return enclosing


# ── Stub for environments without capstone ────────────────────────────────────

class _StubInstruction:
    """Minimal stub so the rest of the framework compiles without capstone."""
    def __init__(self, address: int):
        self.address  = address
        self.mnemonic = "nop"
        self.op_str   = ""
        self.size     = 1
        self.id       = 1  # non-zero → "decodable"
        self.bytes    = b"\x90"
