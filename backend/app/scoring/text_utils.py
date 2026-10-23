"""Small text helpers shared by the lexical similarity backend and the criteria."""

import math
import re
from collections import Counter

STOPWORDS = frozenset(
    """a an and are as at be been being but by can could did do does doing for from had has have
    having he her here hers him his how i if in into is it its itself just me more most my no nor
    not of off on once only or other our ours out over own same she should so some such than that
    the their them then there these they this those through to too under until up very was we were
    what when where which while who whom why will with would you your yours also about after again
    against all am any because before below between both down during each few further let lets
    i'm it's i've we're they're don't""".split()
)

_WORD = re.compile(r"[a-z0-9][a-z0-9+#.\-]*[a-z0-9+#]|[a-z0-9]")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def words(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def stem(word: str) -> str:
    """Very small suffix stripper; enough to match 'tests'/'tested'/'testing'."""
    for suffix in ("ations", "ation", "ingly", "ings", "ing", "edly", "ies", "ied", "ed", "es", "ly", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            base = word[: -len(suffix)]
            return base + "y" if suffix in ("ies", "ied") else base
    return word


def content_stems(text: str) -> list[str]:
    return [stem(w) for w in words(text) if w not in STOPWORDS and len(w) > 1]


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text.strip()) if s.strip()]


def chunks(text: str, size: int = 3, overlap: int = 1) -> list[str]:
    """Groups of up to `size` sentences overlapping by `overlap` (spec 16.4)."""
    parts = sentences(text)
    if len(parts) <= size:
        return [" ".join(parts)] if parts else []
    step = max(1, size - overlap)
    result = []
    for start in range(0, len(parts), step):
        result.append(" ".join(parts[start : start + size]))
        if start + size >= len(parts):
            break
    return result


def cosine_counts(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a[k] * b[k] for k in a.keys() & b.keys())
    norm = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
    return dot / norm if norm else 0.0
