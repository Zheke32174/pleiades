"""
elevator/pruner.py — Prune paths leading to abnormal termination.

Abstract: "pruning only those leading to abnormal termination"

[UNSPECIFIED] The paper defines "abnormal termination" only in passing. We infer
from the context that it means:
  - Paths that decode to provably-illegal instruction sequences
  - Paths that produce invalid control flow (branch into the middle of another
    interpretation's instruction)

The exact pruning criteria, fixpoint algorithm, and interaction with the tile
grammar are entirely UNSPECIFIED.
"""

from __future__ import annotations

import enum
from typing import Optional

from .cfg import InterpCFG, InterpNode
from .interpreter import ByteRole

try:
    import capstone
    _INVALID_MNEMONICS = frozenset({"(bad)", ".byte", "db"})
except ImportError:
    _INVALID_MNEMONICS = frozenset()


class PruneReason(str, enum.Enum):
    """
    [UNSPECIFIED] Paper does not enumerate pruning reasons.
    These are inferred from "abnormal termination" (abstract).
    """
    INVALID_DECODE    = "invalid_decode"     # capstone reports illegal encoding
    DEAD_CODE         = "dead_code"          # no predecessor and not entry
    CONFLICTING_ROLES = "conflicting_roles"  # byte required to be two roles simultaneously


class Pruner:
    """
    Iteratively prune InterpCFG nodes that cannot be part of a valid execution.

    [UNSPECIFIED] Whether pruning is done in a single pass or to fixpoint.
    Using: single forward pass + dead-code elimination pass.
    Alternatives: backward analysis from "abnormal termination" sinks,
    SAT-based feasibility, symbolic execution.
    """

    def __init__(self, cfg: InterpCFG, entry_address: int):
        self.cfg   = cfg
        self.entry = entry_address

    def run(self) -> int:
        """Prune all infeasible nodes. Returns number of pruned nodes."""
        n_pruned = 0
        n_pruned += self._prune_invalid_decodes()
        n_pruned += self._prune_dead_code()
        n_pruned += self._prune_conflicting_roles()
        return n_pruned

    # ── pruning passes ───────────────────────────────────────────────────

    def _prune_invalid_decodes(self) -> int:
        """
        Prune OPCODE nodes whose instruction capstone cannot decode.

        [UNSPECIFIED] Exact definition of "invalid" encoding.
        Using: capstone mnemonic in known-bad set OR instruction id == 0.
        """
        count = 0
        for node in list(self.cfg.nodes.values()):
            if node.pruned:
                continue
            if node.interpretation.role != ByteRole.OPCODE:
                continue
            instr = node.interpretation.instr
            if instr is None:
                self._mark_pruned(node, PruneReason.INVALID_DECODE)
                count += 1
                continue
            mnemonic = getattr(instr, "mnemonic", "").strip().lower()
            if mnemonic in _INVALID_MNEMONICS or getattr(instr, "id", 0) == 0:
                self._mark_pruned(node, PruneReason.INVALID_DECODE)
                count += 1
        return count

    def _prune_dead_code(self) -> int:
        """
        Prune OPCODE nodes unreachable from the entry point.

        [UNSPECIFIED] Whether dead-code elimination is part of Elevator's pruning.
        Using: simple reachability from entry — inferred from "self-contained
        binaries" (abstract).
        """
        reachable: set[str] = set()
        stack = [
            n for n in self.cfg.nodes.values()
            if n.address == self.entry and not n.pruned
               and n.interpretation.role == ByteRole.OPCODE
        ]
        while stack:
            node = stack.pop()
            if node.node_id in reachable:
                continue
            reachable.add(node.node_id)
            for succ in node.successors:
                if not succ.pruned:
                    stack.append(succ)

        count = 0
        for node in self.cfg.nodes.values():
            if node.pruned:
                continue
            if node.interpretation.role == ByteRole.OPCODE:
                if node.node_id not in reachable:
                    self._mark_pruned(node, PruneReason.DEAD_CODE)
                    count += 1
        return count

    def _prune_conflicting_roles(self) -> int:
        """
        Prune DATA nodes at addresses where a live OPCODE node starts — a byte
        cannot simultaneously be the start of an instruction AND pure data.

        [UNSPECIFIED] The paper likely handles this differently (e.g. separate
        execution paths, not pruning one outright). We conservatively keep DATA
        nodes and only prune when an OPCODE node at the same address is already
        live and reachable.
        """
        # Group live nodes by address
        by_addr: dict[int, list[InterpNode]] = {}
        for node in self.cfg.live_nodes():
            by_addr.setdefault(node.address, []).append(node)

        count = 0
        for addr, nodes in by_addr.items():
            roles = {n.interpretation.role for n in nodes}
            # [UNSPECIFIED] The paper explicitly says both interpretations are
            # kept alive. We do NOT prune here by default — conflict resolution
            # is what makes Elevator novel. Left as a TODO.
            # See REPRODUCTION_NOTES.md §Unresolved.
            _ = roles  # intentionally unused — pruning disabled
        return count

    def _mark_pruned(self, node: InterpNode, reason: PruneReason) -> None:
        node.pruned       = True
        node.prune_reason = reason.value
