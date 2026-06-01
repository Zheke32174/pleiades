"""
Continual Harness — implementation of arxiv 2605.09998
"Continual Harness: Online Adaptation for Self-Improving Foundation Agents"

Integrated with:
  - Purple-team octo factory (purple_adapter.py)
  - Hermes Agent Self-Evolution / DSPy+GEPA (hermes_bridge.py)

NOTE: The polyglot testing suite (/workspaces/gentoo/polyglot-testing/) is a
SEPARATE project from this AI evolution infrastructure. It has its own git repo
and its own scope. See /workspaces/gentoo/polyglot-testing/README.md.
"""
from .harness_state import HarnessState, HarnessEdit, MemoryEntry, merge
from .refiner import Refiner, detect_failure_signatures
from .loop import ContinualHarness
from .muse_skill import MUSESkillManager, SkillBank, SkillPackage
from .muse_context import ContextDAG, TurnNode

__all__ = [
    "HarnessState", "HarnessEdit", "MemoryEntry", "merge",
    "Refiner", "detect_failure_signatures",
    "ContinualHarness",
    "MUSESkillManager", "SkillBank", "SkillPackage",
    "ContextDAG", "TurnNode",
]
