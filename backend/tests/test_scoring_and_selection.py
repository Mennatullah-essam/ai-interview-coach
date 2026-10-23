"""Scoring smoke/property checks (spec 16.9 V1-V2), question selection rules,
the shipped question bank, and production start-up guards."""

import pytest

from app.core.config import get_settings
from app.models import QuestionBankItem
from app.models.enums import Difficulty, InterviewType, QuestionKind, QuestionType
from app.scoring.scorer import evaluate_answer
from app.scoring.similarity import LexicalSimilarity, SbertSimilarity
from app.scoring.templates import interview_texts
from app.scoring.text_utils import chunks
from app.services.question_bank import check_bank, load_bank_file
from app.services.question_selection import match_roles, round_half_up, select_questions

ENGINE = LexicalSimilarity()
OFF_TOPIC = ("My favourite holiday was in Alexandria where we visited the library "
             "and ate fresh fish by the sea with my family every evening.")


@pytest.fixture(scope="module")
def bank_entries():
    entries, _ = load_bank_file(get_settings().question_bank_path)
    return entries


def _evaluate(entry, answer):
    return evaluate_answer(ENGINE, question=entry.text, question_type=entry.question_type, answer=answer,
                           reference=entry.reference_answer, key_points=entry.key_points)


# --- the shipped question bank -----------------------------------------------------------------


def test_shipped_bank_passes_its_checks(bank_entries):
    assert check_bank(bank_entries) == []


# --- V1 smoke checks ------------------------------------------------------------------------------


def test_reference_answer_beats_off_topic_answer_for_every_question(bank_entries):
    for entry in bank_entries:
        if entry.kind is QuestionKind.SKILL_TEMPLATE:
            continue
        good = _evaluate(entry, entry.reference_answer)
        bad = _evaluate(entry, OFF_TOPIC)
        assert good.relevance >= 90, entry.text
        assert good.overall_score >= bad.overall_score + 30, entry.text
        assert bad.relevance <= 35, entry.text


def test_same_input_gives_identical_result(bank_entries):
    entry = bank_entries[2]
    first, second = _evaluate(entry, entry.reference_answer), _evaluate(entry, entry.reference_answer)
    assert (first.overall_score, first.strengths, first.weaknesses, first.improvement_tip) == (
        second.overall_score, second.strengths, second.weaknesses, second.improvement_tip)


def test_long_answer_is_chunked_and_scored(bank_entries):
    entry = bank_entries[0]
    long_answer = (entry.reference_answer + " ") * 3
    long_answer = long_answer[:1500]
    assert len(chunks(long_answer)) > 1
    result = _evaluate(entry, long_answer)
    assert 0 <= result.overall_score <= 100


def test_feedback_lists_always_have_one_to_three_items(bank_entries):
    for answer in (bank_entries[5].reference_answer, OFF_TOPIC, "word " * 400):
        result = _evaluate(bank_entries[5], answer)
        assert 1 <= len(result.strengths) <= 3
        assert 1 <= len(result.weaknesses) <= 3
        assert result.improvement_tip
        assert "confiden" not in " ".join(result.strengths + result.weaknesses).lower()


def test_missing_key_points_are_named(bank_entries):
    entry = next(e for e in bank_entries if e.text.startswith("How would you handle an imbalanced"))
    result = _evaluate(entry, "I would simply train the model longer and hope that it learns the rare class well.")
    assert any("You did not mention" in w for w in result.weaknesses)


# --- V2 property checks ---------------------------------------------------------------------------------


def test_adding_a_key_point_never_lowers_coverage(bank_entries):
    entry = next(e for e in bank_entries if e.text.startswith("What is overfitting"))
    base = "Overfitting means the model memorises noise. I compare training and validation scores."
    more = base + " I also use regularization such as dropout and early stopping."
    assert _evaluate(entry, more).technical_depth >= _evaluate(entry, base).technical_depth


def test_repeating_a_sentence_does_not_inflate_the_score(bank_entries):
    entry = bank_entries[0]
    sentence = "I built a machine learning project and measured the impact on the business. "
    once = _evaluate(entry, sentence * 2)
    many = _evaluate(entry, sentence * 12)
    assert many.overall_score <= once.overall_score + 5


# --- sbert backend with a fake model (no download needed) ----------------------------------------------


class _FakeEncoder:
    """Bag-of-letters vectors: enough to exercise the sbert code path offline."""

    def encode(self, texts, normalize_embeddings=True):
        vectors = []
        for text in texts:
            v = [text.lower().count(ch) for ch in "abcdefghijklmnopqrstuvwxyz"]
            norm = sum(x * x for x in v) ** 0.5 or 1.0
            vectors.append([x / norm for x in v])
        return vectors


def test_sbert_backend_path_records_its_provenance(bank_entries):
    engine = SbertSimilarity("fake/model", encoder=_FakeEncoder())
    entry = bank_entries[0]
    result = evaluate_answer(engine, question=entry.text, question_type=entry.question_type,
                             answer=entry.reference_answer, reference=entry.reference_answer, key_points=entry.key_points)
    assert result.scoring_version == "sbert-v2"
    assert result.model_info["embedding_model"] == "fake/model"
    assert result.relevance == 100


# --- aggregation helpers ------------------------------------------------------------------------------


@pytest.mark.parametrize(("value", "expected"), [(82.5, 83), (81.5, 82), (82.4999, 82), (0.5, 1)])
def test_round_half_up_matches_javascript_math_round(value, expected):
    assert round_half_up(value) == expected  # Python's round(82.5) would give 82


def test_interview_texts_pick_weakest_and_strongest():
    breakdown = {"communication": 80, "relevance": 90, "structure": 50, "clarity": 70, "technical_depth": 60}
    strength, improvement, recommendations = interview_texts(breakdown)
    assert "focused" in strength  # relevance is strongest
    assert "result" in improvement  # structure is weakest
    assert len(recommendations) == 3 and "STAR" in recommendations[0]


# --- question selection ---------------------------------------------------------------------------------------


def _bank_items(entries):
    items = []
    for i, e in enumerate(entries):
        items.append(QuestionBankItem(
            id=i, kind=e.kind, text=e.text, question_type=e.question_type, difficulty=e.difficulty,
            role_tags=e.role_tags, skill_tags=e.skill_tags, ideal_answer=e.reference_answer,
            key_points=e.key_points, is_active=True,
        ))
    return items


@pytest.mark.parametrize(
    ("role", "expected"),
    [("AI Engineer", {"AI Engineer"}), ("Senior Backend Engineer", {"Backend Developer"}),
     ("ML Engineer", {"Machine Learning Engineer"}), ("Underwater Basket Weaver", set())],
)
def test_role_matching(role, expected):
    assert match_roles(role) == expected


def test_selection_is_deterministic_and_prefers_exact_difficulty(bank_entries):
    items = _bank_items(bank_entries)
    kwargs = dict(target_role="Data Analyst", interview_type=InterviewType.TECHNICAL,
                  difficulty=Difficulty.BEGINNER, question_count=5, cv_skills=[], seed="fixed-seed")
    first = select_questions(items, **kwargs)
    second = select_questions(items, **kwargs)
    assert [q.text for q in first] == [q.text for q in second]
    by_text = {e.text: e for e in bank_entries}
    assert all(by_text[q.text].difficulty is Difficulty.BEGINNER for q in first)


def test_mixed_interview_ratio(bank_entries):
    selected = select_questions(_bank_items(bank_entries), target_role="Software Engineer",
                                interview_type=InterviewType.MIXED, difficulty=Difficulty.INTERMEDIATE,
                                question_count=10, cv_skills=[], seed="s")
    types = [q.question_type for q in selected]
    assert types.count(QuestionType.TECHNICAL) == 6 and types.count(QuestionType.BEHAVIORAL) == 4


def test_skill_templates_use_cv_skills_once_each(bank_entries):
    selected = select_questions(_bank_items(bank_entries), target_role="AI Engineer",
                                interview_type=InterviewType.TECHNICAL, difficulty=Difficulty.ADVANCED,
                                question_count=15, cv_skills=["PyTorch", "Docker", "SQL"], seed="x")
    templated = [q for q in selected if any(s in q.text for s in ("PyTorch", "Docker", "SQL")) and "CV" in q.text
                 or "{skill}" in q.text]
    assert all("{skill}" not in q.text and "{skill}" not in q.ideal_answer for q in selected)
    assert len(templated) >= 1


# --- production guard -----------------------------------------------------------------------------------------


def test_production_refuses_unsafe_settings(monkeypatch):
    from app.main import check_production_settings

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "short")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        check_production_settings()

    monkeypatch.setenv("JWT_SECRET", "CHANGE_ME_TO_A_LONG_RANDOM_STRING")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="placeholder"):
        check_production_settings()

    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    get_settings.cache_clear()
    check_production_settings()  # secure cookies default to on in production
    assert get_settings().secure_cookies is True
