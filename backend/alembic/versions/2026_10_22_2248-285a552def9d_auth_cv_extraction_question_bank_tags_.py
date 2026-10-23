"""auth, cv extraction, question bank tags, results

Milestone 3. Non-destructive changes on top of the initial schema:

* users: password_hash, is_active; emails lower-cased + CHECK constraint
* refresh_tokens: new table (hashed, rotating login sessions)
* cvs: sha256, extracted skills/experience/education/projects, extractor_version,
  5 MB size CHECK
* question_bank: kind, role_tags (data copied from the old `role` column, which
  is then dropped), skill_tags, key_points, source_note
* interview_sessions: status may be "abandoned"; stored result summary columns
* interview_questions: snapshot of ideal_answer and key_points
* evaluations: confidence_score RENAMED to structure_score (values are kept),
  plus provenance columns (feedback_source, scoring_version, model_info, ...)

Existing rows are kept. Emails that differ only by case would collide when
lower-cased; the upgrade then stops with a unique-constraint error instead of
silently merging accounts.

Revision ID: 285a552def9d
Revises: 9c35bf359c62
Create Date: 2026-10-22 22:48:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "285a552def9d"
down_revision: Union[str, Sequence[str], None] = "9c35bf359c62"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def json_type():
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


EMPTY_LIST = sa.text("'[]'")


def upgrade() -> None:
    # --- users -----------------------------------------------------------
    op.execute("UPDATE users SET email = lower(trim(email)) WHERE email <> lower(trim(email))")
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False))
    op.create_check_constraint(op.f("ck_users_email_lowercase"), "users", "email = lower(email)")

    # --- refresh_tokens --------------------------------------------------
    op.create_table(
        "refresh_tokens",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_refresh_tokens_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
    )
    op.create_index(op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"], unique=False)

    # --- cvs ---------------------------------------------------------------
    op.add_column("cvs", sa.Column("sha256", sa.String(length=64), nullable=True))
    for name in ("skills", "experience", "education", "projects"):
        op.add_column("cvs", sa.Column(name, json_type(), server_default=EMPTY_LIST, nullable=False))
    op.add_column("cvs", sa.Column("extractor_version", sa.String(length=30), nullable=True))
    op.create_check_constraint(op.f("ck_cvs_file_size_max"), "cvs", "file_size_bytes <= 5242880")

    # --- question_bank -----------------------------------------------------
    op.add_column(
        "question_bank",
        sa.Column("kind", sa.String(length=20), server_default="generic", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_question_bank_kind"), "question_bank", "kind IN ('generic', 'skill_template')"
    )
    op.add_column(
        "question_bank",
        sa.Column("role_tags", json_type(), server_default=sa.text("'[\"general\"]'"), nullable=False),
    )
    # Keep the information from the old single `role` column.
    if op.get_bind().dialect.name == "postgresql":
        op.execute("UPDATE question_bank SET role_tags = jsonb_build_array(role) WHERE role IS NOT NULL")
    else:
        op.execute("UPDATE question_bank SET role_tags = json_array(role) WHERE role IS NOT NULL")
    op.drop_column("question_bank", "role")
    op.add_column("question_bank", sa.Column("skill_tags", json_type(), server_default=EMPTY_LIST, nullable=False))
    op.add_column("question_bank", sa.Column("key_points", json_type(), server_default=EMPTY_LIST, nullable=False))
    op.add_column("question_bank", sa.Column("source_note", sa.String(length=255), nullable=True))

    # --- interview_sessions ------------------------------------------------
    op.drop_constraint(op.f("ck_interview_sessions_status"), "interview_sessions", type_="check")
    op.create_check_constraint(
        op.f("ck_interview_sessions_status"),
        "interview_sessions",
        "status IN ('in_progress', 'completed', 'abandoned')",
    )
    op.add_column("interview_sessions", sa.Column("breakdown", json_type(), nullable=True))
    op.add_column("interview_sessions", sa.Column("additional_strength", sa.Text(), nullable=True))
    op.add_column("interview_sessions", sa.Column("additional_improvement", sa.Text(), nullable=True))
    op.add_column("interview_sessions", sa.Column("recommendations", json_type(), nullable=True))
    op.add_column("interview_sessions", sa.Column("generated_by", sa.String(length=8), nullable=True))
    op.create_index(
        "ix_interview_sessions_user_id_status_completed_at",
        "interview_sessions",
        ["user_id", "status", "completed_at"],
        unique=False,
    )

    # --- interview_questions -------------------------------------------------
    op.add_column("interview_questions", sa.Column("ideal_answer", sa.Text(), nullable=True))
    op.add_column(
        "interview_questions", sa.Column("key_points", json_type(), server_default=EMPTY_LIST, nullable=False)
    )

    # --- evaluations ---------------------------------------------------------
    op.drop_constraint(op.f("ck_evaluations_confidence_score_range"), "evaluations", type_="check")
    op.alter_column("evaluations", "confidence_score", new_column_name="structure_score")
    op.create_check_constraint(
        op.f("ck_evaluations_structure_score_range"), "evaluations", "structure_score BETWEEN 0 AND 100"
    )
    op.add_column("evaluations", sa.Column("feedback_source", sa.String(length=8), server_default="rules", nullable=False))
    op.add_column("evaluations", sa.Column("scoring_version", sa.String(length=30), server_default="legacy", nullable=False))
    op.add_column("evaluations", sa.Column("model_info", json_type(), server_default=sa.text("'{}'"), nullable=False))
    op.add_column("evaluations", sa.Column("semantic_similarity", sa.Numeric(precision=5, scale=4), nullable=True))
    op.add_column("evaluations", sa.Column("latency_ms", sa.Integer(), nullable=True))


def downgrade() -> None:
    # evaluations
    for name in ("latency_ms", "semantic_similarity", "model_info", "scoring_version", "feedback_source"):
        op.drop_column("evaluations", name)
    op.drop_constraint(op.f("ck_evaluations_structure_score_range"), "evaluations", type_="check")
    op.alter_column("evaluations", "structure_score", new_column_name="confidence_score")
    op.create_check_constraint(
        op.f("ck_evaluations_confidence_score_range"), "evaluations", "confidence_score BETWEEN 0 AND 100"
    )

    # interview_questions
    op.drop_column("interview_questions", "key_points")
    op.drop_column("interview_questions", "ideal_answer")

    # interview_sessions ("abandoned" did not exist before: treat as in progress)
    op.drop_index("ix_interview_sessions_user_id_status_completed_at", table_name="interview_sessions")
    for name in ("generated_by", "recommendations", "additional_improvement", "additional_strength", "breakdown"):
        op.drop_column("interview_sessions", name)
    op.execute("UPDATE interview_sessions SET status = 'in_progress' WHERE status = 'abandoned'")
    op.drop_constraint(op.f("ck_interview_sessions_status"), "interview_sessions", type_="check")
    op.create_check_constraint(
        op.f("ck_interview_sessions_status"), "interview_sessions", "status IN ('in_progress', 'completed')"
    )

    # question_bank (first non-"general" role tag goes back into `role`)
    op.add_column("question_bank", sa.Column("role", sa.String(length=100), nullable=True))
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "UPDATE question_bank SET role = (SELECT t FROM jsonb_array_elements_text(role_tags) AS t "
            "WHERE t <> 'general' LIMIT 1)"
        )
    for name in ("source_note", "key_points", "skill_tags", "role_tags"):
        op.drop_column("question_bank", name)
    op.drop_constraint(op.f("ck_question_bank_kind"), "question_bank", type_="check")
    op.drop_column("question_bank", "kind")

    # cvs
    op.drop_constraint(op.f("ck_cvs_file_size_max"), "cvs", type_="check")
    for name in ("extractor_version", "projects", "education", "experience", "skills", "sha256"):
        op.drop_column("cvs", name)

    # refresh_tokens
    op.drop_index(op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    # users
    op.drop_constraint(op.f("ck_users_email_lowercase"), "users", type_="check")
    op.drop_column("users", "is_active")
    op.drop_column("users", "password_hash")
