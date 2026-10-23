"""Similarity engines behind one interface (API spec 16.6).

* LexicalSimilarity: term-overlap cosine on stemmed content words. Standard
  library only; runs on any machine. Lower quality than a model.
* SbertSimilarity: a local Sentence-Transformers model
  (default sentence-transformers/all-MiniLM-L6-v2). Needs requirements-ml.txt
  and downloads the model once.

The backend is chosen explicitly with SIMILARITY_BACKEND. If "sbert" is chosen
and the model cannot load, evaluation reports AI_SERVICE_UNAVAILABLE; it NEVER
silently switches to the lexical backend.
"""

import logging
import threading
from collections import Counter
from typing import Protocol

from app.core.config import get_settings
from app.scoring.text_utils import content_stems

logger = logging.getLogger(__name__)


class SimilarityEngine(Protocol):
    name: str
    model_id: str | None

    def similarity(self, a: str, b: str) -> float: ...

    def max_similarity(self, pieces: list[str], target: str) -> float: ...


class LexicalSimilarity:
    name = "lexical"
    model_id = None

    def similarity(self, a: str, b: str) -> float:
        from app.scoring.text_utils import cosine_counts

        return cosine_counts(Counter(content_stems(a)), Counter(content_stems(b)))

    def max_similarity(self, pieces: list[str], target: str) -> float:
        return max((self.similarity(p, target) for p in pieces), default=0.0)


class SbertSimilarity:
    name = "sbert"

    def __init__(self, model_id: str, model_path: str | None = None, encoder=None):
        self.model_id = model_id
        self._model_path = model_path
        self._model = encoder  # tests may inject a fake encoder
        self._cache: dict[str, object] = {}
        self._lock = threading.Lock()

    def load(self) -> None:
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer  # optional dependency

        self._model = SentenceTransformer(self._model_path or self.model_id, device="cpu")

    def _embed(self, texts: list[str]):
        missing = [t for t in texts if t not in self._cache]
        if missing:
            vectors = self._model.encode(missing, normalize_embeddings=True)
            with self._lock:
                for text, vector in zip(missing, vectors):
                    if len(self._cache) > 5000:
                        self._cache.clear()
                    self._cache[text] = vector
        return [self._cache[t] for t in texts]

    def embed(self, texts: list[str]) -> list:
        """Normalised vectors for the texts (cached in memory)."""
        return self._embed(texts)

    def similarity(self, a: str, b: str) -> float:
        va, vb = self._embed([a, b])
        return float(sum(x * y for x, y in zip(va, vb)))

    def max_similarity(self, pieces: list[str], target: str) -> float:
        if not pieces:
            return 0.0
        vectors = self._embed([*pieces, target])
        target_vector = vectors[-1]
        return max(float(sum(x * y for x, y in zip(v, target_vector))) for v in vectors[:-1])


class EngineUnavailable(Exception):
    pass


_engine: SimilarityEngine | None = None
_engine_error: str | None = None
_engine_lock = threading.Lock()


def load_engine() -> None:
    """Called once at start-up. Never raises; failures are reported by get_engine()."""
    global _engine, _engine_error
    settings = get_settings()
    with _engine_lock:
        if settings.similarity_backend == "lexical":
            _engine, _engine_error = LexicalSimilarity(), None
            return
        try:
            engine = SbertSimilarity(settings.embedding_model, settings.embedding_model_path)
            engine.load()
            engine.similarity("warm up", "warm up")
            _engine, _engine_error = engine, None
            logger.info("Similarity model loaded: %s", settings.embedding_model)
        except Exception as exc:  # missing package, download failure, bad path, ...
            _engine, _engine_error = None, type(exc).__name__
            logger.error("Similarity model could not be loaded (%s); evaluation is unavailable.", type(exc).__name__)


def get_engine() -> SimilarityEngine:
    if _engine is None and _engine_error is None:
        load_engine()
    if _engine is None:
        raise EngineUnavailable(_engine_error or "not loaded")
    return _engine


def engine_status() -> str:
    """"ok" (sbert loaded), "lexical", or "unavailable" — for the health endpoint."""
    try:
        engine = get_engine()
    except EngineUnavailable:
        return "unavailable"
    return "lexical" if engine.name == "lexical" else "ok"


def set_engine_for_tests(engine: SimilarityEngine | None) -> None:
    global _engine, _engine_error
    _engine, _engine_error = engine, None
