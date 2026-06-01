"""
Continual Harness — Two-Loop Architecture
§3.1: inner loop (agent acts) + outer loop (Refiner edits H every F steps after W warmup).
Reset-free: environment never resets between refinement cycles.

[UNSPECIFIED] F (refinement frequency): Using 50. Paper evaluates at game scale (thousands
of steps); F=50 is reasonable for agent task scale.
[UNSPECIFIED] W (warmup steps): Using 10. Paper mentions warmup but gives no value.
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any, Callable, Iterator

from .harness_state import HarnessEdit, HarnessState, merge
from .refiner import Refiner, detect_failure_signatures

# §3.1 — loop parameters (both UNSPECIFIED in paper, see audit)
DEFAULT_F = 50   # refinement frequency: every F steps
DEFAULT_W = 10   # warmup: first W steps, no refinement


class ContinualHarness:
    """
    §3.1: Two-loop architecture.

    Inner loop: agent reads (s_t, H_t, trajectory) → emits a_t
    Outer loop: every F steps after W warmup, Refiner reads τ_{t-F:t} → emits Δ → H_{t+1} = H_t ⊕ Δ

    The agent and refiner share the same model (§3.1), passed as llm_callable.
    """

    def __init__(
        self,
        llm_callable: Callable[[str], str],
        initial_state: HarnessState | None = None,
        F: int = DEFAULT_F,
        W: int = DEFAULT_W,
        checkpoint_dir: str | None = None,
    ):
        self.state = initial_state or HarnessState()
        self.refiner = Refiner(llm_callable)
        self.llm = llm_callable
        self.F = F
        self.W = W
        self.checkpoint_dir = Path(checkpoint_dir) if checkpoint_dir else None
        self._trajectory: list[dict] = []
        self._step = 0
        self._refinement_count = 0

    def step(self, observation: str) -> str:
        """
        §3.1 inner loop: one agent step.
        Agent reads (s_t, H_t, τ) → emits a_t.
        """
        prompt = self._build_agent_prompt(observation)
        action = self.llm(prompt)

        self._trajectory.append({
            "step": self._step,
            "role": "agent",
            "observation": observation,
            "action": action,
            "timestamp": time.time(),
        })
        self._step += 1

        # §3.1 outer loop trigger: every F steps after W warmup
        if self._step > self.W and self._step % self.F == 0:
            self._run_refinement()

        return action

    def run(self, observation_stream: Iterator[str]) -> Iterator[str]:
        """Drive the full loop from an observation stream. Yields actions."""
        for obs in observation_stream:
            yield self.step(obs)

    def _run_refinement(self) -> None:
        """
        §3.2: Refiner reads τ_{t-F:t}, emits Δ, applies merge.
        Refinement information accumulates monotonically (§3.2).
        """
        window = self._trajectory[-self.F:]
        failures = detect_failure_signatures(
            " ".join(s.get("action", "") + " " + s.get("observation", "") for s in window)
        )
        delta: HarnessEdit = self.refiner.refine(self.state, window, failures)
        self.state = merge(self.state, delta)
        self._refinement_count += 1

        if self.checkpoint_dir:
            self._save_checkpoint(delta)

    def _build_agent_prompt(self, observation: str) -> str:
        """Compose (s_t, H_t, τ_excerpt) into the agent's prompt."""
        mem_str = "\n".join(
            f"- [{e.importance:.1f}] {e.content}"
            for e in sorted(self.state.M, key=lambda e: -e.importance)[:10]
        )
        skills_str = "\n".join(f"- {k}" for k in self.state.K)
        agents_str = "\n".join(f"- {k}" for k in self.state.G)
        recent = self._trajectory[-5:] if self._trajectory else []
        recent_str = "\n".join(
            f"  step {s['step']}: {s.get('action','')[:200]}" for s in recent
        )
        return f"""{self.state.p}

## Current observation
{observation}

## Available skills
{skills_str or '(none yet)'}

## Available sub-agents
{agents_str or '(none yet)'}

## Memory (top by importance)
{mem_str or '(none yet)'}

## Recent actions
{recent_str or '(none yet)'}

Emit your next action:"""

    def _save_checkpoint(self, delta: HarnessEdit) -> None:
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.state.save(str(self.checkpoint_dir / f"harness_step_{self._step}.json"))
        with open(self.checkpoint_dir / f"delta_step_{self._step}.json", "w") as f:
            json.dump(delta.to_dict(), f, indent=2)

    @property
    def stats(self) -> dict:
        return {
            "step": self._step,
            "refinement_cycles": self._refinement_count,
            "skills": len(self.state.K),
            "subagents": len(self.state.G),
            "memories": len(self.state.M),
        }
