"""
elevator/cfg.py — Multi-interpretation Control Flow Graph.

Abstract: "we generate separate control flow paths for all interpretations"

[UNSPECIFIED] The paper does not describe its CFG data structure. Every design
choice below is a reasonable inference from the abstract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .interpreter import ByteInterpretation, ByteRole


@dataclass
class InterpNode:
    """
    One node in the multi-interpretation CFG.

    Each node corresponds to ONE interpretation of ONE byte or one basic-block
    boundary.  Multiple nodes can share the same address with different ByteRoles.

    [UNSPECIFIED] Whether the CFG is byte-level or basic-block-level.
    Using: instruction-level nodes (OPCODE nodes represent whole instructions).
    Alternatives: byte-level (finer), basic-block-level (coarser).
    """
    address:        int
    interpretation: ByteInterpretation
    successors:     list["InterpNode"] = field(default_factory=list, repr=False)
    predecessors:   list["InterpNode"] = field(default_factory=list, repr=False)
    pruned:         bool = False
    prune_reason:   Optional[str] = None

    @property
    def node_id(self) -> str:
        return f"{self.address:#010x}:{self.interpretation.role.value}"


@dataclass
class InterpCFG:
    """
    CFG over multi-interpretation nodes.

    Abstract: "produces a separate translation for each feasible [interpretation]"

    [UNSPECIFIED] How overlapping interpretations are merged in the output binary.
    Using: maintain all interpretations independently; merger is a TODO that
    requires full paper details.
    """
    entry_address: int
    nodes:         dict[str, InterpNode] = field(default_factory=dict)

    # ── construction helpers ──────────────────────────────────────────────

    def add_node(self, interp: ByteInterpretation) -> InterpNode:
        node = InterpNode(address=interp.address, interpretation=interp)
        self.nodes[node.node_id] = node
        return node

    def add_edge(self, src: InterpNode, dst: InterpNode) -> None:
        if dst not in src.successors:
            src.successors.append(dst)
        if src not in dst.predecessors:
            dst.predecessors.append(src)

    # ── queries ──────────────────────────────────────────────────────────

    def live_nodes(self) -> list[InterpNode]:
        """Return all non-pruned nodes."""
        return [n for n in self.nodes.values() if not n.pruned]

    def opcode_nodes(self) -> list[InterpNode]:
        """Return live OPCODE nodes (the ones that become translated instructions)."""
        return [
            n for n in self.live_nodes()
            if n.interpretation.role == ByteRole.OPCODE
        ]

    def data_nodes(self) -> list[InterpNode]:
        return [
            n for n in self.live_nodes()
            if n.interpretation.role == ByteRole.DATA
        ]

    def stats(self) -> dict:
        total  = len(self.nodes)
        pruned = sum(1 for n in self.nodes.values() if n.pruned)
        return {
            "total_nodes":  total,
            "pruned_nodes": pruned,
            "live_nodes":   total - pruned,
            "opcode_nodes": len(self.opcode_nodes()),
            "data_nodes":   len(self.data_nodes()),
        }


class CFGBuilder:
    """
    Construct an InterpCFG from multi-interpretation disassembly.

    [UNSPECIFIED] The paper does not detail the CFG construction algorithm.
    Using: linear sweep with fall-through and direct-branch edges.
    """

    def __init__(self, disassembler):
        self.dis = disassembler

    def build(self, entry: int) -> InterpCFG:
        cfg = InterpCFG(entry_address=entry)

        prev_opcode_node: Optional[InterpNode] = None

        for address, interps in self.dis.all_interpretations():
            for interp in interps:
                node = cfg.add_node(interp)

                # [UNSPECIFIED] Fall-through edge policy between interpretations.
                # Using: OPCODE nodes at consecutive addresses get a fall-through edge.
                if (prev_opcode_node is not None
                        and interp.role == ByteRole.OPCODE):
                    prev_instr = prev_opcode_node.interpretation.instr
                    if prev_instr is not None:
                        prev_end = (prev_opcode_node.address
                                    + getattr(prev_instr, "size", 1))
                        if prev_end == address:
                            cfg.add_edge(prev_opcode_node, node)

                if interp.role == ByteRole.OPCODE:
                    prev_opcode_node = node

        return cfg
