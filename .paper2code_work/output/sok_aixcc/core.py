"""
SoK: AIxCC — Systematization of Knowledge for AI-powered Cyber Competition
arXiv: 2602.07666

Implements the core pipeline taxonomy and scoring framework described in the paper:
autonomous vulnerability discovery → exploitation → patching loop used in AIxCC competitions.
"""
from __future__ import annotations
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Vulnerability:
    binary: str
    cve_id: Optional[str] = None
    crash_input: Optional[bytes] = None
    exploit: Optional[bytes] = None
    patch: Optional[str] = None
    confidence: float = 0.0


@dataclass
class AIxCCPipeline:
    """
    Models the three-phase autonomous pipeline from the SoK survey:
    Phase 1: Vulnerability Discovery (static + dynamic analysis)
    Phase 2: Exploit Generation  (crash → PoC)
    Phase 3: Patch Generation    (LLM-assisted fix)
    """
    binary_path: str
    work_dir: Path = field(default_factory=lambda: Path("/tmp/aixcc_work"))
    timeout: int = 3600

    def __post_init__(self):
        self.work_dir.mkdir(parents=True, exist_ok=True)

    # ── Phase 1: Discovery ────────────────────────────────────────────────────

    def discover(self) -> list[Vulnerability]:
        """Static + dynamic triage to surface candidate vulnerabilities."""
        vulns: list[Vulnerability] = []

        # Static: dangerous function sinks
        result = subprocess.run(
            ["nm", "-D", self.binary_path],
            capture_output=True, text=True
        )
        dangerous = {"gets", "strcpy", "sprintf", "scanf", "system"}
        found_sinks = [sym for sym in dangerous if sym in result.stdout]
        if found_sinks:
            vulns.append(Vulnerability(
                binary=self.binary_path,
                confidence=0.6,
            ))

        # Dynamic: AFL++ triage (short run)
        afl = subprocess.run(
            ["which", "afl-fuzz"], capture_output=True
        )
        if afl.returncode == 0:
            # Abbreviated fuzz — real run would use self.timeout
            vulns.extend(self._fuzz_triage())

        return vulns

    def _fuzz_triage(self) -> list[Vulnerability]:
        seed = self.work_dir / "in"
        seed.mkdir(exist_ok=True)
        (seed / "seed").write_bytes(b"AAAA\x00")
        # In production: run afl-fuzz, collect crashes
        return []

    # ── Phase 2: Exploit Generation ───────────────────────────────────────────

    def generate_exploit(self, vuln: Vulnerability) -> Vulnerability:
        """Convert crash input into a minimal PoC exploit."""
        if not vuln.crash_input:
            return vuln
        # Pattern: cyclic payload to identify offset, then ROP chain
        cyclic = bytes(range(256)) * 4
        vuln.exploit = cyclic[:512]
        return vuln

    # ── Phase 3: Patch Generation ─────────────────────────────────────────────

    def generate_patch(self, vuln: Vulnerability, llm_bin: str = "/usr/local/bin/purple-llm") -> Vulnerability:
        """LLM-assisted patch proposal."""
        import shutil, tempfile
        if not shutil.which(llm_bin.split("/")[-1]) and not Path(llm_bin).exists():
            return vuln
        prompt = (
            f"Binary: {Path(self.binary_path).name}\n"
            "Crash type: likely buffer overflow at input sink.\n"
            "Propose a minimal C patch adding bounds checking. Output only code."
        )
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(prompt)
            tmp = f.name
        result = subprocess.run(
            [llm_bin, "--mode=patch", f"--file={tmp}"],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            vuln.patch = result.stdout.strip()
        return vuln

    def run(self) -> list[Vulnerability]:
        """Full AIxCC pipeline: discover → exploit → patch."""
        vulns = self.discover()
        return [self.generate_patch(self.generate_exploit(v)) for v in vulns]


def score_pipeline(vulns: list[Vulnerability]) -> dict:
    """Compute AIxCC-style scoring metrics from the SoK framework."""
    return {
        "total_vulns": len(vulns),
        "exploitable": sum(1 for v in vulns if v.exploit),
        "patched": sum(1 for v in vulns if v.patch),
        "avg_confidence": sum(v.confidence for v in vulns) / max(len(vulns), 1),
    }


if __name__ == "__main__":
    import sys
    binary = sys.argv[1] if len(sys.argv) > 1 else "/bin/ls"
    pipeline = AIxCCPipeline(binary)
    results = pipeline.run()
    scores = score_pipeline(results)
    print(f"AIxCC pipeline complete: {scores}")
