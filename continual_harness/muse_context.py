"""
MUSE-Autoskill — Context DAG with two-level adaptive compression
§3.4, Figure 4: L1 in-place node summary, L2 span-merge.

KEEP_FIRST=2, KEEP_LAST=2 from Figure 4 caption (PARTIALLY_SPECIFIED).
L1 threshold=8000 tokens, budget=50000 tokens (UNSPECIFIED — see ambiguity_audit.md).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable

# §3.4 Figure 4 caption — PARTIALLY_SPECIFIED (values read from figure)
KEEP_FIRST = 2
KEEP_LAST = 2
# [UNSPECIFIED] per-node token threshold for L1; 8000 chosen from Figure 4 examples
L1_NODE_TOKEN_THRESHOLD = 8000
# [UNSPECIFIED] total budget; Figure 4 uses 50K in its worked example
DEFAULT_BUDGET_TOKENS = 50_000


def _token_count(text: str) -> int:
    # Approximation: 1 token ≈ 4 chars (standard rough estimate)
    return len(text) // 4


@dataclass
class TurnNode:
    """
    §3.4: each turn is a (plan, action, observation) triple.
    parent_id = active chain; history links = full immutable history.
    """
    turn_id: int
    plan: str
    action: str
    observation: str
    is_summary: bool = False
    parent_id: int | None = None         # mutable: defines active chain
    history_prev: int | None = None      # immutable full-history back-link
    history_next: int | None = None      # immutable full-history forward-link
    token_count: int = 0

    def __post_init__(self) -> None:
        if not self.token_count:
            self.token_count = _token_count(self.plan + self.action + self.observation)

    def text(self) -> str:
        return f"[plan] {self.plan}\n[action] {self.action}\n[obs] {self.observation}"


class ContextDAG:
    """
    §3.4: DAG of ReAct turns with two-level adaptive compression.

    Active chain = linked list via parent_id (sent to LLM each step).
    Full history = immutable doubly-linked list via history_prev/next (always replayable).
    """

    def __init__(
        self,
        llm: Callable[[str], str],
        keep_first: int = KEEP_FIRST,
        keep_last: int = KEEP_LAST,
        l1_threshold: int = L1_NODE_TOKEN_THRESHOLD,
        budget: int = DEFAULT_BUDGET_TOKENS,
    ):
        self._llm = llm
        self.keep_first = keep_first
        self.keep_last = keep_last
        self.l1_threshold = l1_threshold
        self.budget = budget
        self._nodes: dict[int, TurnNode] = {}
        self._active_chain: list[int] = []   # ordered turn_ids in active chain
        self._next_id = 0

    def append(self, plan: str, action: str, observation: str) -> TurnNode:
        """Add a new (plan, action, observation) turn; run compression if needed."""
        node = TurnNode(
            turn_id=self._next_id,
            plan=plan,
            action=action,
            observation=observation,
            parent_id=self._active_chain[-1] if self._active_chain else None,
            history_prev=self._next_id - 1 if self._next_id > 0 else None,
        )
        # Update previous node's forward history link (immutable history)
        if self._next_id > 0 and (self._next_id - 1) in self._nodes:
            self._nodes[self._next_id - 1].history_next = self._next_id

        self._nodes[self._next_id] = node
        self._active_chain.append(self._next_id)
        self._next_id += 1
        self._maybe_compress()
        return node

    def active_text(self) -> str:
        """Full active chain as text for LLM context."""
        return "\n---\n".join(
            self._nodes[tid].text() for tid in self._active_chain if tid in self._nodes
        )

    def total_tokens(self) -> int:
        return sum(self._nodes[tid].token_count for tid in self._active_chain if tid in self._nodes)

    # ── Compression ───────────────────────────────────────────────────────────

    def _maybe_compress(self) -> None:
        """§3.4: try L1 first; if still over budget, apply L2."""
        if self.total_tokens() <= self.budget:
            return
        self._l1_compress()
        if self.total_tokens() > self.budget:
            self._l2_compress()

    def _compressible_range(self) -> list[int]:
        """Middle of active chain, excluding first keep_first and last keep_last."""
        if len(self._active_chain) <= self.keep_first + self.keep_last:
            return []
        return self._active_chain[self.keep_first: len(self._active_chain) - self.keep_last]

    def _l1_compress(self) -> None:
        """
        §3.4 Level-1: replace each oversized node in the compressible range
        with a compact in-place summary. Less destructive — preserves per-turn structure.
        """
        for tid in self._compressible_range():
            node = self._nodes.get(tid)
            if node and not node.is_summary and node.token_count > self.l1_threshold:
                summary = self._summarize_node(node.text())
                node.plan = "[L1-summary]"
                node.action = ""
                node.observation = summary
                node.token_count = _token_count(summary)
                node.is_summary = True

    def _l2_compress(self) -> None:
        """
        §3.4 Level-2: merge the entire compressible span into one synthetic summary node
        when L1 alone is insufficient. Original nodes remain in full history.
        """
        span = self._compressible_range()
        if not span:
            return
        span_text = "\n---\n".join(
            self._nodes[tid].text() for tid in span if tid in self._nodes
        )
        merged_summary = self._summarize_node(span_text, label="span-merge")
        # Create synthetic node
        synthetic = TurnNode(
            turn_id=self._next_id,
            plan="[L2-span-summary]",
            action="",
            observation=merged_summary,
            is_summary=True,
            parent_id=self._active_chain[self.keep_first - 1] if self.keep_first > 0 else None,
        )
        self._nodes[self._next_id] = synthetic
        self._next_id += 1

        # Rebuild active chain: pinned_first + [synthetic] + pinned_last
        pinned_first = self._active_chain[: self.keep_first]
        pinned_last = self._active_chain[len(self._active_chain) - self.keep_last:]
        self._active_chain = pinned_first + [synthetic.turn_id] + pinned_last

    def _summarize_node(self, text: str, label: str = "summary") -> str:
        return self._llm(
            f"Summarize the following agent trajectory turns concisely (1-3 sentences):\n\n{text[:3000]}"
        )

    def replay_history(self) -> list[TurnNode]:
        """§3.4: full history is always replayable via history_prev/next links."""
        if not self._nodes:
            return []
        # Walk forward from node 0
        result, cur = [], 0
        while cur in self._nodes:
            result.append(self._nodes[cur])
            nxt = self._nodes[cur].history_next
            if nxt is None:
                break
            cur = nxt
        return result
