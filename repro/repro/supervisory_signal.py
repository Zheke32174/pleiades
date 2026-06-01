"""
Supervisory Signal Design (§3.1).

Three-level guide extraction → source grounding → standardization → filtering.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from repro import embeddings, prompts


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class Criterion:
    fact: str
    scope: str
    source_sentences: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        return f"<fact>{self.fact}</fact> <scope>{self.scope}</scope>"


@dataclass
class PaperGuide:
    framework: str        # level-1 bullet list
    configuration: str    # level-2 bullet list
    paragraphs: List[str] # level-3 selected sentences per paragraph


# ── LLM caller (LiteLLM) ──────────────────────────────────────────────────────

def _call_llm(model: str, system: str, user: str) -> str:
    from litellm import completion
    resp = completion(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content.strip()


# ── Level-1 and Level-2 Guide Extraction ──────────────────────────────────────

class GuideExtractor:
    """Extract 3-level guidance from the paper (§3.1)."""

    # §4.1: Deepseek-V3 for supervisory signal design
    DESIGN_MODEL = "deepseek/deepseek-chat"

    def extract_framework(self, title: str, intro_text: str) -> str:
        return _call_llm(
            self.DESIGN_MODEL,
            prompts.FRAMEWORK_GUIDE_SYSTEM,
            prompts.FRAMEWORK_GUIDE_USER_TEMPLATE.format(
                title=title, text=intro_text
            ),
        )

    def extract_configuration(self, experiment_text: str) -> str:
        return _call_llm(
            self.DESIGN_MODEL,
            prompts.CONFIGURATION_GUIDE_SYSTEM,
            prompts.CONFIGURATION_GUIDE_USER_TEMPLATE.format(text=experiment_text),
        )

    def extract_paragraph_sentences(self, paragraph: str) -> List[int]:
        """Return selected sentence indices (0-based) for one paragraph."""
        indexed = _index_paragraph(paragraph)
        raw = _call_llm(
            self.DESIGN_MODEL,
            prompts.GUIDE_EXTRACTION_SYSTEM,
            indexed,
        )
        try:
            indices = json.loads(raw)
            # paper uses 1-based in the prompt example; convert to 0-based
            return [i - 1 for i in indices if isinstance(i, int) and i >= 1]
        except (json.JSONDecodeError, ValueError):
            return []

    def extract_all(
        self,
        title: str,
        intro_text: str,
        experiment_text: str,
        paragraphs: List[str],
    ) -> PaperGuide:
        framework = self.extract_framework(title, intro_text)
        configuration = self.extract_configuration(experiment_text)
        selected: List[str] = []
        sentences_all: List[str] = []
        for para in paragraphs:
            sents = _split_sentences(para)
            indices = self.extract_paragraph_sentences(para)
            for i in indices:
                if 0 <= i < len(sents):
                    selected.append(sents[i])
            sentences_all.extend(sents)
        return PaperGuide(
            framework=framework,
            configuration=configuration,
            paragraphs=selected,
        )


# ── Source Grounding ───────────────────────────────────────────────────────────

class SourceGrounder:
    """Ground each extracted sentence to its top-3 source paragraphs (§3.1)."""

    # §3.1: top-3 paragraphs per criterion unit
    TOP_K = 3

    def __init__(self, paragraphs: List[str]):
        self.paragraphs = paragraphs
        self._para_vecs: Optional[np.ndarray] = None

    def _para_embeddings(self) -> np.ndarray:
        if self._para_vecs is None:
            self._para_vecs = embeddings.embed(self.paragraphs)
        return self._para_vecs

    def ground(self, sentence: str) -> List[str]:
        """Return top-3 source paragraphs for a guidance sentence."""
        q = embeddings.embed([sentence])
        idxs = embeddings.top_k_indices(q[0], self._para_embeddings(), self.TOP_K)
        return [self.paragraphs[i] for i in idxs]


# ── Standardization ────────────────────────────────────────────────────────────

class CriteriaStandardizer:
    """Convert guidance sentences to atomic fact-scope criteria (§3.1)."""

    DESIGN_MODEL = "deepseek/deepseek-chat"

    def standardize(self, sentences: List[str]) -> List[Criterion]:
        if not sentences:
            return []
        block = "\n".join(f"- {s}" for s in sentences)
        raw = _call_llm(
            self.DESIGN_MODEL,
            prompts.STANDARDIZATION_SYSTEM,
            prompts.STANDARDIZATION_USER_TEMPLATE.format(sentences=block),
        )
        return _parse_criteria(raw)


# ── Filtering ──────────────────────────────────────────────────────────────────

class CriteriaFilter:
    """
    Two-step filter: cluster-based dedup + LLM semantic filter (§3.1).

    Clustering algorithm: UNSPECIFIED in paper. We use AgglomerativeClustering
    with cosine distance threshold 0.15. [UNSPECIFIED-1]
    """

    DESIGN_MODEL = "deepseek/deepseek-chat"
    # [UNSPECIFIED-1] distance threshold for cluster dedup
    CLUSTER_DISTANCE_THRESHOLD = 0.15

    def _cluster_dedup(self, criteria: List[Criterion]) -> List[Criterion]:
        if len(criteria) <= 1:
            return criteria
        try:
            from sklearn.cluster import AgglomerativeClustering
        except ImportError:
            return criteria

        texts = [str(c) for c in criteria]
        vecs = embeddings.embed(texts)
        # cosine distance = 1 - cosine_similarity; vecs are already normalised
        dist_matrix = 1.0 - (vecs @ vecs.T)
        dist_matrix = np.clip(dist_matrix, 0.0, 2.0)

        clustering = AgglomerativeClustering(
            n_clusters=None,
            metric="precomputed",
            linkage="average",
            distance_threshold=self.CLUSTER_DISTANCE_THRESHOLD,
        )
        labels = clustering.fit_predict(dist_matrix)

        # keep one representative per cluster (closest to centroid)
        kept: List[Criterion] = []
        for label in sorted(set(labels)):
            cluster_idxs = [i for i, l in enumerate(labels) if l == label]
            cluster_vecs = vecs[cluster_idxs]
            centroid = cluster_vecs.mean(axis=0)
            centroid /= np.linalg.norm(centroid) + 1e-9
            sims = cluster_vecs @ centroid
            best = cluster_idxs[int(np.argmax(sims))]
            kept.append(criteria[best])
        return kept

    def _llm_semantic_filter(self, criteria: List[Criterion]) -> List[Criterion]:
        if not criteria:
            return criteria
        numbered = "\n".join(f"{i}. {c}" for i, c in enumerate(criteria))
        raw = _call_llm(
            self.DESIGN_MODEL,
            prompts.SEMANTIC_FILTER_SYSTEM,
            prompts.SEMANTIC_FILTER_USER_TEMPLATE.format(
                criteria_numbered=numbered
            ),
        )
        try:
            keep_idxs = json.loads(raw)
            return [criteria[i] for i in keep_idxs if 0 <= i < len(criteria)]
        except (json.JSONDecodeError, IndexError, TypeError):
            return criteria

    def filter(self, criteria: List[Criterion]) -> List[Criterion]:
        after_cluster = self._cluster_dedup(criteria)
        after_llm = self._llm_semantic_filter(after_cluster)
        return after_llm


# ── Top-level pipeline ─────────────────────────────────────────────────────────

class SupervisorySignalPipeline:
    """
    Full §3.1 pipeline: extract → ground → standardize → filter.

    Returns (fingerprint, guide) where fingerprint is the final criterion list.
    """

    def __init__(self, paragraphs: List[str]):
        self.extractor = GuideExtractor()
        self.grounder = SourceGrounder(paragraphs)
        self.standardizer = CriteriaStandardizer()
        self.filter_ = CriteriaFilter()
        self.paragraphs = paragraphs

    def run(
        self,
        title: str,
        intro_text: str,
        experiment_text: str,
    ) -> Tuple[List[Criterion], PaperGuide]:
        guide = self.extractor.extract_all(
            title, intro_text, experiment_text, self.paragraphs
        )
        all_sentences = guide.paragraphs
        criteria_raw = self.standardizer.standardize(all_sentences)

        # add source sentences via grounding
        for crit in criteria_raw:
            crit.source_sentences = self.grounder.ground(str(crit))

        fingerprint = self.filter_.filter(criteria_raw)
        return fingerprint, guide


# ── Helpers ────────────────────────────────────────────────────────────────────

def _split_sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _index_paragraph(paragraph: str) -> str:
    sents = _split_sentences(paragraph)
    return " ".join(f"[{i+1}]: {s}" for i, s in enumerate(sents))


def _parse_criteria(raw: str) -> List[Criterion]:
    pattern = re.compile(
        r"<fact>(.*?)</fact>\s*<scope>(.*?)</scope>", re.DOTALL
    )
    results = []
    for m in pattern.finditer(raw):
        fact = m.group(1).strip()
        scope = m.group(2).strip()
        if fact and scope:
            results.append(Criterion(fact=fact, scope=scope))
    return results
