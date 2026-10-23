"""Model metadata, relationships, create/read and constraints (SQLite).

PostgreSQL-specific behaviour (JSONB, native UUID, timezone-aware timestamps)
is checked in test_migrations_postgres.py.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError, StatementError

from app.db.base import Base
from app.models import (
    CV,
    Answer,
    Evaluation,
    InterviewQuestion,
    InterviewSession,
    QuestionBankItem,
    User,
)
from app.models.enums import (
    CVFileType,
    CVStatus,
    Difficulty,
    InterviewType,
    QuestionType,
    SessionStatus,
)

EXPECTED_TABLES = {
    "users",
    "refresh_tokens",
    "cvs",
    "question_bank",
    "interview_sessions",
    "interview_questions",
    "answers",
    "evaluations",
    "candidate_profiles",  # Milestone 4
    "improvement_plans",  # Milestone 4
    "agent_decisions",  # Milestone 5
}


# --- helpers -----------------------------------------------------------------


def make_user(email: str = "candidate@example.com") -> User:
    return User(full_name="Test Candidate", email=email)


def make_cv(user: User, path: str = "uploads/cv-1.pdf") -> CV:
    return CV(
        user=user,
        original_filename="my_cv.pdf",
        storage_path=path,
        file_type=CVFileType.PDF,
        file_size_bytes=120_000,
    )


def make_session(user: User, cv: CV | None = None) -> InterviewSession:
    return InterviewSession(
        user=user,
        cv=cv,
        target_role="AI Engineer",
        interview_type=InterviewType.TECHNICAL,
        difficulty=Difficulty.INTERMEDIATE,
        question_count=2,
    )


def make_question(position: int, bank: QuestionBankItem | None = None) -> InterviewQuestion:
    return InterviewQuestion(
        position=position,
        text=f"Question {position}?",
        question_type=QuestionType.TECHNICAL,
        bank_question=bank,
    )


# --- metadata ----------------------------------------------------------------


def test_metadata_contains_exactly_the_expected_tables():
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_tables_are_created_in_test_database(sqlite_engine):
    assert set(inspect(sqlite_engine).get_table_names()) == EXPECTED_TABLES


@pytest.mark.parametrize(
    ("table", "column", "target", "on_delete"),
    [
        ("cvs", "user_id", "users", "CASCADE"),
        ("refresh_tokens", "user_id", "users", "CASCADE"),
        ("interview_sessions", "user_id", "users", "CASCADE"),
        ("interview_sessions", "cv_id", "cvs", "SET NULL"),
        ("interview_questions", "session_id", "interview_sessions", "CASCADE"),
        ("interview_questions", "bank_question_id", "question_bank", "SET NULL"),
        ("answers", "question_id", "interview_questions", "CASCADE"),
        ("evaluations", "answer_id", "answers", "CASCADE"),
        ("interview_questions", "parent_question_id", "interview_questions", "CASCADE"),
        ("candidate_profiles", "user_id", "users", "CASCADE"),
        ("candidate_profiles", "cv_id", "cvs", "SET NULL"),
        ("improvement_plans", "user_id", "users", "CASCADE"),
        ("improvement_plans", "interview_id", "interview_sessions", "CASCADE"),
        ("agent_decisions", "session_id", "interview_sessions", "CASCADE"),
        ("agent_decisions", "question_id", "interview_questions", "CASCADE"),
        ("agent_decisions", "result_question_id", "interview_questions", "SET NULL"),
    ],
)
def test_foreign_keys(table, column, target, on_delete):
    (fk,) = Base.metadata.tables[table].c[column].foreign_keys
    assert fk.column.table.name == target
    assert fk.column.name == "id"
    assert fk.ondelete == on_delete


def test_every_foreign_key_column_is_indexed():
    """Unindexed FK columns make joins and cascading deletes slow."""
    for table in Base.metadata.tables.values():
        indexed_first_columns = {idx.columns[0].name for idx in table.indexes}
        indexed_first_columns |= {
            uc.columns[0].name for uc in table.constraints if uc.__class__.__name__ == "UniqueConstraint"
        }
        for fk in table.foreign_keys:
            assert fk.parent.name in indexed_first_columns, f"{table.name}.{fk.parent.name}"


def test_relationships_are_wired_both_ways():
    assert User.cvs.property.mapper.class_ is CV
    assert User.interview_sessions.property.mapper.class_ is InterviewSession
    assert InterviewSession.questions.property.mapper.class_ is InterviewQuestion
    assert InterviewQuestion.answer.property.uselist is False
    assert Answer.evaluation.property.uselist is False
    assert Evaluation.answer.property.back_populates == "evaluation"


# --- create / read -----------------------------------------------------------


def test_full_interview_can_be_created_and_read_back(db_session):
    user = make_user()
    cv = make_cv(user)
    bank_item = QuestionBankItem(text="Explain overfitting.", question_type=QuestionType.TECHNICAL)
    interview = make_session(user, cv)
    # Added out of order on purpose: reading back must follow `position`.
    interview.questions = [make_question(2), make_question(1, bank_item)]
    first = interview.questions[1]
    first.answer = Answer(answer_text="I would use regularisation and more data.")
    first.answer.evaluation = Evaluation(
        score=84,
        relevance_score=88,
        clarity_score=81,
        technical_depth_score=79,
        structure_score=83,
        strengths=["Clear structure", "Relevant example"],
        weaknesses=["Quantify the impact"],
        improvement_tip="Use the STAR method.",
        ideal_answer="An ideal answer...",
    )
    db_session.add(interview)
    db_session.commit()
    interview_id = interview.id
    db_session.expunge_all()  # force a real read from the database

    loaded = db_session.get(InterviewSession, interview_id)

    assert isinstance(loaded.id, uuid.UUID)
    assert loaded.status is SessionStatus.IN_PROGRESS  # default
    assert loaded.cv.status is CVStatus.UPLOADED  # default
    assert loaded.created_at is not None and loaded.updated_at is not None
    assert loaded.user.email == "candidate@example.com"
    assert [q.position for q in loaded.questions] == [1, 2]
    q1 = loaded.questions[0]
    assert q1.bank_question.text == "Explain overfitting."
    assert q1.answer.evaluation.score == 84
    assert q1.answer.evaluation.strengths == ["Clear structure", "Relevant example"]
    assert loaded.questions[1].answer is None


def test_question_ids_are_stable_and_independent_of_position(db_session):
    interview = make_session(make_user())
    interview.questions = [make_question(1), make_question(2)]
    db_session.add(interview)
    db_session.commit()
    ids = {q.position: q.id for q in interview.questions}

    # Swap the order (one step at a time, because positions are unique).
    q1, q2 = interview.questions
    q1.position = 3
    db_session.flush()
    q2.position = 1
    db_session.flush()
    q1.position = 2
    db_session.commit()

    assert db_session.get(InterviewQuestion, ids[1]).position == 2
    assert db_session.get(InterviewQuestion, ids[2]).position == 1


def test_user_history_newest_first(db_session):
    user = make_user()
    other_user = make_user("someone.else@example.com")
    older = make_session(user)
    newer = make_session(user)
    older.created_at = datetime(2026, 9, 1, tzinfo=UTC)
    newer.created_at = datetime(2026, 10, 1, tzinfo=UTC)
    newer.status = SessionStatus.COMPLETED
    newer.completed_at = datetime(2026, 10, 1, 1, tzinfo=UTC)
    newer.overall_score = 82
    db_session.add_all([older, newer, make_session(other_user)])
    db_session.commit()

    history = db_session.scalars(
        select(InterviewSession)
        .where(InterviewSession.user_id == user.id)
        .order_by(InterviewSession.created_at.desc())
    ).all()

    assert [s.id for s in history] == [newer.id, older.id]
    assert history[0].overall_score == 82


# --- delete behaviour (needs foreign keys enforced) --------------------------


def test_deleting_user_deletes_all_their_data(db_session):
    user = make_user()
    interview = make_session(user, make_cv(user))
    interview.questions = [make_question(1)]
    interview.questions[0].answer = Answer(answer_text="An answer.")
    interview.questions[0].answer.evaluation = Evaluation(score=70)
    db_session.add(interview)
    db_session.commit()

    db_session.delete(user)
    db_session.commit()

    for model in (User, CV, InterviewSession, InterviewQuestion, Answer, Evaluation):
        assert db_session.scalars(select(model)).all() == [], model.__name__


def test_deleting_cv_keeps_interview_history(db_session):
    user = make_user()
    cv = make_cv(user)
    interview = make_session(user, cv)
    db_session.add(interview)
    db_session.commit()

    db_session.delete(cv)
    db_session.commit()
    db_session.expire_all()

    assert db_session.get(InterviewSession, interview.id).cv_id is None


def test_deleting_bank_question_keeps_asked_question(db_session):
    bank_item = QuestionBankItem(text="Bank question?", question_type=QuestionType.BEHAVIORAL)
    interview = make_session(make_user())
    interview.questions = [make_question(1, bank_item)]
    db_session.add(interview)
    db_session.commit()
    question_id = interview.questions[0].id

    db_session.execute(text("DELETE FROM question_bank"))
    db_session.commit()
    db_session.expire_all()

    question = db_session.get(InterviewQuestion, question_id)
    assert question.bank_question_id is None
    assert question.text == "Question 1?"


# --- constraints ---------------------------------------------------------------


def commit_expecting_integrity_error(db_session, *objects):
    db_session.add_all(objects)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_email_must_be_unique(db_session):
    db_session.add(make_user("same@example.com"))
    db_session.commit()
    commit_expecting_integrity_error(db_session, make_user("same@example.com"))


def test_question_position_unique_within_session(db_session):
    interview = make_session(make_user())
    interview.questions = [make_question(1), make_question(1)]
    commit_expecting_integrity_error(db_session, interview)


def test_only_one_answer_per_question(db_session):
    interview = make_session(make_user())
    question = make_question(1)
    interview.questions = [question]
    db_session.add(interview)
    db_session.commit()

    commit_expecting_integrity_error(
        db_session,
        Answer(question_id=question.id, answer_text="first"),
        Answer(question_id=question.id, answer_text="second"),
    )


@pytest.mark.parametrize("bad_score", [-1, 101])
def test_scores_must_be_between_0_and_100(db_session, bad_score):
    interview = make_session(make_user())
    interview.questions = [make_question(1)]
    interview.questions[0].answer = Answer(answer_text="An answer.")
    interview.questions[0].answer.evaluation = Evaluation(score=bad_score)
    commit_expecting_integrity_error(db_session, interview)


def test_completed_session_requires_completed_at(db_session):
    interview = make_session(make_user())
    interview.status = SessionStatus.COMPLETED  # but completed_at left empty
    commit_expecting_integrity_error(db_session, interview)


def test_empty_answer_rejected(db_session):
    interview = make_session(make_user())
    interview.questions = [make_question(1)]
    interview.questions[0].answer = Answer(answer_text="")
    commit_expecting_integrity_error(db_session, interview)


def test_invalid_enum_value_rejected_by_orm(db_session):
    interview = make_session(make_user())
    interview.difficulty = "expert"
    db_session.add(interview)
    with pytest.raises(StatementError):
        db_session.commit()
    db_session.rollback()


def test_invalid_enum_value_rejected_by_database_check(db_session):
    db_session.add(make_user())
    db_session.commit()
    user_id = db_session.scalars(select(User.id)).one()

    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO cvs (id, user_id, original_filename, storage_path, file_type,"
                " file_size_bytes, status) VALUES (:id, :user_id, 'x.exe', 'p', 'exe', 10, 'uploaded')"
            ),
            {"id": uuid.uuid4().hex, "user_id": user_id.hex},
        )
    db_session.rollback()


def test_missing_required_field_rejected(db_session):
    commit_expecting_integrity_error(db_session, User(full_name="No Email"))
