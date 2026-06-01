"""
Elevator: LLM-assisted Binary Lifting to High-Level IR
arXiv: 2605.08419

Implements the binary lifting pipeline: x86/ARM binary → LLVM IR → C pseudocode,
using LLM refinement to recover variable names, types, and structure.
"""
from __future__ import annotations
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class LiftedFunction:
    name: str
    address: int
    asm: str
    llvm_ir: Optional[str] = None
    pseudocode: Optional[str] = None
    inferred_types: dict = None

    def __post_init__(self):
        if self.inferred_types is None:
            self.inferred_types = {}


class ElevatorLifter:
    """
    Binary lifting pipeline from the Elevator paper:
    1. Disassemble with radare2/objdump
    2. Lift to LLVM IR via retdec or McSema (if available)
    3. LLM refinement: recover names, types, structure
    4. Output annotated C pseudocode
    """

    def __init__(self, binary: str, llm_bin: str = "/usr/local/bin/purple-llm"):
        self.binary = Path(binary)
        self.llm_bin = llm_bin

    # ── Stage 1: Disassembly ──────────────────────────────────────────────────

    def disassemble(self) -> list[LiftedFunction]:
        """Extract functions via radare2 or objdump fallback."""
        funcs: list[LiftedFunction] = []

        if subprocess.run(["which", "r2"], capture_output=True).returncode == 0:
            out = subprocess.run(
                ["r2", "-q", "-e", "scr.color=0", "-e", "log.level=0",
                 "-c", "aaa; aflj", str(self.binary)],
                capture_output=True, text=True, timeout=60
            )
            try:
                import json
                for fn in json.loads(out.stdout or "[]"):
                    asm_out = subprocess.run(
                        ["r2", "-q", "-e", "scr.color=0", "-e", "log.level=0",
                         "-c", f"s {fn['offset']}; pdf", str(self.binary)],
                        capture_output=True, text=True, timeout=30
                    )
                    funcs.append(LiftedFunction(
                        name=fn.get("name", f"fcn_{fn['offset']:x}"),
                        address=fn["offset"],
                        asm=asm_out.stdout[:4096],
                    ))
            except Exception:
                pass

        if not funcs:
            # Fallback: objdump
            out = subprocess.run(
                ["objdump", "-d", str(self.binary)],
                capture_output=True, text=True, timeout=30
            )
            funcs.append(LiftedFunction(
                name="main", address=0, asm=out.stdout[:8192]
            ))

        return funcs

    # ── Stage 2: LLVM IR lifting ──────────────────────────────────────────────

    def lift_to_ir(self, func: LiftedFunction) -> LiftedFunction:
        """Attempt retdec or McSema IR lifting; fall back to ASM."""
        if subprocess.run(["which", "retdec-decompiler"], capture_output=True).returncode == 0:
            with tempfile.NamedTemporaryFile(suffix=".ll", delete=False) as f:
                out = subprocess.run(
                    ["retdec-decompiler", str(self.binary), "--select-ranges",
                     hex(func.address), "-o", f.name],
                    capture_output=True, timeout=60
                )
                if out.returncode == 0:
                    func.llvm_ir = Path(f.name).read_text(errors="replace")[:8192]
        return func

    # ── Stage 3: LLM refinement ───────────────────────────────────────────────

    def refine(self, func: LiftedFunction) -> LiftedFunction:
        """Use LLM to recover variable names, types, and produce clean pseudocode."""
        import shutil
        if not (shutil.which("purple-llm") or Path(self.llm_bin).exists()):
            func.pseudocode = f"// LLM not available\n// Raw ASM:\n{func.asm[:2000]}"
            return func

        src = func.llvm_ir or func.asm
        prompt = (
            f"Function: {func.name} @ 0x{func.address:x}\n"
            f"Assembly/IR:\n{src[:3000]}\n\n"
            "Lift to clean C pseudocode. Recover: variable names, types, "
            "control flow, and any security issues. Output only C code."
        )
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(prompt)
            tmp = f.name

        result = subprocess.run(
            [self.llm_bin, "--mode=re", f"--file={tmp}"],
            capture_output=True, text=True, timeout=120
        )
        func.pseudocode = result.stdout.strip() if result.returncode == 0 else func.asm[:2000]
        return func

    def lift(self) -> list[LiftedFunction]:
        """Full pipeline: disassemble → IR → LLM refine."""
        funcs = self.disassemble()
        return [self.refine(self.lift_to_ir(f)) for f in funcs]

    def report(self, funcs: list[LiftedFunction]) -> str:
        lines = [f"# Elevator Lifting Report: {self.binary.name}\n"]
        for fn in funcs:
            lines.append(f"## {fn.name} @ 0x{fn.address:x}\n```c\n{fn.pseudocode or fn.asm[:500]}\n```\n")
        return "\n".join(lines)


if __name__ == "__main__":
    import sys
    binary = sys.argv[1] if len(sys.argv) > 1 else "/bin/ls"
    lifter = ElevatorLifter(binary)
    funcs = lifter.lift()
    print(lifter.report(funcs))
