"""
Continual Harness — HarnessState
§2.2: H = (p, G, K, M)

[UNSPECIFIED] Sub-agent and skill structures — paper says "specialized modules" and
"reusable routines" but gives no schema. Using name→spec string dicts matching the
meta-tool API described in §2.2 (define_agent, run_code calls emit string specs).
[UNSPECIFIED] Memory entry schema — paper mentions "facts, strategies, observations"
and an importance field used for demotion. Using list[dict] with 'content' and
'importance' (float 0–1) based on §3.2 "demotes importance for areas the agent has
moved past."
"""
from __future__ import annotations
import copy
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MemoryEntry:
    content: str
    importance: float = 1.0          # §3.2: demoted toward 0 when no longer relevant
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"content": self.content, "importance": self.importance, "tags": self.tags}

    @staticmethod
    def from_dict(d: dict) -> "MemoryEntry":
        return MemoryEntry(d["content"], d.get("importance", 1.0), d.get("tags", []))


@dataclass
class HarnessState:
    """
    §2.2 — Agentic harness H = (p, G, K, M).

    p  — system prompt: instructions and strategic guidance to M at each step
    G  — sub-agents: dict[name, spec_string] of specialized modules
    K  — skills: dict[name, code_or_spec] of reusable routines (text or executable)
    M  — memory: list[MemoryEntry] — persistent knowledge accumulated over trajectory
    """
    p: str = ""
    G: dict[str, str] = field(default_factory=dict)
    K: dict[str, str] = field(default_factory=dict)
    M: list[MemoryEntry] = field(default_factory=list)

    def clone(self) -> "HarnessState":
        return HarnessState(
            p=self.p,
            G=copy.deepcopy(self.G),
            K=copy.deepcopy(self.K),
            M=copy.deepcopy(self.M),
        )

    def to_dict(self) -> dict:
        return {
            "p": self.p,
            "G": self.G,
            "K": self.K,
            "M": [e.to_dict() for e in self.M],
        }

    @staticmethod
    def from_dict(d: dict) -> "HarnessState":
        return HarnessState(
            p=d.get("p", ""),
            G=d.get("G", {}),
            K=d.get("K", {}),
            M=[MemoryEntry.from_dict(e) for e in d.get("M", [])],
        )

    def save(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @staticmethod
    def load(path: str) -> "HarnessState":
        with open(path) as f:
            return HarnessState.from_dict(json.load(f))


@dataclass
class HarnessEdit:
    """
    Δ = (Δp, ΔG, ΔK, ΔM) emitted by the Refiner each cycle.
    §3.1: "emits per-component edits Δ=(Δp, ΔG, ΔK, ΔM)"
    §3.1: "p replaced by Δp; G, K, M receiving CRUD-style operations"
    """
    # §3.1: prompt is fully replaced
    new_p: str | None = None

    # CRUD for sub-agents: §3.2 creates/edits/deletes G entries
    G_create: dict[str, str] = field(default_factory=dict)
    G_update: dict[str, str] = field(default_factory=dict)
    G_delete: list[str] = field(default_factory=list)

    # CRUD for skills: §3.2 codifies new skills and repairs broken ones
    K_create: dict[str, str] = field(default_factory=dict)
    K_update: dict[str, str] = field(default_factory=dict)
    K_delete: list[str] = field(default_factory=list)

    # CRUD for memory: §3.2 adds/updates stale entries/demotes
    M_add: list[MemoryEntry] = field(default_factory=list)
    M_updates: list[dict] = field(default_factory=list)   # {index, content, importance}
    M_demotions: list[dict] = field(default_factory=list) # {index, new_importance}

    def to_dict(self) -> dict:
        return {
            "new_p": self.new_p,
            "G_create": self.G_create,
            "G_update": self.G_update,
            "G_delete": self.G_delete,
            "K_create": self.K_create,
            "K_update": self.K_update,
            "K_delete": self.K_delete,
            "M_add": [e.to_dict() for e in self.M_add],
            "M_updates": self.M_updates,
            "M_demotions": self.M_demotions,
        }


def merge(state: HarnessState, delta: HarnessEdit) -> HarnessState:
    """
    §3.1: H_{t+1} = H_t ⊕ Δ
    Prompt is fully replaced; G, K, M receive CRUD operations.
    [UNSPECIFIED] Conflict resolution for simultaneous create+update on same key.
    Using: last-write-wins (update overwrites create).
    """
    new = state.clone()

    if delta.new_p is not None:
        new.p = delta.new_p

    for name, spec in delta.G_create.items():
        new.G[name] = spec
    for name, spec in delta.G_update.items():
        new.G[name] = spec
    for name in delta.G_delete:
        new.G.pop(name, None)

    for name, code in delta.K_create.items():
        new.K[name] = code
    for name, code in delta.K_update.items():
        new.K[name] = code
    for name in delta.K_delete:
        new.K.pop(name, None)

    new.M.extend(delta.M_add)
    for upd in delta.M_updates:
        idx = upd["index"]
        if 0 <= idx < len(new.M):
            new.M[idx].content = upd.get("content", new.M[idx].content)
            new.M[idx].importance = upd.get("importance", new.M[idx].importance)
    for dem in delta.M_demotions:
        idx = dem["index"]
        if 0 <= idx < len(new.M):
            new.M[idx].importance = dem["new_importance"]

    return new
