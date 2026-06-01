"""
elevator/x86_to_aarch64.py — Concrete translation tiles: x86-64 → AArch64.

Abstract: tiles are "automatically derived from a high-level description of
the source ISA." In a full Elevator implementation, this file would be
generated, not hand-written.

[UNSPECIFIED] The ISA description language, tile generator, and the complete
set of tiles are entirely unknown (PDF unavailable).

What follows is a MANUALLY WRITTEN skeleton for a small subset of x86-64
instructions sufficient to demonstrate the tile framework. It is NOT a
faithful reproduction of Elevator's actual tile set.

Register mapping
----------------
[UNSPECIFIED] The paper does not describe the register assignment.
Using the following fixed map (a common convention for x86-to-AArch64):

  x86-64   AArch64   Notes
  rax   →  x0        caller-saved in AArch64 ABI
  rbx   →  x19       callee-saved
  rcx   →  x1
  rdx   →  x2
  rsi   →  x3
  rdi   →  x4 (x0 in Linux ABI — UNSPECIFIED)
  rsp   →  sp (x31)
  rbp   →  x29       frame pointer
  r8-r15 → x8-x15
"""

from __future__ import annotations

from .tiles import Tile, TileContext

# ── Register map ─────────────────────────────────────────────────────────────
# [UNSPECIFIED] Full register map. Using a minimal set for illustration.
REG_MAP: dict[str, str] = {
    "rax": "x0",  "eax": "w0",  "ax": "w0",
    "rbx": "x19", "ebx": "w19",
    "rcx": "x1",  "ecx": "w1",
    "rdx": "x2",  "edx": "w2",
    "rsi": "x3",  "esi": "w3",
    "rdi": "x4",  "edi": "w4",
    "rsp": "sp",
    "rbp": "x29", "ebp": "w29",
    "r8":  "x8",  "r8d": "w8",
    "r9":  "x9",  "r9d": "w9",
    "r10": "x10", "r10d": "w10",
    "r11": "x11", "r11d": "w11",
    "r12": "x12", "r12d": "w12",
    "r13": "x13", "r13d": "w13",
    "r14": "x14", "r14d": "w14",
    "r15": "x15", "r15d": "w15",
}


def _xreg(name: str) -> str:
    """Map x86-64 register name to AArch64. Return original if unmapped."""
    return REG_MAP.get(name.lower(), name)


# ── Helper: parse capstone operands (very simplified) ────────────────────────

def _ops(instr) -> list[str]:
    """Split operand string into individual operands."""
    return [s.strip() for s in getattr(instr, "op_str", "").split(",") if s.strip()]


# ── Tile definitions ──────────────────────────────────────────────────────────

def _tile_nop():
    return Tile(
        name="nop",
        matches=lambda i: getattr(i, "mnemonic", "").lower() in ("nop", "endbr64"),
        emit=lambda i, ctx: ["nop"],
    )


def _tile_ret():
    """
    x86-64 `ret` → AArch64 `ret`.

    [UNSPECIFIED] Whether Elevator translates the return address mechanism
    or relies on a compatible ABI. Using: direct ret (assumes ABI compat).
    """
    return Tile(
        name="ret",
        matches=lambda i: getattr(i, "mnemonic", "").lower() in ("ret", "retq"),
        emit=lambda i, ctx: ["ret"],
    )


def _tile_push():
    """
    x86-64 `push reg` → AArch64 `str reg, [sp, #-16]!`

    [UNSPECIFIED] Stack alignment: x86-64 uses 8-byte alignment for push,
    AArch64 requires 16-byte SP alignment. We use 16-byte slots.
    This is a known ABI mismatch in x86→AArch64 translation.
    """
    def matches(i):
        return getattr(i, "mnemonic", "").lower() == "push"

    def emit(i, ctx: TileContext) -> list[str]:
        ops = _ops(i)
        if not ops:
            return ["// [UNTILED] push with no operand"]
        src = _xreg(ops[0])
        # [UNSPECIFIED] 8-byte vs 16-byte slot. Using 16 for AArch64 alignment.
        return [f"str {src}, [sp, #-16]!"]

    return Tile(name="push", matches=matches, emit=emit)


def _tile_pop():
    def matches(i):
        return getattr(i, "mnemonic", "").lower() == "pop"

    def emit(i, ctx: TileContext) -> list[str]:
        ops = _ops(i)
        if not ops:
            return ["// [UNTILED] pop with no operand"]
        dst = _xreg(ops[0])
        return [f"ldr {dst}, [sp], #16"]

    return Tile(name="pop", matches=matches, emit=emit)


def _tile_mov_reg_reg():
    """mov reg, reg"""
    def matches(i):
        if getattr(i, "mnemonic", "").lower() not in ("mov", "movq", "movl"):
            return False
        ops = _ops(i)
        return len(ops) == 2 and ops[0] in REG_MAP and ops[1] in REG_MAP

    def emit(i, ctx: TileContext) -> list[str]:
        ops = _ops(i)
        dst, src = _xreg(ops[0]), _xreg(ops[1])
        return [f"mov {dst}, {src}"]

    return Tile(name="mov_reg_reg", matches=matches, emit=emit)


def _tile_mov_reg_imm():
    """mov reg, imm"""
    def matches(i):
        if getattr(i, "mnemonic", "").lower() not in ("mov", "movq", "movl"):
            return False
        ops = _ops(i)
        if len(ops) != 2:
            return False
        return ops[0] in REG_MAP and ops[1].lstrip("-").lstrip("0x").isalnum()

    def emit(i, ctx: TileContext) -> list[str]:
        ops = _ops(i)
        dst = _xreg(ops[0])
        imm = ops[1]
        # AArch64 mov for immediate uses movz/movk for large values.
        # [UNSPECIFIED] How Elevator handles 64-bit immediate moves.
        # Using: mov (works for 16-bit immediates; ldr from literal pool otherwise)
        try:
            val = int(imm, 0)
            if 0 <= val <= 0xFFFF:
                return [f"mov {dst}, #{val}"]
            else:
                # [UNSPECIFIED] Literal pool strategy
                return [
                    f"// [UNSPECIFIED] Large immediate {imm} — using movz/movk sequence",
                    f"movz {dst}, #{val & 0xFFFF}",
                    f"movk {dst}, #{(val >> 16) & 0xFFFF}, lsl #16",
                    f"movk {dst}, #{(val >> 32) & 0xFFFF}, lsl #32",
                    f"movk {dst}, #{(val >> 48) & 0xFFFF}, lsl #48",
                ]
        except ValueError:
            return [f"// [UNSPECIFIED] Cannot parse immediate: {imm}"]

    return Tile(name="mov_reg_imm", matches=matches, emit=emit)


def _tile_add():
    def matches(i):
        return getattr(i, "mnemonic", "").lower() in ("add", "addq", "addl")

    def emit(i, ctx: TileContext) -> list[str]:
        ops = _ops(i)
        if len(ops) != 2:
            return ["// [UNTILED] add with unexpected operands"]
        dst = _xreg(ops[0])
        src = ops[1]
        if src in REG_MAP:
            return [f"add {dst}, {dst}, {_xreg(src)}"]
        try:
            return [f"add {dst}, {dst}, #{int(src, 0)}"]
        except ValueError:
            return [f"// [UNSPECIFIED] add operand: {src}"]

    return Tile(name="add", matches=matches, emit=emit)


def _tile_sub():
    def matches(i):
        return getattr(i, "mnemonic", "").lower() in ("sub", "subq", "subl")

    def emit(i, ctx: TileContext) -> list[str]:
        ops = _ops(i)
        if len(ops) != 2:
            return ["// [UNTILED] sub with unexpected operands"]
        dst = _xreg(ops[0])
        src = ops[1]
        if src in REG_MAP:
            return [f"sub {dst}, {dst}, {_xreg(src)}"]
        try:
            return [f"sub {dst}, {dst}, #{int(src, 0)}"]
        except ValueError:
            return [f"// [UNSPECIFIED] sub operand: {src}"]

    return Tile(name="sub", matches=matches, emit=emit)


def _tile_jmp():
    """
    Unconditional jump.

    [UNSPECIFIED] How indirect branches (jmp *rax) are handled.
    Using: direct jumps only; indirect → brk.
    """
    def matches(i):
        return getattr(i, "mnemonic", "").lower() in ("jmp", "jmpq")

    def emit(i, ctx: TileContext) -> list[str]:
        ops = _ops(i)
        if not ops:
            return ["// [UNTILED] jmp with no target"]
        target = ops[0]
        try:
            addr = int(target, 0)
            return [f"b {ctx.label_for(addr)}"]
        except ValueError:
            # Indirect jump
            return [
                f"// [UNSPECIFIED] Indirect jmp {target} — runtime resolution needed",
                f"// Elevator would pre-compute all targets; we stub with brk.",
                "brk #0x1",
            ]

    return Tile(name="jmp", matches=matches, emit=emit, cost=2)


def _tile_call():
    """
    x86-64 call → AArch64 bl / blr.

    [UNSPECIFIED] How the return address stack is synchronized between
    x86-64 (pushed onto stack) and AArch64 (stored in x30/lr).
    """
    def matches(i):
        return getattr(i, "mnemonic", "").lower() in ("call", "callq")

    def emit(i, ctx: TileContext) -> list[str]:
        ops = _ops(i)
        if not ops:
            return ["// [UNTILED] call with no target"]
        target = ops[0]
        try:
            addr = int(target, 0)
            return [f"bl {ctx.label_for(addr)}"]
        except ValueError:
            if target in REG_MAP:
                return [f"blr {_xreg(target)}"]
            return [
                f"// [UNSPECIFIED] call {target} — cannot resolve",
                "brk #0x2",
            ]

    return Tile(name="call", matches=matches, emit=emit, cost=2)


def _tile_xor_zero():
    """
    xor reg, reg → AArch64 mov reg, #0  (zero-idiom).

    This is a very common x86-64 idiom. Elevator almost certainly has a
    tile for it, but the exact form is [UNSPECIFIED].
    """
    def matches(i):
        if getattr(i, "mnemonic", "").lower() != "xor":
            return False
        ops = _ops(i)
        return len(ops) == 2 and ops[0] == ops[1]

    def emit(i, ctx: TileContext) -> list[str]:
        ops = _ops(i)
        dst = _xreg(ops[0])
        return [f"mov {dst}, xzr"]

    return Tile(name="xor_zero", matches=matches, emit=emit, cost=0)


# ── Public tile list ──────────────────────────────────────────────────────────

def default_tile_set() -> list[Tile]:
    """
    Return the default ordered tile list.

    [UNSPECIFIED] The actual Elevator tile set and ordering. This is a minimal
    demonstration subset. A real implementation would have hundreds of tiles.
    """
    return [
        _tile_nop(),
        _tile_ret(),
        _tile_xor_zero(),   # before general xor — more specific
        _tile_push(),
        _tile_pop(),
        _tile_mov_reg_reg(),
        _tile_mov_reg_imm(),
        _tile_add(),
        _tile_sub(),
        _tile_call(),
        _tile_jmp(),
    ]
