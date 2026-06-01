"""
elevator — Deterministic Fully-Static Whole-Binary Translation without Heuristics.

Framework implementation based on:
  Chen, McGowan, Franz (2026). "Deterministic Fully-Static Whole-Binary
  Translation without Heuristics." arXiv:2605.08419

IMPORTANT: This implementation is based solely on the paper abstract.
The full paper PDF was unavailable at implementation time. See
REPRODUCTION_NOTES.md for a complete list of unspecified choices.
"""

from .interpreter import MultiInterpretationDisassembler, ByteRole, ByteInterpretation
from .cfg import InterpCFG, CFGBuilder, InterpNode
from .pruner import Pruner
from .tiles import Tile, TileContext, FirstMatchSelector
from .x86_to_aarch64 import default_tile_set, REG_MAP
from .translator import Translator, TranslationResult

__all__ = [
    "MultiInterpretationDisassembler", "ByteRole", "ByteInterpretation",
    "InterpCFG", "CFGBuilder", "InterpNode",
    "Pruner",
    "Tile", "TileContext", "FirstMatchSelector",
    "default_tile_set", "REG_MAP",
    "Translator", "TranslationResult",
]
