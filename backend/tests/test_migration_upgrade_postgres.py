"""The Milestone 3 migration upgrades a populated Milestone 2 database without losing data.

Runs only against TEST_DATABASE_URL (same safety rules as test_migrations_postgres.py):
the database is rebuilt from scratch and left empty afterwards.
"""

import pytest
from sqlalchemy import text

from app.db.session import create_db_engine
from tests.test_migrations_postgres import _alembic, _test_database_url

pytestmark = pytest.mark.postgres

M2_DATA = """
INSERT INTO users (id, full_name, email) VALUES
  ('11111111-1111-1111-1111-111111111111', 'Old User', 'Old.User@Example.COM');
INSERT INTO question_bank (id, text, question_type, role, difficulty, ideal_answer) VALUES
  ('22222222-2222-2222-2222-222222222222', 'Old bank question?', 'technical', 'Data Scientist', 'beginner', 'Old ref');
INSERT INTO interview_sessions (id, user_id, target_role, interview_type, difficulty, question_count, status,
                                overall_score, completed_at) VALUES
  ('33333333-3333-3333-3333-333333333333', '11111111-1111-1111-1111-111111111111', 'Data Scientist',
   'technical', 'beginner', 1, 'completed', 70, now());
INSERT INTO interview_questions (id, session_id, bank_question_id, position, text, question_type) VALUES
  ('44444444-4444-4444-4444-444444444444', '33333333-3333-3333-3333-333333333333',
   '22222222-2222-2222-2222-222222222222', 1, 'Old bank question?', 'technical');
INSERT INTO answers (id, question_id, answer_text) VALUES
  ('55555555-5555-5555-5555-555555555555', '44444444-4444-4444-4444-444444444444', 'An old answer.');
INSERT INTO evaluations (id, answer_id, score, confidence_score, strengths, weaknesses) VALUES
  ('66666666-6666-6666-6666-666666666666', '55555555-5555-5555-5555-555555555555', 70, 81, '["a"]', '["b"]');
"""


def test_upgrade_from_milestone_2_keeps_existing_data():
    engine = create_db_engine(_test_database_url())
    try:
        with engine.begin() as conn:
            _alembic(conn, "downgrade", "base")
            _alembic(conn, "upgrade", "9c35bf359c62")
            for statement in filter(str.strip, M2_DATA.split(";")):
                conn.execute(text(statement))
            _alembic(conn, "upgrade", "head")

            user = conn.execute(text("SELECT email, password_hash, is_active FROM users")).one()
            assert tuple(user) == ("old.user@example.com", None, True)
            bank = conn.execute(text("SELECT role_tags, kind, key_points FROM question_bank")).one()
            assert tuple(bank) == (["Data Scientist"], "generic", [])
            evaluation = conn.execute(text("SELECT structure_score, scoring_version FROM evaluations")).one()
            assert tuple(evaluation) == (81, "legacy")
            session = conn.execute(text("SELECT status, overall_score FROM interview_sessions")).one()
            assert tuple(session) == ("completed", 70)
            counts = [conn.execute(text(f"SELECT count(*) FROM {t}")).scalar_one()
                      for t in ("interview_questions", "answers")]
            assert counts == [1, 1]

            _alembic(conn, "downgrade", "9c35bf359c62")  # back to Milestone 2, still without data loss
            assert conn.execute(text("SELECT confidence_score FROM evaluations")).scalar_one() == 81
            assert conn.execute(text("SELECT role FROM question_bank")).scalar_one() == "Data Scientist"
            _alembic(conn, "upgrade", "head")
            assert conn.execute(text("SELECT structure_score FROM evaluations")).scalar_one() == 81
    finally:
        with engine.begin() as conn:
            _alembic(conn, "downgrade", "base")
        engine.dispose()
