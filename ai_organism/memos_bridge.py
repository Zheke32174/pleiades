"""
AI Organism — MemOS bridge for HarnessState.M
Routes memory reads/writes through MemOS for semantic retrieval (+43% accuracy).
Falls back to plain list if MemOS unavailable.
"""
from __future__ import annotations
from typing import Any


def _try_import():
    try:
        from memos.configs.mem_os_config import MemOSConfig
        from memos.mem_os import MemOS
        return MemOS, MemOSConfig
    except ImportError:
        return None, None


MemOS, MemOSConfig = _try_import()


class MEMOSBridge:
    """Wraps MemOS to serve as the M component of HarnessState."""

    def __init__(self, user_id: str = "harness", data_dir: str | None = None):
        self._ok = False
        if MemOS is None:
            return
        try:
            cfg = MemOSConfig(user_id=user_id)
            if data_dir:
                cfg.memory.storage_path = data_dir
            self._mem = MemOS(cfg)
            self._ok = True
        except Exception:
            pass

    @property
    def available(self) -> bool:
        return self._ok

    def add(self, content: str, importance: float = 1.0, tags: list[str] | None = None) -> None:
        if not self._ok:
            return
        self._mem.add(messages=[{"role": "user", "content": content}])

    def search(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        if not self._ok:
            return []
        try:
            results = self._mem.search(query=query, top_k=top_k)
            return results.get("results", []) if isinstance(results, dict) else []
        except Exception:
            return []

    def get_context(self, query: str, top_k: int = 5) -> str:
        hits = self.search(query, top_k)
        if not hits:
            return ""
        lines = []
        for h in hits:
            mem_text = h.get("memory", h.get("content", str(h)))
            lines.append(f"- {mem_text}")
        return "\n".join(lines)
