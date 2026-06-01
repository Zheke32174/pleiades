"""
Purple-Team Factory → Continual Harness adapter.

Maps the octo factory's session.json + scenario transcripts into the
trajectory format that ContinualHarness.refiner expects, and wires
factory agent runs as the "environment" steps in the inner loop.

This is the integration point between:
  - Continual Harness (arxiv 2605.09998): the self-improving harness framework
  - Hermes Agent Self-Evolution: offline GEPA skill optimizer (see hermes_bridge.py)
  - Purple-team octo factory: the existing CI/red-team task runner
"""
from __future__ import annotations
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from .harness_state import HarnessState, MemoryEntry
from .loop import ContinualHarness

FACTORY_DIR = Path("/workspaces/gentoo/.octo/factory")
SKILLS_DIR = Path.home() / ".claude" / "skills"
CLAUDE_JSON = Path.home() / ".claude.json"


# ── Factory session → trajectory ──────────────────────────────────────────────

def load_factory_trajectory(factory_run_dir: str | Path) -> list[dict]:
    """
    Convert an octo factory session into Continual Harness trajectory format.
    Reads scenarios-all.md and nqs-scores.json from the run directory.
    """
    run_dir = Path(factory_run_dir)
    steps = []

    scenarios_path = run_dir / "scenarios-all.md"
    scores_path = run_dir / "nqs-scores.json"

    scenarios_text = scenarios_path.read_text() if scenarios_path.exists() else ""
    scores = {}
    if scores_path.exists():
        scores = json.loads(scores_path.read_text())

    # Parse each scenario block as one trajectory step
    for i, block in enumerate(_split_scenario_blocks(scenarios_text)):
        score = scores.get(str(i), {}).get("score", None)
        steps.append({
            "step": i,
            "role": "agent",
            "observation": block.get("spec", ""),
            "action": block.get("result", ""),
            "score": score,
            "content": f"SCENARIO: {block.get('spec','')}\nRESULT: {block.get('result','')}",
        })

    return steps


def _split_scenario_blocks(text: str) -> list[dict]:
    """Split scenarios-all.md into per-scenario dicts."""
    blocks = []
    current: dict[str, str] = {}
    for line in text.splitlines():
        if line.startswith("## Scenario"):
            if current:
                blocks.append(current)
            current = {"spec": "", "result": ""}
        elif line.startswith("**Result"):
            current["result"] = line
        else:
            current["spec"] = current.get("spec", "") + line + "\n"
    if current:
        blocks.append(current)
    return blocks


# ── Harness state ↔ Claude Code skills ───────────────────────────────────────

def export_skills_to_claude(state: HarnessState) -> None:
    """
    Write evolved skills from HarnessState.K back to ~/.claude/skills/
    so Claude Code picks them up on the next session.
    Each skill becomes a SKILL.md in its own directory.
    """
    for skill_name, skill_spec in state.K.items():
        skill_dir = SKILLS_DIR / f"ch-{skill_name}"
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(f"# {skill_name}\n\n{skill_spec}\n")


def import_skills_from_claude(state: HarnessState) -> HarnessState:
    """
    Load existing Claude Code skills (those prefixed ch-) back into HarnessState.K.
    Used to bootstrap a new run from a previously evolved harness.
    """
    for skill_dir in SKILLS_DIR.glob("ch-*/"):
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            skill_name = skill_dir.name.removeprefix("ch-")
            state.K[skill_name] = skill_md.read_text()
    return state


# ── Factory run wrapper ───────────────────────────────────────────────────────

def run_factory_with_harness(
    spec_path: str,
    harness: ContinualHarness,
    satisfaction_target: float = 0.85,
) -> dict[str, Any]:
    """
    Run one octo factory cycle, then feed the resulting trajectory back into
    the Continual Harness refiner. Returns factory session dict + harness stats.

    This implements the outer loop at factory granularity:
      1. Factory runs agent scenarios (inner loop episodes)
      2. Refiner reads resulting trajectories → updates H
      3. Updated H is exported back to Claude Code skills for next factory run
    """
    # Inject current harness system prompt into the factory spec env var
    env = os.environ.copy()
    env["CH_SYSTEM_PROMPT"] = harness.state.p
    env["CH_SKILLS"] = json.dumps(list(harness.state.K.keys()))

    result = subprocess.run(
        ["claude", "-p", f"Run octo factory on {spec_path}"],
        capture_output=True, text=True, env=env, timeout=600,
    )

    # Find the most recent factory run
    runs = sorted(FACTORY_DIR.glob("factory-*/"))
    if not runs:
        return {"error": "no factory run found", "harness": harness.stats}

    latest_run = runs[-1]
    trajectory = load_factory_trajectory(latest_run)

    # Feed trajectory into harness — each scenario is one "step"
    for step in trajectory:
        obs = step.get("observation", "")
        harness._trajectory.append(step)
        harness._step += 1
        if harness._step > harness.W and harness._step % harness.F == 0:
            harness._run_refinement()

    # Export evolved skills back to Claude Code
    export_skills_to_claude(harness.state)

    session_path = latest_run / "session.json"
    session = json.loads(session_path.read_text()) if session_path.exists() else {}
    return {"session": session, "harness": harness.stats, "run_dir": str(latest_run)}
