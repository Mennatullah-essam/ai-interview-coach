"""Evidence-based concept matching for answer evaluation (Milestone 5).

For every rubric key point the answer gets one status, with the sentence that
supports it:

  demonstrated  the concept is explained in a real sentence (most of the key
                point's words, a synonym, or a rubric alias; with the embedding
                model, a semantically close sentence)
  partial       only part of the concept appears in an explanation
  mentioned     the concept is named, but only in a bare list or fragment, so
                naming it is not counted as understanding it
  missing       no evidence

Coverage credit: demonstrated 1, partial 0.5, mentioned 0.25, missing 0.

Separately, the answer is checked for
* unsupported claims: sweeping statements ("always", "never needs", "the only",
  "trust me"...) in a sentence that gives no reason or example. Statements of
  one's own practice ("I never commit secrets") are not counted;
* incorrect claims: the question's known misconception patterns.
An incorrect claim is different from a missing concept: the first lowers
technical accuracy, the second only means there is no evidence yet.
"""

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache

from app.intelligence.knowledge import DATA_DIR
from app.scoring.text_utils import content_stems, sentences, words

CREDIT = {"demonstrated": 1.0, "partial": 0.5, "mentioned": 0.25, "missing": 0.0}

# Words too generic to show a concept on their own (a match on only these is not partial evidence).
_GENERIC = frozenset(content_stems(
    "data model models use value values question answer system way thing things time result results "
    "make good better work set test tests code number numbers problem approach"))
_VERB = re.compile(
    r"\b(is|are|was|were|be|use|uses|used|using|would|will|can|could|should|do|does|did|have|has|had|make|makes|"
    r"keep|keeps|check|checks|compare|compares|choose|need|needs|help|helps|means|mean|give|gives|take|takes|"
    r"improve|improves|reduce|reduces|increase|increases|work|works|apply|add|adds|run|runs|measure|measures|"
    r"train|trains|learn|learns|avoid|avoids|prevent|prevents|split|splits|stop|stops|look|looks|catch|tune|move|"
    r"put|store|stores|send|sends|return|returns|let|lets|happen|happens|get|gets|set|sets|show|shows|tell|tells|"
    r"pick|picks|drop|drops|fill|fills|log|logs|monitor|monitors|cause|causes|depend|depends|spot|detect|detects)\b",
    re.I,
)
_REASON = re.compile(r"\b(because|since|so that|which means|this means|for example|for instance|e\.g\.|due to|"
                     r"as a result|in my|we measured|i measured|the reason|that is why|otherwise)\b", re.I)
_SWEEPING = re.compile(
    r"\b(always|never|guarantee[sd]?|100 ?%|perfect(ly)?|no cost|the best|the only|nobody|"
    r"does ?n[o']t matter|do ?n[o']t need|not something .{0,20}need)\b", re.I)
# Appeals to authority or certainty instead of reasons: flagged even next to correct concepts.
_HOLLOW = re.compile(r"\b(trust me|everyone (in \w+ )?knows|every serious|obvious(ly)?|it is a myth|is a myth|"
                     r"basically magic|just how it works|everyone uses|everybody knows)\b", re.I)
_OWN_PRACTICE = re.compile(r"\b(i|we|you should|i'd|we'd)\s+(always|never|usually|completely)\b", re.I)


@dataclass
class ConceptEvidence:
    concept: str
    status: str  # demonstrated | partial | mentioned | missing
    evidence: str | None = None

    def as_dict(self) -> dict:
        return {"concept": self.concept, "status": self.status, "evidence": self.evidence}


@dataclass
class ConceptReport:
    items: list[ConceptEvidence] = field(default_factory=list)
    unsupported_claims: list[str] = field(default_factory=list)

    @property
    def coverage(self) -> float:
        if not self.items:
            return 1.0
        return sum(CREDIT[i.status] for i in self.items) / len(self.items)

    def with_status(self, *statuses: str) -> list[str]:
        return [i.concept for i in self.items if i.status in statuses]


@lru_cache
def _aliases() -> dict[str, tuple[re.Pattern, ...]]:
    data = json.loads((DATA_DIR / "rubric_aliases.json").read_text(encoding="utf-8"))["aliases"]
    result = {}
    for point, phrases in data.items():
        result[point.lower()] = tuple(
            re.compile(rf"(?<![a-z0-9]){re.escape(p.lower())}(?![a-z0-9])", re.I) for p in phrases if p.strip()
        )
    return result


def _explanatory(sentence: str) -> bool:
    """A real sentence: enough words and a verb, not a comma-separated list of terms."""
    tokens = words(sentence)
    if len(tokens) < 6 or not _VERB.search(sentence):
        return False
    commas = sentence.count(",") + sentence.count(";")
    return commas / max(1, len(tokens)) <= 0.3


def _trim(text: str, limit: int = 180) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def analyse_concepts(answer: str, key_points: list[str], *, expand, engine=None, sbert_threshold: float = 0.55,
                     word_share: float = 0.6, filler: frozenset = frozenset(), keyword_list: bool = False) -> ConceptReport:
    """`expand(text) -> set[str]` returns content stems plus synonym concepts (scorer.expanded_stems).

    Evidence is looked for sentence by sentence; a concept spread over a few
    sentences of a real explanation also counts, a bare keyword list never does.
    """
    parts = sentences(answer) or ([answer] if answer.strip() else [])
    info = [(s, _explanatory(s) and not keyword_list, expand(s)) for s in parts]
    whole = expand(answer)
    any_explanatory = any(ok for _, ok, _ in info)
    aliases = _aliases()
    report = ConceptReport()
    for point in key_points:
        point_stems = set(content_stems(point))
        if point_stems - filler:  # "taking initiative" is about the initiative, not the verb
            point_stems -= filler
        best_status, best_sentence = "missing", None
        for sentence, explanatory, stems in info:
            share = len(point_stems & stems) / len(point_stems) if point_stems else 0.0
            alias_hit = any(p.search(sentence) for p in aliases.get(point.lower(), ()))
            if share >= word_share or alias_hit:
                status = "demonstrated" if explanatory else "mentioned"
            elif share >= 0.5 and explanatory and (point_stems & stems) - _GENERIC:
                status = "partial"
            else:
                continue
            if CREDIT[status] > CREDIT[best_status]:
                best_status, best_sentence = status, sentence
            if best_status == "demonstrated":
                break
        if best_status in ("missing", "partial", "mentioned") and point_stems:
            share_all = len(point_stems & whole) / len(point_stems)
            if share_all >= word_share:
                if any_explanatory and best_status != "mentioned":
                    closest = max(info, key=lambda item: len(point_stems & item[2]))
                    best_status, best_sentence = "demonstrated", closest[0]
                elif best_status == "missing":
                    best_status, best_sentence = "mentioned", parts[0] if parts else None
        if best_status in ("missing", "partial") and engine is not None and engine.name == "sbert":
            explanatory_parts = [s for s, ok, _ in info if ok]
            if explanatory_parts:
                scores = [engine.similarity(s, point) for s in explanatory_parts]
                top = max(scores)
                if top >= sbert_threshold:
                    best_status, best_sentence = "demonstrated", explanatory_parts[scores.index(top)]
                elif top >= sbert_threshold - 0.1 and best_status == "missing":
                    best_status, best_sentence = "partial", explanatory_parts[scores.index(top)]
        report.items.append(ConceptEvidence(point, best_status, _trim(best_sentence) if best_sentence else None))

    evidence_sentences = {_trim(i.evidence) for i in report.items if i.status in ("demonstrated", "partial") and i.evidence}
    for sentence in parts:
        if _HOLLOW.search(sentence):
            report.unsupported_claims.append(_trim(sentence, 160))
            continue
        # A sweeping statement that also explains a rubric concept is usually a correct rule ("microtasks
        # always run before the next task"); only flag sweeping claims that carry no reason and no concept.
        if _SWEEPING.search(sentence) and not _REASON.search(sentence) and _trim(sentence) not in evidence_sentences:
            stripped = _OWN_PRACTICE.sub("", sentence)
            if _SWEEPING.search(stripped):
                report.unsupported_claims.append(_trim(sentence, 160))
    report.unsupported_claims = report.unsupported_claims[:3]
    return report


def find_misconceptions(answer: str, misconceptions: list[dict] | None) -> list[dict]:
    """Known incorrect claims (question-specific regex patterns from the bank), with the matching sentence."""
    found = []
    parts = sentences(answer) or [answer]
    for item in misconceptions or []:
        try:
            pattern = re.compile(item["pattern"], re.IGNORECASE)
        except (re.error, KeyError, TypeError):
            continue
        sentence = next((s for s in parts if pattern.search(s)), None)
        if sentence is None and pattern.search(answer):
            sentence = answer
        if sentence is not None:
            found.append({"pattern": item["pattern"], "explanation": item.get("explanation", ""),
                          "evidence": _trim(sentence, 160)})
    return found
