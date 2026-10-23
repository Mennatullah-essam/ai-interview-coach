"""Adaptive interview rules (Milestone 4, feature 3).

Milestone 5: follow-up decisions are now made by intelligence/agent.py (context-aware,
optional LLM, policy-validated). This module still provides the follow-up limits
(max_follow_ups) and the difficulty adjustment (target_difficulty). decide_follow_up
is the Milestone 4 rule set, kept as the documented baseline (used by its tests and
the benchmark script), not by the running app.

Only used when the candidate turns on "adaptive follow-ups" for an interview;
fixed interviews keep their exact question sequence.

After each evaluated answer the engine may add ONE follow-up right after it:
  clarify  the answer missed key concepts and scored low  -> ask about the missing concept
  example  the answer stayed general (little evidence)      -> ask for a concrete example
  deeper   the answer was strong                             -> probe trade-offs / reflection
Limits: no follow-up on a follow-up, one per question, and at most
max_follow_ups(question_count) per interview (2 / 3 / 4 for 5 / 10 / 15 questions).

It may also adjust the difficulty of the NEXT unanswered question once enough
evidence exists (average of at least two answers), at most twice per interview.

Every decision is a plain rule on the stored evaluation, so it is explainable,
repeatable and testable. No external AI provider is required.
"""

from dataclasses import dataclass, field

from app.models.enums import Difficulty, QuestionType

WEAK_BELOW = 50
STRONG_FROM = 80
GENERAL_EVIDENCE_BELOW = 40
GENERAL_OVERALL_BELOW = 70
ADJUST_MIN_ANSWERS = 2
ADJUST_HARDER_FROM = 80
ADJUST_EASIER_BELOW = 45
MAX_ADJUSTMENTS = 2
ADJUSTED_PREFIX = "Adjusted:"
_LIMITS = {5: 2, 10: 3, 15: 4}
_ORDER = [Difficulty.BEGINNER, Difficulty.INTERMEDIATE, Difficulty.ADVANCED]


def max_follow_ups(question_count: int) -> int:
    return _LIMITS.get(question_count, max(1, question_count // 4))


@dataclass
class FollowUpPlan:
    kind: str  # clarify | example | deeper
    text: str
    reference: str
    key_points: list[str]
    reason: str
    focus_skills: list[str] = field(default_factory=list)


def _score(dimensions: list[dict] | None, key: str) -> int | None:
    for item in dimensions or []:
        if item.get("key") == key:
            return item.get("score")
    return None


def decide_follow_up(
    *,
    question_text: str,
    question_type: QuestionType,
    category: str | None,
    parent_reference: str | None,
    focus_skills: list[str],
    overall: int,
    dimensions: list[dict] | None,
    missing_concepts: list[str],
    used: int,
    limit: int,
    has_follow_up: bool,
) -> FollowUpPlan | None:
    """Return the follow-up to ask, or None. Pure function of the stored evaluation."""
    if category == "follow_up" or has_follow_up or used >= limit:
        return None
    evidence = _score(dimensions, "specificity")
    reference = parent_reference or ""

    if overall < WEAK_BELOW and missing_concepts and question_type is QuestionType.TECHNICAL:
        concept = missing_concepts[0]
        return FollowUpPlan(
            kind="clarify",
            text=f"Let's go back to that question. You didn't mention {concept}. "
                 f"How does it apply here? Please explain it with a concrete example.",
            reference=reference,
            key_points=[*missing_concepts[:3], "a concrete example"],
            reason=f"Follow-up because your answer did not cover “{concept}”.",
            focus_skills=focus_skills,
        )
    if overall < WEAK_BELOW:
        return FollowUpPlan(
            kind="example",
            text="Can you walk me through one specific situation in more detail: what exactly did you do, "
                 "and what was the result?",
            reference=reference,
            key_points=["one specific situation", "your own actions", "a measurable result", "what you learned"],
            reason="Follow-up asking for a specific example because the first answer was incomplete.",
            focus_skills=focus_skills,
        )
    if evidence is not None and evidence < GENERAL_EVIDENCE_BELOW and overall < GENERAL_OVERALL_BELOW:
        return FollowUpPlan(
            kind="example",
            text="Can you give a concrete example of how you applied this, ideally with a measurable result?",
            reference=reference,
            key_points=["a concrete example", "the tools or methods used", "a measurable result"],
            reason="Follow-up asking for evidence because the answer stayed general.",
            focus_skills=focus_skills,
        )
    if overall >= STRONG_FROM:
        if question_type is QuestionType.TECHNICAL:
            return FollowUpPlan(
                kind="deeper",
                text="Good answer. Let's go deeper: what are the main trade-offs or limitations of this approach, "
                     "and how would you check that it works in practice?",
                reference="A strong answer names at least two trade-offs or limitations, compares one alternative "
                          "approach, and explains how success would be measured, for example with metrics, tests "
                          "or monitoring.",
                key_points=["trade-offs", "limitations", "an alternative approach", "how to measure success"],
                reason=f"Deeper follow-up because your answer was strong ({overall}/100).",
                focus_skills=focus_skills,
            )
        return FollowUpPlan(
            kind="deeper",
            text="Thanks. Looking back, what would you do differently next time, and why?",
            reference="A strong reflection is honest about one thing that could have gone better, explains what "
                      "you would change and why it would lead to a better result, and names what you learned.",
            key_points=["honest reflection", "what you would change", "why it would be better", "what you learned"],
            reason=f"Deeper follow-up because your answer was strong ({overall}/100).",
            focus_skills=focus_skills,
        )
    return None


def target_difficulty(recent_scores: list[int], current: Difficulty) -> Difficulty | None:
    """Harder after consistently strong answers, easier after weak ones; else None."""
    if len(recent_scores) < ADJUST_MIN_ANSWERS:
        return None
    average = sum(recent_scores) / len(recent_scores)
    index = _ORDER.index(current)
    if average >= ADJUST_HARDER_FROM and index < len(_ORDER) - 1:
        return _ORDER[index + 1]
    if average < ADJUST_EASIER_BELOW and index > 0:
        return _ORDER[index - 1]
    return None
