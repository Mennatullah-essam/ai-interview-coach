"""The Milestone 4 migration upgrades a populated Milestone 3 database without losing data.

Runs only against TEST_DATABASE_URL (same safety rules as test_migrations_postgres.py):
the database is rebuilt from scratch and left empty afterwards.
"""

import pytest
from sqlalchemy import text

from app.db.session import create_db_engine
from tests.test_migrations_postgres import _alembic, _test_database_url

pytestmark = pytest.mark.postgres

M3 = "285a552def9d"
M3_DATA = """
INSERT INTO users (id, full_name, email, password_hash) VALUES
  ('11111111-1111-1111-1111-111111111111', 'M3 User', 'm3.user@example.com', 'scrypt$hash');
INSERT INTO cvs (id, user_id, original_filename, storage_path, file_type, file_size_bytes, status, skills) VALUES
  ('77777777-7777-7777-7777-777777777777', '11111111-1111-1111-1111-111111111111', 'cv.pdf', 'ab/cd.pdf',
   'pdf', 1000, 'parsed', '["Python"]');
INSERT INTO question_bank (id, text, question_type, difficulty, ideal_answer, kind, role_tags, skill_tags, key_points)
VALUES ('22222222-2222-2222-2222-222222222222', 'How do you use {skill}?', 'technical', 'beginner', 'ref',
        'skill_template', '["AI Engineer"]', '[]', '["a point"]');
INSERT INTO interview_sessions (id, user_id, cv_id, target_role, interview_type, difficulty, question_count, status,
                                overall_score, completed_at, breakdown) VALUES
  ('33333333-3333-3333-3333-333333333333', '11111111-1111-1111-1111-111111111111',
   '77777777-7777-7777-7777-777777777777', 'AI Engineer', 'technical', 'beginner', 1, 'completed', 64, now(),
   '{"relevance": 70, "clarity": 60, "technical_depth": 55, "structure": 65}');
INSERT INTO interview_questions (id, session_id, bank_question_id, position, text, question_type, key_points) VALUES
  ('44444444-4444-4444-4444-444444444444', '33333333-3333-3333-3333-333333333333',
   '22222222-2222-2222-2222-222222222222', 1, 'How do you use Python?', 'technical', '["a point"]');
INSERT INTO answers (id, question_id, answer_text) VALUES
  ('55555555-5555-5555-5555-555555555555', '44444444-4444-4444-4444-444444444444', 'An M3 answer.');
INSERT INTO evaluations (id, answer_id, score, relevance_score, clarity_score, technical_depth_score, structure_score,
                         strengths, weaknesses, scoring_version) VALUES
  ('66666666-6666-6666-6666-666666666666', '55555555-5555-5555-5555-555555555555', 64, 70, 60, 55, 65,
   '["a"]', '["b"]', 'lexical-v0-draft');
"""

COUNTS = ("users", "cvs", "question_bank", "interview_sessions", "interview_questions", "answers", "evaluations")


def _counts(conn):
    return [conn.execute(text(f"SELECT count(*) FROM {t}")).scalar_one() for t in COUNTS]


def test_upgrade_from_milestone_3_keeps_existing_data():
    engine = create_db_engine(_test_database_url())
    try:
        with engine.begin() as conn:
            _alembic(conn, "downgrade", "base")
            _alembic(conn, "upgrade", M3)
            for statement in filter(str.strip, M3_DATA.split(";")):
                conn.execute(text(statement))
            assert _counts(conn) == [1] * len(COUNTS)

            _alembic(conn, "upgrade", "head")
            assert _counts(conn) == [1] * len(COUNTS)
            session = conn.execute(text(
                "SELECT overall_score, adaptive, max_follow_ups, personalized, job_description FROM interview_sessions"
            )).one()
            assert tuple(session) == (64, False, 0, False, None)  # old interviews stay fixed, non-personalised
            question = conn.execute(text(
                "SELECT text, parent_question_id, focus_skills, misconceptions FROM interview_questions")).one()
            assert tuple(question) == ("How do you use Python?", None, [], [])
            evaluation = conn.execute(text(
                "SELECT score, structure_score, dimensions, missing_concepts, scoring_version FROM evaluations")).one()
            assert tuple(evaluation) == (64, 65, None, [], "lexical-v0-draft")
            assert conn.execute(text("SELECT kind, misconceptions FROM question_bank")).one() == ("skill_template", [])
            assert conn.execute(text("SELECT count(*) FROM candidate_profiles")).scalar_one() == 0

            # New data that uses Milestone 4 features...
            conn.execute(text("""
                INSERT INTO question_bank (id, text, question_type, kind) VALUES
                  ('88888888-8888-8888-8888-888888888888', 'In your project {project}?', 'technical',
                   'project_template');
                INSERT INTO interview_questions (id, session_id, position, text, question_type, parent_question_id,
                                                 category) VALUES
                  ('99999999-9999-9999-9999-999999999999', '33333333-3333-3333-3333-333333333333', 2,
                   'Follow-up?', 'technical', '44444444-4444-4444-4444-444444444444', 'follow_up');
            """))
            # ...is removed cleanly on downgrade, and everything from Milestone 3 survives.
            _alembic(conn, "downgrade", M3)
            assert _counts(conn) == [1] * len(COUNTS)
            assert conn.execute(text("SELECT text FROM interview_questions")).scalar_one() == "How do you use Python?"
            assert conn.execute(text("SELECT structure_score FROM evaluations")).scalar_one() == 65

            _alembic(conn, "upgrade", "head")
            assert _counts(conn) == [1] * len(COUNTS)
    finally:
        with engine.begin() as conn:
            _alembic(conn, "downgrade", "base")
        engine.dispose()
