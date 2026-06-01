"""
Hermes Agent Self-Evolution ↔ Continual Harness bridge.

These two systems are COMPLEMENTARY, not competing:

  Continual Harness (arxiv 2605.09998):
    - Online adaptation, within a single run
    - Refiner edits H = (p, G, K, M) mid-episode without resets
    - Fast, broad: touches all four harness components each cycle

  Hermes Agent Self-Evolution (NousResearch/hermes-agent-self-evolution):
    - Offline optimization, between runs
    - Uses DSPy + GEPA to evolve individual skill files via complete episodes + reset
    - Slow, surgical: one skill at a time, many eval iterations, constraint-gated

Integration pattern:
  1. Factory run N   → Continual Harness online refines H in real time
  2. End of run N    → Export H.K to Claude Code skills (purple_adapter.export_skills_to_claude)
  3. Between runs    → Hermes Self-Evolution runs GEPA on the most-updated skills
  4. Start of run N+1 → Import GEPA-optimized skills back into H.K (bootstrap_updating mode)

This matches the "bootstrap updating" variant described in §4.1 of the paper, where a
successfully refined harness from run N seeds run N+1 with refinement continuing.
"""
from __future__ import annotations
import subprocess
import json
from pathlib import Path

HERMES_EVOLVE = "python3 -m evolution.skills.evolve_skill"
HERMES_REPO = Path("/workspaces/gentoo/tools/hermes-agent-self-evolution")
SKILLS_DIR = Path.home() / ".claude" / "skills"


def evolve_skill_offline(
    skill_name: str,
    iterations: int = 10,
    eval_source: str = "synthetic",
) -> dict:
    """
    Run the Hermes GEPA optimizer on a single Claude Code skill between factory runs.

    skill_name: name of a ch-{skill_name} directory in ~/.claude/skills/
    iterations: GEPA evolution iterations (more = better quality, higher cost)
    eval_source: 'synthetic' (generated) or 'sessiondb' (real Claude Code history)

    Returns dict with {success, skill_name, output}.
    """
    skill_dir = SKILLS_DIR / f"ch-{skill_name}"
    if not skill_dir.exists():
        return {"success": False, "error": f"skill dir not found: {skill_dir}"}

    cmd = [
        "python3", "-m", "evolution.skills.evolve_skill",
        "--skill", str(skill_dir / "SKILL.md"),
        "--iterations", str(iterations),
        "--eval-source", eval_source,
    ]
    result = subprocess.run(
        cmd,
        cwd=HERMES_REPO,
        capture_output=True,
        text=True,
        timeout=1800,
    )
    return {
        "success": result.returncode == 0,
        "skill_name": skill_name,
        "output": result.stdout[-2000:] if result.stdout else result.stderr[-2000:],
    }


def evolve_top_skills(
    harness_stats: dict,
    top_n: int = 3,
    iterations: int = 10,
) -> list[dict]:
    """
    After a Continual Harness run, evolve the N most-recently-updated skills offline.
    Mirrors Figure 3 of the paper: a small subset of components gets most updates.

    harness_stats: output of ContinualHarness.stats (has 'skills' count, not names yet —
    extend ContinualHarness.stats to include skill_update_counts for full integration).
    """
    # [UNSPECIFIED] Which skills to prioritize — paper tracks update counts (Fig 3).
    # Using: all ch-* skills, limited to top_n by mtime (most recently written = most evolved).
    ch_skills = sorted(
        (SKILLS_DIR / f"ch-{d.name.removeprefix('ch-')}" for d in SKILLS_DIR.glob("ch-*/")),
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
        reverse=True,
    )[:top_n]

    results = []
    for skill_path in ch_skills:
        skill_name = skill_path.name.removeprefix("ch-")
        results.append(evolve_skill_offline(skill_name, iterations=iterations))

    return results


def bootstrap_harness_from_evolved_skills(state) -> None:
    """
    §4.1 'bootstrap updating' variant: load GEPA-optimized skills into harness state
    so run N+1 starts from the best available skill set.
    """
    from .purple_adapter import import_skills_from_claude
    import_skills_from_claude(state)
