"""Semantic retrieval over the curated question bank (Milestone 5).

Each bank question becomes one retrieval document: its text, its rubric key
points and the descriptions of the competencies it assesses. A query is the
target role, its required skills and their descriptions, and the job
description. Two engines can score document/query pairs:

* sbert   a local Sentence-Transformers model (optional). Document vectors are
          computed once per model and kept in memory and in an on-disk cache
          (storage/embedding_cache/<model>.json), so restarts don't re-encode
          the bank. Nothing is sent to an external API.
* lexical the deterministic fallback, used automatically for retrieval when no
          model is loaded. It expands both sides with the curated concept
          synonyms and skill aliases, so "k8s" and "Kubernetes" or
          "weight decay" and "regularization" still match.

Similarity is only one input to ranking (see question_selection): a similar
question can still be the wrong role, difficulty or interview type.
"""

import hashlib
import json
import logging
import math
import threading
from collections import Counter
from pathlib import Path

from app.intelligence.competencies import competency_model

logger = logging.getLogger(__name__)


def _concept_counter(text: str) -> Counter:
    """Stems of the text plus the canonical concepts its synonyms/aliases stand for."""
    from app.intelligence.knowledge import find_alias_skills
    from app.scoring.scorer import expanded_stems
    from app.scoring.text_utils import content_stems

    counts = Counter(content_stems(text))
    for stem in expanded_stems(text) - set(counts):
        counts[stem] += 1
    for skill in find_alias_skills(text):
        for stem in content_stems(skill):
            counts[stem] += 1
    return counts


def _cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a[k] * b[k] for k in a.keys() & b.keys())
    norm = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
    return dot / norm if norm else 0.0


def question_document(text: str, key_points: list[str] | None, skill_tags: list[str] | None) -> str:
    model = competency_model()
    descriptions = [model.description(s) for s in (skill_tags or [])]
    return " ".join(filter(None, [text, "; ".join(key_points or []), " ".join(skill_tags or []), " ".join(descriptions)]))


class SemanticIndex:
    """Scores question documents against a query. Deterministic for a given engine and model."""

    def __init__(self, engine=None, cache_dir: Path | None = None):
        self.engine = engine
        self.name = engine.name if engine is not None and engine.name == "sbert" else "lexical"
        self._lexical: dict[str, Counter] = {}
        self._vectors: dict[str, list[float]] = {}
        self._lock = threading.Lock()
        self._cache_file = None
        if self.name == "sbert" and cache_dir is not None:
            safe = "".join(c if c.isalnum() else "_" for c in (engine.model_id or "model"))
            self._cache_file = Path(cache_dir) / f"{safe}.json"
            self._load_cache()

    # --- vectors ------------------------------------------------------------------------------
    @staticmethod
    def _key(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]

    def _load_cache(self) -> None:
        try:
            if self._cache_file and self._cache_file.exists():
                self._vectors = json.loads(self._cache_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._vectors = {}

    def _save_cache(self) -> None:
        if not self._cache_file:
            return
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._cache_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._vectors), encoding="utf-8")
            tmp.replace(self._cache_file)
        except OSError:
            logger.warning("Could not write the embedding cache; vectors stay in memory only.")

    def vectors(self, texts: list[str]) -> list[list[float]]:
        keys = [self._key(t) for t in texts]
        missing = [(k, t) for k, t in zip(keys, texts, strict=True) if k not in self._vectors]
        if missing:
            encoded = self.engine.embed([t for _, t in missing])
            with self._lock:
                for (k, _), vector in zip(missing, encoded, strict=True):
                    self._vectors[k] = [round(float(x), 6) for x in vector]
            self._save_cache()
        return [self._vectors[k] for k in keys]

    def warm(self, documents: list[str]) -> None:
        if self.name == "sbert":
            self.vectors(documents)

    # --- scoring ------------------------------------------------------------------------------
    def _counter(self, text: str) -> Counter:
        found = self._lexical.get(text)
        if found is None:
            found = _concept_counter(text)
            if len(self._lexical) > 4000:
                self._lexical.clear()
            self._lexical[text] = found
        return found

    def similarity(self, a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        if self.name == "sbert":
            va, vb = self.vectors([a, b])
            return max(0.0, float(sum(x * y for x, y in zip(va, vb, strict=True))))
        return _cosine(self._counter(a), self._counter(b))


_indexes: dict[str, SemanticIndex] = {}
_index_lock = threading.Lock()


def get_index(engine=None) -> SemanticIndex:
    """One index per engine/model per process, so vectors are computed once."""
    from app.core.config import get_settings

    usable = engine is not None and engine.name == "sbert" and hasattr(engine, "embed")
    key = f"sbert:{engine.model_id}" if usable else "lexical"
    with _index_lock:
        if key not in _indexes:
            cache_dir = Path(get_settings().cv_storage_dir).parent / "embedding_cache" if usable else None
            _indexes[key] = SemanticIndex(engine if usable else None, cache_dir=cache_dir)
        return _indexes[key]


def reset_indexes_for_tests() -> None:
    with _index_lock:
        _indexes.clear()
