"""
Sentence embedding wrapper for RePro.

Uses all-MiniLM-L6-v2 as specified in §4.1.
"""

from __future__ import annotations

from typing import List

import numpy as np


_MODEL = None


def _get_model():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _MODEL


def embed(texts: List[str]) -> np.ndarray:
    """Return L2-normalised embeddings, shape (N, D)."""
    model = _get_model()
    vecs = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    return vecs


def cosine_similarity_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Cosine similarity between rows of a and rows of b.

    Since embeddings are L2-normalised, this is just the dot product.
    Returns shape (len(a), len(b)).
    """
    return a @ b.T


def top_k_indices(query_vec: np.ndarray, corpus_vecs: np.ndarray, k: int) -> List[int]:
    """Return indices of the k most similar rows in corpus_vecs to query_vec."""
    sims = query_vec @ corpus_vecs.T
    k = min(k, len(sims))
    return list(np.argsort(sims)[::-1][:k])
