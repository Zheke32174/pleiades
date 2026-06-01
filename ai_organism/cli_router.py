"""
AI Organism — CLI Cost Router
Routes tasks to the appropriate CLI (Claude Code / Codex / Cursor) based on
risk/complexity, and injects agent-rules-books AGENTS.md rules for each target.

CodexSaver (fendouai/CodexSaver) provides the delegate_task MCP tool for
low-risk tasks. agent-rules-books (ciembor/agent-rules-books) provides the
engineering rules injected per CLI target.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

CLI = Literal["claude-code", "codex", "cursor"]

# Paths
_ARB = Path("/workspaces/gentoo/tools/agent-rules-books")
_RULES_CACHE: dict[str, str] = {}

# ── Risk classifier ───────────────────────────────────────────────────────────

_HIGH_RISK = re.compile(
    r"(auth|security|payment|migration|database schema|drop table|"
    r"secret|credential|production deploy|rollback|encryption)",
    re.I,
)
_ARCH_RISK = re.compile(
    r"(architect|redesign|refactor entire|new service|api design|"
    r"domain model|system design|data model)",
    re.I,
)


@dataclass
class RoutingDecision:
    cli: CLI
    risk: str          # "low" | "medium" | "high"
    rules_injected: list[str]
    delegate_via_codexsaver: bool
    rationale: str


def route(task: str, files: list[str] | None = None) -> RoutingDecision:
    """
    Classify a task and return routing decision with rules to inject.

    High-risk / architectural → claude-code (full context, max capability)
    Medium (refactor, review)  → claude-code with relevant arb- rules
    Low-risk bounded            → codex via CodexSaver delegate_task
    """
    high = bool(_HIGH_RISK.search(task))
    arch = bool(_ARCH_RISK.search(task))

    if high:
        return RoutingDecision(
            cli="claude-code",
            risk="high",
            rules_injected=[],
            delegate_via_codexsaver=False,
            rationale="Security/production-critical — full Claude Code, no delegation",
        )

    if arch:
        rules = _load_rules(["domain-driven-design", "designing-data-intensive-applications"])
        return RoutingDecision(
            cli="claude-code",
            risk="medium",
            rules_injected=rules,
            delegate_via_codexsaver=False,
            rationale="Architectural work — Claude Code + DDD/DDIA rules",
        )

    # Detect refactoring/review work
    if re.search(r"(refactor|clean up|code review|improve|lint|format|test|doc)", task, re.I):
        rules = _load_rules(["clean-code", "refactoring"])
        return RoutingDecision(
            cli="codex",
            risk="low",
            rules_injected=rules,
            delegate_via_codexsaver=True,
            rationale="Low-risk quality work — delegate via CodexSaver with Clean Code rules",
        )

    # Default low-risk: delegate
    rules = _load_rules(["clean-code"])
    return RoutingDecision(
        cli="codex",
        risk="low",
        rules_injected=rules,
        delegate_via_codexsaver=True,
        rationale="Bounded task — delegate via CodexSaver for cost savings",
    )


def _load_rules(books: list[str]) -> list[str]:
    loaded = []
    for book in books:
        if book not in _RULES_CACHE:
            p = _ARB / book / f"{book}.mini.md"
            if p.exists():
                _RULES_CACHE[book] = p.read_text()
            else:
                _RULES_CACHE[book] = ""
        if _RULES_CACHE[book]:
            loaded.append(book)
    return loaded


def rules_text(books: list[str]) -> str:
    """Return concatenated rules text for the given book names."""
    parts = []
    for book in books:
        _load_rules([book])
        if _RULES_CACHE.get(book):
            parts.append(f"## Rules: {book}\n\n{_RULES_CACHE[book]}")
    return "\n\n---\n\n".join(parts)


def build_codexsaver_payload(task: str, files: list[str], decision: RoutingDecision) -> dict:
    """Build the MCP delegate_task payload for CodexSaver."""
    constraints = []
    if decision.rules_injected:
        constraints.append(
            f"Apply these engineering rules:\n\n{rules_text(decision.rules_injected)}"
        )
    return {
        "instruction": task,
        "files": files or [],
        "constraints": constraints,
    }


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    task = " ".join(sys.argv[1:]) or "refactor the auth module to be cleaner"
    decision = route(task)
    print(f"CLI:       {decision.cli}")
    print(f"Risk:      {decision.risk}")
    print(f"Delegate:  {decision.delegate_via_codexsaver}")
    print(f"Rules:     {decision.rules_injected}")
    print(f"Rationale: {decision.rationale}")
