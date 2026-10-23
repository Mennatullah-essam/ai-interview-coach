"""Answer evaluation: six separate, rubric-based dimensions (Milestone 4, feature 4).

Dimensions (each 0..100, or None when it does not apply):
  relevance         Does the answer address this question?          (similarity: supporting evidence)
  coverage          Which of the question's key concepts are covered? (rubric key points + synonyms)
  correctness       Technical accuracy against the rubric: concept coverage minus
                    known misconceptions stated in the answer. Technical questions only.
  structure         Is it organised? STAR cues (behavioral) or approach/reasoning/
                    example/trade-off cues (technical).
  specificity       Evidence: examples, numbers, named tools, reasoning.
  communication     Clear and developed enough: length, sentence length, repetition.

The overall score is a weighted mean over the dimensions that apply; weights
differ for technical and behavioral questions (config.json), so communication
and structure never dominate a technical assessment and vice versa.

Guards so similarity is never mistaken for correctness:
* similar wording without any expected concept caps relevance and correctness;
* a list of keywords without explanation is detected and capped;
* correctness never rises above what the rubric concepts support.
These are automated estimates for practice, not validated measurements.
"""

import json
import re
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.models.enums import QuestionType
from app.scoring import templates
from app.scoring.concepts import ConceptReport, analyse_concepts, find_misconceptions
from app.scoring.similarity import SimilarityEngine
from app.scoring.text_utils import chunks, content_stems, sentences, words
from app.services.cv_parsing import find_skills, load_skills

CONFIG_PATH = Path(__file__).with_name("config.json")
SYNONYMS_PATH = Path(__file__).with_name("concept_synonyms.json")

# Behavioral answers: STAR-style groups (situation, action, result, ordered flow).
_BEHAVIORAL_CUES = {
    "context": r"\b(problem|situation|challenge|goal|task|context|needed|because|when|issue|requirement|asked|project)\b",
    "action": r"\b(i|we) (built|implemented|designed|decided|used|created|led|wrote|analy[sz]ed|added|chose|"
              r"compared|tested|measured|organi[sz]ed|proposed|refactored|deployed|trained|fixed|asked|started|"
              r"spoke|talked|offered|suggested|planned|collected|told)\b|\b(approach|solution|steps?)\b",
    "result": r"\b(result|outcome|improv\w*|reduc\w*|increas\w*|sav\w*|achiev\w*|learn\w*|impact|delivered|"
              r"succeeded|so that|which (led|meant))\b|\d+(\.\d+)?\s?(%|percent|x\b|times)",
    "flow": r"\b(first|firstly|then|next|after that|afterwards|finally|as a result|in the end|second|third|since then)\b",
}
# Technical answers: explanation-style groups (approach, reasoning, example, trade-off/conclusion).
_TECHNICAL_CUES = {
    "approach": r"\b(first|then|next|start|step|use|using|apply|choose|check|measure|define|split|add|compare|i would|we would|i use)\b",
    "reasoning": r"\b(because|so that|which means|this means|since|to avoid|in order to|why|the reason|therefore|so)\b",
    "example": r"\b(for example|for instance|e\.g\.|such as|like|in my|i once|we used|in a project|in one project)\b",
    "tradeoff": r"\b(trade-?offs?|however|but|cost|downside|limitation|depends|instead|overall|in summary|finally|risk)\b",
}
_CUE_GROUPS = {QuestionType.BEHAVIORAL: _BEHAVIORAL_CUES, QuestionType.TECHNICAL: _TECHNICAL_CUES}
_EXAMPLE_RE = re.compile(r"\b(for example|for instance|e\.g\.|in my (last |previous )?(project|internship|job|role|team)|"
                         r"i (built|implemented|led|used|designed|wrote|trained|deployed)|we (built|used|implemented))\b", re.I)
_REASONING_RE = re.compile(r"\b(because|so that|which means|this means|since|in order to|the reason|therefore)\b", re.I)
_COMMON_VERBS = re.compile(
    r"\b(is|are|was|were|be|been|use|used|using|would|will|can|could|should|do|did|does|have|has|had|make|"
    r"made|build|built|check|checked|compare|choose|chose|need|needs|helps?|keeps?|means|gives?|takes?|"
    r"improves?|reduces?|increases?|work|works|worked|apply|applies|add|added|run|runs|ran|measure|train|trained)\b",
    re.I,
)

DIMENSION_LABELS = {
    "relevance": "Relevance",
    "coverage": "Key concepts",
    "correctness": "Technical accuracy",
    "structure": "Structure",
    "specificity": "Evidence & examples",
    "communication": "Communication",
}


@lru_cache
def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


@lru_cache
def _synonym_patterns() -> tuple[tuple[str, re.Pattern], ...]:
    raw = json.loads(SYNONYMS_PATH.read_text(encoding="utf-8"))
    data: dict[str, list[str]] = {}
    for section in ("synonyms", "rubric_cues"):
        for concept, alternatives in raw.get(section, {}).items():
            data.setdefault(concept, []).extend(alternatives)
    result = []
    for concept, alternatives in data.items():
        alternation = "|".join(re.escape(a) for a in sorted(alternatives, key=len, reverse=True))
        result.append((concept, re.compile(rf"(?<![a-z0-9])({alternation})(?![a-z0-9])", re.I)))
    return tuple(result)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _to_score(x: float) -> int:
    return int(round(_clamp01(x) * 100))


def _band(value: float, low: float, high: float) -> float:
    """1 inside [low, high], falling linearly to 0 at half / double the band."""
    if low <= value <= high:
        return 1.0
    if value < low:
        return _clamp01((value - low / 2) / (low / 2)) if low else 0.0
    return _clamp01(1 - (value - high) / high)


_MEASURED_RE = re.compile(r"\d\s?%|\bfrom\s+\d[\d.,]*\s*\w*\s+to\s+\d|\b\d+(?:\.\d+)?\s?x\s+(?:faster|fewer|smaller|cheaper)", re.I)


def expanded_stems(text: str) -> set[str]:
    """Content stems of the text, plus the concept words its synonyms stand for."""
    stems = set(content_stems(text))
    for concept, pattern in _synonym_patterns():
        if pattern.search(text):
            stems.update(content_stems(concept))
    if _MEASURED_RE.search(text):  # "30%", "from 0.71 to 0.89", "2x faster"
        stems.update(content_stems("measurable"))
    return stems


@dataclass
class Signals:
    sim_ref: float
    sim_question: float
    keypoint_coverage: float
    covered_key_points: list[str]
    missing_key_points: list[str]
    structure_cues: float
    clarity_cues: float
    word_count: int
    specificity: float
    off_topic: bool
    keyword_list: bool
    misconceptions_found: list[dict] = field(default_factory=list)
    concepts: ConceptReport | None = None
    unsupported_claims: list[str] = field(default_factory=list)

    @property
    def evidence_level(self) -> str:
        """sufficient | limited | insufficient: how much the answer gives to judge it on."""
        if self.word_count < 12 or self.off_topic:
            return "insufficient"
        mentioned_only = self.concepts is not None and self.concepts.items and not self.covered_key_points \
            and bool(self.concepts.with_status("mentioned"))
        if self.word_count < 35 or self.keyword_list or mentioned_only:
            return "limited"
        return "sufficient"


@dataclass
class Dimension:
    key: str
    label: str
    score: int | None
    weight: float
    explanation: str

    def as_dict(self) -> dict:
        return {"key": self.key, "label": self.label, "score": self.score, "weight": self.weight,
                "explanation": self.explanation}


@dataclass
class EvaluationResult:
    overall_score: int
    relevance: int
    clarity: int
    technical_depth: int
    structure: int
    strengths: list[str]
    weaknesses: list[str]
    improvement_tip: str
    semantic_similarity: float
    scoring_version: str
    model_info: dict = field(default_factory=dict)
    latency_ms: int = 0
    dimensions: list[Dimension] = field(default_factory=list)
    missing_concepts: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    explanation: str = ""
    # Milestone 5: evidence behind the scores.
    concept_evidence: list[dict] = field(default_factory=list)
    demonstrated_concepts: list[str] = field(default_factory=list)
    unsupported_claims: list[str] = field(default_factory=list)
    incorrect_claims: list[dict] = field(default_factory=list)
    evidence_level: str = "sufficient"
    feedback_source: str = "rules"

    def dimension(self, key: str) -> Dimension | None:
        return next((d for d in self.dimensions if d.key == key), None)


# Generic verbs in rubric wording that carry no concept of their own.
_RUBRIC_FILLER = frozenset(content_stems("taking using made getting something went how your"))


def _is_keyword_list(answer: str, word_count: int) -> bool:
    """A comma-separated list of terms, without sentences that explain anything."""
    if word_count < 6:
        return False
    commas = answer.count(",") + answer.count(";") + answer.count("\n")
    verbs = len(_COMMON_VERBS.findall(answer))
    return (commas / word_count > 0.25 and verbs < 3) or verbs == 0


def compute_signals(
    engine: SimilarityEngine,
    *,
    question: str,
    question_type: QuestionType,
    answer: str,
    reference: str,
    key_points: list[str],
    extra_terms: list[str],
    misconceptions: list[dict] | None = None,
) -> Signals:
    cfg = load_config()
    answer_chunks = chunks(answer) or [answer]
    sim_ref = max(engine.similarity(answer, reference), engine.max_similarity(answer_chunks, reference))
    sim_question = max(engine.similarity(answer, question), engine.max_similarity(answer_chunks, question))
    guard = cfg["off_topic"][engine.name]
    off_topic = sim_question < guard["question_below"] and sim_ref < guard["reference_below"]

    answer_words = words(answer)
    keyword_list = _is_keyword_list(answer, len(answer_words))
    report = analyse_concepts(answer, key_points, expand=expanded_stems, engine=engine,
                              sbert_threshold=cfg["keypoint"]["sbert_similarity"],
                              word_share=cfg["keypoint"]["lexical_word_share"], filler=_RUBRIC_FILLER,
                              keyword_list=keyword_list)
    coverage = report.coverage
    covered = report.with_status("demonstrated", "partial")
    missing = report.with_status("missing", "mentioned")

    lowered = answer.lower()
    cue_groups = _CUE_GROUPS[question_type]
    structure_cues = sum(1 for rx in cue_groups.values() if re.search(rx, lowered)) / len(cue_groups)

    sentence_list = sentences(answer) or [answer]
    # Length is measured on distinct sentences, so padding an answer by
    # repeating itself cannot move it into the "good length" band.
    distinct = list(dict.fromkeys(" ".join(words(s)) for s in sentence_list))
    word_count = sum(len(s.split()) for s in distinct)
    low, high = cfg["clarity"]["words_band"][question_type.value]
    length_part = _band(word_count, low, high)
    avg_sentence = len(answer_words) / max(1, len(sentence_list))
    s_low, s_high = cfg["clarity"]["sentence_words_band"]
    sentence_part = _band(avg_sentence, s_low, s_high)
    unique_ratio = len(set(answer_words)) / max(1, len(answer_words))
    repetition_part = _clamp01(unique_ratio / cfg["clarity"]["min_unique_ratio"])
    clarity_cues = 0.5 * length_part + 0.3 * sentence_part + 0.2 * repetition_part

    numbers = len(re.findall(r"\b\d+(?:[.,]\d+)?\s?%?", answer))
    vocabulary = tuple(dict.fromkeys([*load_skills(get_settings().skills_list_path), *extra_terms]))
    named = len(find_skills(answer, vocabulary))
    examples = len(_EXAMPLE_RE.findall(answer))
    reasoning = len(_REASONING_RE.findall(answer))
    specificity = (0.3 * _clamp01(numbers / 2) + 0.3 * _clamp01(named / 2)
                   + 0.25 * _clamp01(examples) + 0.15 * _clamp01(reasoning))

    found = find_misconceptions(answer, misconceptions)
    unsupported = report.unsupported_claims
    if unsupported:  # sweeping claims without reasons are not evidence
        specificity *= 1 - cfg["guards"]["unsupported_specificity_factor"] * min(len(unsupported), 2)

    if keyword_list:
        structure_cues = min(structure_cues, 0.25)
        clarity_cues = min(clarity_cues, 0.35)

    return Signals(
        sim_ref=sim_ref, sim_question=sim_question, keypoint_coverage=coverage, covered_key_points=covered,
        missing_key_points=missing, structure_cues=structure_cues, clarity_cues=clarity_cues,
        word_count=word_count, specificity=specificity, off_topic=off_topic, keyword_list=keyword_list,
        misconceptions_found=found, concepts=report, unsupported_claims=unsupported,
    )


def _dimensions(signals: Signals, engine, question_type: QuestionType, key_points: list[str], cfg: dict,
                category: str | None = None) -> list[Dimension]:
    weights = cfg["category_weights"].get(category or "", cfg["dimension_weights"][question_type.value])
    low, high = cfg["similarity_map"][engine.name]["low"], cfg["similarity_map"][engine.name]["high"]

    relevance = _clamp01((signals.sim_ref - low) / (high - low))
    relevance_note = f"Compared with the question and an example answer ({engine.name} similarity)."
    if signals.off_topic:
        relevance = min(relevance, cfg["off_topic"]["relevance_cap"] / 100)
        relevance_note = "The answer does not seem to address this question."
    elif key_points and signals.keypoint_coverage == 0 and relevance > cfg["guards"]["no_concept_relevance_cap"]:
        relevance = cfg["guards"]["no_concept_relevance_cap"]
        relevance_note = "Similar wording, but none of the expected concepts, so relevance is capped."

    total = len(key_points)
    coverage_note = "No rubric concepts are defined for this question."
    if total and signals.concepts is not None:
        counts = {s: len(signals.concepts.with_status(s)) for s in ("demonstrated", "partial", "mentioned")}
        coverage_note = (f"{counts['demonstrated']} of {total} key concepts explained"
                         + (f", {counts['partial']} partly" if counts["partial"] else "")
                         + (f", {counts['mentioned']} only named without explanation" if counts["mentioned"] else "")
                         + ".")

    correctness: float | None = None
    correctness_note = "Not assessed for behavioral questions."
    if question_type is QuestionType.TECHNICAL and key_points:
        # Nothing assessable without any expected concept; otherwise credit grows with coverage.
        correctness = 0.0 if signals.keypoint_coverage == 0 else 0.35 + 0.65 * signals.keypoint_coverage
        notes = [f"Based on {len(signals.covered_key_points)} of {total} rubric concepts"]
        if signals.misconceptions_found:
            correctness -= cfg["guards"]["misconception_penalty"] * len(signals.misconceptions_found)
            notes.append(f"{len(signals.misconceptions_found)} incorrect claim(s) detected")
        if signals.unsupported_claims:
            correctness -= min(cfg["guards"]["unsupported_max_penalty"],
                               cfg["guards"]["unsupported_penalty"] * len(signals.unsupported_claims))
            notes.append(f"{len(signals.unsupported_claims)} sweeping claim(s) without support")
        if signals.keyword_list:
            correctness = min(correctness, cfg["guards"]["keyword_list_cap"])
            notes.append("concepts are listed but not explained")
        if signals.off_topic:
            correctness = min(correctness, cfg["off_topic"]["relevance_cap"] / 100)
        correctness = max(0.0, correctness)
        correctness_note = "; ".join(notes) + ". Automated checks cannot verify every claim."
    elif question_type is QuestionType.TECHNICAL:
        correctness_note = "No rubric is available for this question, so accuracy is not scored."

    structure_note = ("Looks for situation, action, result and a clear order (STAR)."
                      if question_type is QuestionType.BEHAVIORAL
                      else "Looks for an approach, reasoning, an example and trade-offs.")
    if signals.keyword_list:
        structure_note = "A list of terms without sentences has little structure."
    return [
        Dimension("relevance", DIMENSION_LABELS["relevance"], _to_score(relevance), weights["relevance"], relevance_note),
        Dimension("coverage", DIMENSION_LABELS["coverage"], _to_score(signals.keypoint_coverage) if total else None,
                  weights["coverage"], coverage_note),
        Dimension("correctness", DIMENSION_LABELS["correctness"],
                  None if correctness is None else _to_score(correctness), weights.get("correctness", 0.0), correctness_note),
        Dimension("structure", DIMENSION_LABELS["structure"], _to_score(signals.structure_cues), weights["structure"], structure_note),
        Dimension("specificity", DIMENSION_LABELS["specificity"], _to_score(signals.specificity), weights["specificity"],
                  "Counts concrete examples, numbers, named tools and reasoning."),
        Dimension("communication", DIMENSION_LABELS["communication"], _to_score(signals.clarity_cues),
                  weights["communication"], "Checks length, sentence length and repetition."),
    ]


def evaluate_answer(
    engine: SimilarityEngine,
    *,
    question: str,
    question_type: QuestionType,
    answer: str,
    reference: str,
    key_points: list[str],
    extra_terms: list[str] | None = None,
    misconceptions: list[dict] | None = None,
    category: str | None = None,
) -> EvaluationResult:
    started = time.perf_counter()
    cfg = load_config()
    signals = compute_signals(
        engine, question=question, question_type=question_type, answer=answer, reference=reference,
        key_points=key_points, extra_terms=extra_terms or [], misconceptions=misconceptions,
    )
    dims = _dimensions(signals, engine, question_type, key_points, cfg, category)
    applicable = [d for d in dims if d.score is not None and d.weight > 0]
    weight_sum = sum(d.weight for d in applicable)
    overall = int(sum(d.score * d.weight for d in applicable) / weight_sum + 0.5) if weight_sum else 0

    by_key = {d.key: d.score for d in dims}
    knowledge = [s for s in (by_key["coverage"], by_key["correctness"]) if s is not None]
    technical_depth = int(sum(knowledge) / len(knowledge) + 0.5) if knowledge else by_key["specificity"]

    feedback = templates.answer_feedback(dimensions=dims, signals=signals, question_type=question_type,
                                         thresholds=cfg["feedback"])
    explanation = templates.explanation(dimensions=dims, signals=signals, engine_name=engine.name,
                                        question_type=question_type, overall=overall)
    return EvaluationResult(
        overall_score=overall,
        relevance=by_key["relevance"],
        clarity=by_key["communication"],
        technical_depth=technical_depth,
        structure=by_key["structure"],
        strengths=feedback.strengths,
        weaknesses=feedback.weaknesses,
        improvement_tip=feedback.tip,
        semantic_similarity=round(_clamp01(signals.sim_ref), 4),
        scoring_version=f"{engine.name}-{cfg['version']}",
        model_info={
            "similarity_backend": engine.name,
            "embedding_model": engine.model_id,
            "config_version": cfg["version"],
            "signals": {
                "sim_ref": round(signals.sim_ref, 4),
                "sim_question": round(signals.sim_question, 4),
                "keypoint_coverage": round(signals.keypoint_coverage, 4),
                "structure_cues": round(signals.structure_cues, 4),
                "clarity_cues": round(signals.clarity_cues, 4),
                "specificity": round(signals.specificity, 4),
                "off_topic": signals.off_topic,
                "keyword_list": signals.keyword_list,
                "misconceptions": [m.get("explanation", "") for m in signals.misconceptions_found],
                "unsupported_claims": len(signals.unsupported_claims),
                "evidence_level": signals.evidence_level,
            },
        },
        latency_ms=int((time.perf_counter() - started) * 1000),
        dimensions=dims,
        missing_concepts=list(signals.missing_key_points),
        suggestions=feedback.suggestions,
        explanation=explanation,
        concept_evidence=[i.as_dict() for i in signals.concepts.items] if signals.concepts else [],
        demonstrated_concepts=signals.concepts.with_status("demonstrated", "partial") if signals.concepts else [],
        unsupported_claims=list(signals.unsupported_claims),
        incorrect_claims=[{"explanation": m["explanation"], "evidence": m.get("evidence")} for m in signals.misconceptions_found],
        evidence_level=signals.evidence_level,
    )


def recompute_totals(result: EvaluationResult, question_type: QuestionType) -> None:
    """Recalculate overall and the compatibility categories after dimensions were adjusted."""
    applicable = [d for d in result.dimensions if d.score is not None and d.weight > 0]
    weight_sum = sum(d.weight for d in applicable)
    result.overall_score = int(sum(d.score * d.weight for d in applicable) / weight_sum + 0.5) if weight_sum else 0
    by_key = {d.key: d.score for d in result.dimensions}
    knowledge = [v for v in (by_key["coverage"], by_key["correctness"]) if v is not None]
    result.technical_depth = int(sum(knowledge) / len(knowledge) + 0.5) if knowledge else by_key["specificity"]
