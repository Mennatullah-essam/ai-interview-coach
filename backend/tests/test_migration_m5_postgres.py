"""The Milestone 5 migration upgrades a populated Milestone 4 database without losing data.

Runs only against TEST_DATABASE_URL (same safety rules as test_migrations_postgres.py):
the database is rebuilt from scratch and left empty afterwards.
"""

import pytest
from sqlalchemy import text

from app.db.session import create_db_engine
from tests.test_migrations_postgres import _alembic, _test_database_url

pytestmark = pytest.mark.postgres

M4 = "d87ec07e6d71"
M3 = M4  # data below is valid at Milestone 4
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


def test_upgrade_from_milestone_4_keeps_existing_data():
    engine = create_db_engine(_test_database_url())
    try:
        with engine.begin() as conn:
            _alembic(conn, "downgrade", "base")
            _alembic(conn, "upgrade", M3)
            for statement in filter(str.strip, M3_DATA.split(";")):
                conn.execute(text(statement))
            assert _counts(conn) == [1] * len(COUNTS)

            conn.execute(text("""
                UPDATE evaluations SET dimensions = '[{"key": "relevance", "score": 70}]', missing_concepts = '["x"]';
                INSERT INTO candidate_profiles (id, user_id, status, data) VALUES
                  ('88888888-8888-8888-8888-888888888888', '11111111-1111-1111-1111-111111111111', 'confirmed', '{}');
                INSERT INTO improvement_plans (id, user_id, interview_id, target_role, plan_version, data) VALUES
                  ('99999999-9999-9999-9999-999999999999', '11111111-1111-1111-1111-111111111111',
                   '33333333-3333-3333-3333-333333333333', 'AI Engineer', 'plan-v1', '{"summary": "old"}');
            """))

            _alembic(conn, "upgrade", "head")
            assert _counts(conn) == [1] * len(COUNTS)
            evaluation = conn.execute(text(
                "SELECT score, dimensions, missing_concepts, concept_evidence, unsupported_claims, incorrect_claims, "
                "evidence_level, scoring_version FROM evaluations")).one()
            assert tuple(evaluation) == (64, [{"key": "relevance", "score": 70}], ["x"], [], [], [], None,
                                         "lexical-v0-draft")
            assert conn.execute(text("SELECT data FROM improvement_plans")).scalar_one() == {"summary": "old"}
            assert conn.execute(text("SELECT status FROM candidate_profiles")).scalar_one() == "confirmed"
            assert conn.execute(text("SELECT count(*) FROM agent_decisions")).scalar_one() == 0

            conn.execute(text("""
                INSERT INTO agent_decisions (id, session_id, question_id, kind, action, source, policy, rationale)
                VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '33333333-3333-3333-3333-333333333333',
                        '44444444-4444-4444-4444-444444444444', 'follow_up', 'continue', 'rules', 'accepted', 'ok');
            """))
            _alembic(conn, "downgrade", M4)  # back to Milestone 4: everything from before is still there
            assert _counts(conn) == [1] * len(COUNTS)
            assert conn.execute(text("SELECT dimensions FROM evaluations")).scalar_one() == [{"key": "relevance", "score": 70}]
            assert conn.execute(text("SELECT count(*) FROM improvement_plans")).scalar_one() == 1

            _alembic(conn, "upgrade", "head")
            assert _counts(conn) == [1] * len(COUNTS)
    finally:
        with engine.begin() as conn:
            _alembic(conn, "downgrade", "base")
        engine.dispose()
