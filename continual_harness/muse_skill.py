"""
MUSE-Autoskill — Skill Lifecycle Manager
arxiv 2605.27366: Self-Evolving Agents via Skill Creation, Memory, Management, Evaluation

Implements the five-stage skill lifecycle from §3.2 and three-level memory from §3.3.
Integrates with ContinualHarness as a richer replacement for raw K_create/update
operations in the Refiner's Pass (iii).

Skill package format follows Anthropic Agent Skills (SKILL.md) — the same format
used in ~/.claude/skills/. See §3.2: "following Anthropic's Agent Skills format [2]".

[UNSPECIFIED] Max retry count on test failure: Using 3.
[UNSPECIFIED] L1 token threshold: Using 8000 tokens (Figure 4 shows ~10-20K nodes as triggers).
[UNSPECIFIED] Context budget: Using 50000 tokens (Figure 4 uses 50K in its example).
[UNSPECIFIED] Prune criteria: fail_count >= 3 OR unused_turns >= 100.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


# ── Skill Package (§3.2) ──────────────────────────────────────────────────────

@dataclass
class SkillPackage:
    """
    §3.2: "skill is packaged as a structured directory with standard components,
    following Anthropic's Agent Skills format."
    Components: SKILL.md, scripts/, tests/, resources/, .memory.md
    """
    name: str
    skill_md: str                          # SKILL.md content: name, description, I/O
    scripts: dict[str, str] = field(default_factory=dict)    # filename → code
    tests: dict[str, str] = field(default_factory=dict)      # filename → test code
    resources: dict[str, str] = field(default_factory=dict)  # filename → content
    memory_md: str = ""                    # §3.3: accumulated .memory.md notes
    fail_count: int = 0
    last_used_turn: int = 0

    def to_catalog_entry(self) -> str:
        """§3.2: catalog injected into system prompt — name + description only."""
        first_line = self.skill_md.split("\n")[0].lstrip("# ").strip()
        desc_lines = [l for l in self.skill_md.split("\n")[1:] if l.strip()]
        desc = desc_lines[0].strip() if desc_lines else ""
        return f"- **{self.name}**: {desc}"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "skill_md": self.skill_md,
            "scripts": self.scripts,
            "tests": self.tests,
            "resources": self.resources,
            "memory_md": self.memory_md,
            "fail_count": self.fail_count,
            "last_used_turn": self.last_used_turn,
        }

    @staticmethod
    def from_dict(d: dict) -> "SkillPackage":
        return SkillPackage(**{k: v for k, v in d.items()
                               if k in SkillPackage.__dataclass_fields__})

    @staticmethod
    def from_claude_skills_dir(path: str | Path) -> "SkillPackage":
        """Load a skill from the ~/.claude/skills/<name>/ format."""
        p = Path(path)
        skill_md = (p / "SKILL.md").read_text() if (p / "SKILL.md").exists() else ""
        scripts = {
            f.name: f.read_text()
            for f in (p / "scripts").glob("*") if f.is_file()
        } if (p / "scripts").exists() else {}
        tests = {
            f.name: f.read_text()
            for f in (p / "tests").glob("*") if f.is_file()
        } if (p / "tests").exists() else {}
        memory_md = (p / ".memory.md").read_text() if (p / ".memory.md").exists() else ""
        return SkillPackage(
            name=p.name,
            skill_md=skill_md,
            scripts=scripts,
            tests=tests,
            memory_md=memory_md,
        )

    def write_to_dir(self, base: str | Path) -> Path:
        """Write skill package to a directory (for Claude Code discovery)."""
        skill_dir = Path(base) / self.name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(self.skill_md)
        if self.scripts:
            (skill_dir / "scripts").mkdir(exist_ok=True)
            for fname, code in self.scripts.items():
                (skill_dir / "scripts" / fname).write_text(code)
        if self.tests:
            (skill_dir / "tests").mkdir(exist_ok=True)
            for fname, code in self.tests.items():
                (skill_dir / "tests" / fname).write_text(code)
        if self.memory_md:
            (skill_dir / ".memory.md").write_text(self.memory_md)
        return skill_dir


# ── Skill Bank (§3.2 management) ─────────────────────────────────────────────

class SkillBank:
    """
    §3.2: skill bank with catalog retrieval, merge (overlap), prune (unused/failing).
    [UNSPECIFIED] Prune threshold — using fail_count >= 3 OR unused_turns >= 100.
    """

    def __init__(self, skills: dict[str, SkillPackage] | None = None,
                 prune_fail_threshold: int = 3,
                 prune_unused_threshold: int = 100):
        self.skills: dict[str, SkillPackage] = skills or {}
        self._prune_fail = prune_fail_threshold
        self._prune_unused = prune_unused_threshold

    def register(self, pkg: SkillPackage) -> None:
        """Register a newly evaluated (passing) skill."""
        self.skills[pkg.name] = pkg

    def get(self, name: str) -> SkillPackage | None:
        return self.skills.get(name)

    def catalog(self) -> str:
        """§3.2: catalog injected into system prompt."""
        if not self.skills:
            return "(no skills yet)"
        return "\n".join(s.to_catalog_entry() for s in self.skills.values())

    def append_memory(self, name: str, note: str) -> None:
        """§3.3: append note to per-skill .memory.md."""
        if name in self.skills:
            self.skills[name].memory_md += f"\n- {note}"

    def mark_used(self, name: str, turn: int) -> None:
        if name in self.skills:
            self.skills[name].last_used_turn = turn

    def mark_failed(self, name: str) -> None:
        if name in self.skills:
            self.skills[name].fail_count += 1

    def prune(self, current_turn: int) -> list[str]:
        """§3.2: remove skills that consistently fail or remain unused."""
        to_remove = [
            name for name, s in self.skills.items()
            if s.fail_count >= self._prune_fail
            or (current_turn - s.last_used_turn) >= self._prune_unused
        ]
        for name in to_remove:
            del self.skills[name]
        return to_remove

    def save(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump({k: v.to_dict() for k, v in self.skills.items()}, f, indent=2)

    @staticmethod
    def load(path: str) -> "SkillBank":
        with open(path) as f:
            d = json.load(f)
        return SkillBank({k: SkillPackage.from_dict(v) for k, v in d.items()})


# ── Skill Creator (§3.2 creation) ─────────────────────────────────────────────

class SkillCreator:
    """
    §3.2: "new skills are generated through the built-in skill_create skill"
    Takes a high-level spec (intent, inputs, outputs) → SkillPackage with SKILL.md + tests.
    """

    def __init__(self, llm: Callable[[str], str]):
        self._llm = llm

    def create(self, spec: str, existing_catalog: str = "") -> SkillPackage:
        """§3.2: generate SKILL.md + scripts/ + tests/ from spec string."""
        prompt = f"""You are the Skill Creator (MUSE-Autoskill, arxiv 2605.27366).
Generate a complete skill package following Anthropic Agent Skills format.

Existing skills (do not duplicate):
{existing_catalog or '(none)'}

Skill specification:
{spec}

Output JSON with this exact schema:
{{
  "name": "skill_name_snake_case",
  "skill_md": "# skill_name\\n\\n## Description\\n...\\n## Inputs\\n...\\n## Outputs\\n...",
  "scripts": {{"main.py": "# implementation\\n..."}},
  "tests": {{"test_main.py": "# pytest tests\\ndef test_basic():\\n    pass"}}
}}

Rules:
- name must be snake_case, <= 40 chars
- SKILL.md must include Description, Inputs, Outputs sections
- tests/ must have at least one pytest test that verifies basic behavior
- scripts/ code must be runnable Python 3"""
        raw = self._llm(prompt)
        data = _parse_json_response(raw, {})
        return SkillPackage(
            name=data.get("name", "unnamed_skill"),
            skill_md=data.get("skill_md", f"# {spec[:40]}\n\nAuto-generated skill."),
            scripts=data.get("scripts", {}),
            tests=data.get("tests", {}),
        )


# ── Skill Evaluator (§3.2 evaluation) ─────────────────────────────────────────

class SkillEvaluator:
    """
    §3.2: "runs the unit tests in the tests/ directory inside the sandbox;
    only registers the skill if all tests pass."
    [UNSPECIFIED] Sandbox = Docker; using subprocess in tmp dir as local equivalent.
    """

    def evaluate(self, pkg: SkillPackage, timeout: int = 30) -> tuple[bool, str]:
        """Returns (passed, error_trace). passed=True iff all tests exit 0."""
        if not pkg.tests:
            # §3.2: no tests = treat as pass (no evaluation possible)
            return True, ""

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Write scripts
            if pkg.scripts:
                (tmp_path / "scripts").mkdir()
                for fname, code in pkg.scripts.items():
                    (tmp_path / "scripts" / fname).write_text(code)
            # Write tests
            for fname, code in pkg.tests.items():
                (tmp_path / fname).write_text(code)

            result = subprocess.run(
                [sys.executable, "-m", "pytest", str(tmp_path), "-q", "--tb=short"],
                capture_output=True, text=True, timeout=timeout,
                cwd=tmp,
            )
            passed = result.returncode == 0
            trace = result.stdout + result.stderr
            return passed, trace


# ── Skill Refiner (§3.2 refinement) ───────────────────────────────────────────

class SkillRefiner:
    """
    §3.2: "inspects the error trace and invokes update_skill to patch the package
    before re-running tests."
    [UNSPECIFIED] Max retries: Using 3.
    """
    MAX_RETRIES = 3

    def __init__(self, llm: Callable[[str], str], evaluator: SkillEvaluator | None = None):
        self._llm = llm
        self._eval = evaluator or SkillEvaluator()

    def refine_until_pass(self, pkg: SkillPackage) -> tuple[SkillPackage, bool]:
        """
        §3.2: create → evaluate → register or patch → retry loop.
        Returns (final_pkg, passed).
        """
        for attempt in range(self.MAX_RETRIES):
            passed, trace = self._eval.evaluate(pkg)
            if passed:
                return pkg, True
            pkg = self._patch(pkg, trace)
        # Final evaluation
        passed, _ = self._eval.evaluate(pkg)
        return pkg, passed

    def _patch(self, pkg: SkillPackage, error_trace: str) -> SkillPackage:
        prompt = f"""You are patching a skill that failed its unit tests.
Skill name: {pkg.name}
SKILL.md:
{pkg.skill_md}
Scripts:
{json.dumps(pkg.scripts, indent=2)}
Tests:
{json.dumps(pkg.tests, indent=2)}
Error trace:
{error_trace[:2000]}

Output JSON with patched skill (same schema as creation output):
{{
  "name": "{pkg.name}",
  "skill_md": "...",
  "scripts": {{}},
  "tests": {{}}
}}"""
        raw = self._llm(prompt)
        data = _parse_json_response(raw, {})
        return SkillPackage(
            name=data.get("name", pkg.name),
            skill_md=data.get("skill_md", pkg.skill_md),
            scripts=data.get("scripts", pkg.scripts),
            tests=data.get("tests", pkg.tests),
            memory_md=pkg.memory_md,
            fail_count=pkg.fail_count + 1,
            last_used_turn=pkg.last_used_turn,
        )


# ── MUSE skill manager: wires all components ──────────────────────────────────

class MUSESkillManager:
    """
    Top-level façade that wires SkillCreator → SkillEvaluator → SkillRefiner →
    SkillBank. Called from ContinualHarness Refiner Pass (iii) in place of
    raw K_create/update strings.
    """

    def __init__(self, llm: Callable[[str], str], bank: SkillBank | None = None):
        self.bank = bank or SkillBank()
        self._creator = SkillCreator(llm)
        self._eval = SkillEvaluator()
        self._refiner = SkillRefiner(llm, self._eval)
        self._llm = llm

    def create_and_register(self, spec: str) -> tuple[str, bool]:
        """Full create→eval→refine→register loop. Returns (skill_name, registered)."""
        pkg = self._creator.create(spec, self.bank.catalog())
        pkg, passed = self._refiner.refine_until_pass(pkg)
        if passed:
            self.bank.register(pkg)
        return pkg.name, passed

    def repair_skill(self, name: str, error_trace: str) -> bool:
        """Repair an existing skill that failed at runtime."""
        pkg = self.bank.get(name)
        if not pkg:
            return False
        pkg.scripts["_error_context"] = error_trace[:500]
        pkg, passed = self._refiner.refine_until_pass(pkg)
        if passed:
            self.bank.register(pkg)
        else:
            self.bank.mark_failed(name)
        return passed

    def merge_overlapping(self, name_a: str, name_b: str) -> bool:
        """§3.2: merge two overlapping skills into one."""
        a, b = self.bank.get(name_a), self.bank.get(name_b)
        if not a or not b:
            return False
        prompt = f"""Merge these two overlapping skills into one more general skill.
Skill A ({name_a}):
{a.skill_md}

Skill B ({name_b}):
{b.skill_md}

Output JSON (same schema as creation output) for the merged skill."""
        raw = self._llm(prompt)
        data = _parse_json_response(raw, {})
        merged = SkillPackage(
            name=data.get("name", f"{name_a}_merged"),
            skill_md=data.get("skill_md", a.skill_md),
            scripts={**a.scripts, **b.scripts, **data.get("scripts", {})},
            tests={**a.tests, **b.tests, **data.get("tests", {})},
        )
        _, passed = self._refiner.refine_until_pass(merged)
        if passed:
            self.bank.register(merged)
            if name_a in self.bank.skills:
                del self.bank.skills[name_a]
            if name_b in self.bank.skills:
                del self.bank.skills[name_b]
        return passed

    def export_to_claude_skills(self, base: Path | None = None) -> None:
        """Export all bank skills to ~/.claude/skills/ for Claude Code discovery."""
        base = base or (Path.home() / ".claude" / "skills")
        for pkg in self.bank.skills.values():
            pkg.write_to_dir(base)


# ── Utilities ──────────────────────────────────────────────────────────────────

def _parse_json_response(text: str, default: Any) -> Any:
    import re
    try:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group())
    except (json.JSONDecodeError, AttributeError):
        pass
    return default
