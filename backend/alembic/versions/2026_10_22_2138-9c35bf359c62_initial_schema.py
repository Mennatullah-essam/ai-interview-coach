"""initial schema

Creates the Milestone 2 tables: users, cvs, question_bank,
interview_sessions, interview_questions, answers, evaluations.
Generated with `alembic revision --autogenerate`, then reviewed.

Revision ID: 9c35bf359c62
Revises:
Create Date: 2026-10-22 21:38:32.667330

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '9c35bf359c62'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('question_bank',
    sa.Column('text', sa.String(length=1000), nullable=False),
    sa.Column('question_type', sa.Enum('technical', 'behavioral', name='question_type', native_enum=False, create_constraint=True, length=20), nullable=False),
    sa.Column('role', sa.String(length=100), nullable=True),
    sa.Column('difficulty', sa.Enum('beginner', 'intermediate', 'advanced', name='difficulty', native_enum=False, create_constraint=True, length=20), nullable=True),
    sa.Column('ideal_answer', sa.Text(), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_question_bank')),
    sa.UniqueConstraint('text', name=op.f('uq_question_bank_text'))
    )
    op.create_table('users',
    sa.Column('full_name', sa.String(length=100), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email'))
    )
    op.create_table('cvs',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('original_filename', sa.String(length=255), nullable=False),
    sa.Column('storage_path', sa.String(length=500), nullable=False),
    sa.Column('file_type', sa.Enum('pdf', 'docx', name='file_type', native_enum=False, create_constraint=True, length=20), nullable=False),
    sa.Column('file_size_bytes', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('uploaded', 'parsed', 'failed', name='status', native_enum=False, create_constraint=True, length=20), nullable=False),
    sa.Column('extracted_text', sa.Text(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('file_size_bytes > 0', name=op.f('ck_cvs_file_size_positive')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_cvs_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_cvs')),
    sa.UniqueConstraint('storage_path', name=op.f('uq_cvs_storage_path'))
    )
    op.create_index(op.f('ix_cvs_user_id'), 'cvs', ['user_id'], unique=False)
    op.create_table('interview_sessions',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('cv_id', sa.Uuid(), nullable=True),
    sa.Column('target_role', sa.String(length=100), nullable=False),
    sa.Column('interview_type', sa.Enum('technical', 'behavioral', 'mixed', name='interview_type', native_enum=False, create_constraint=True, length=20), nullable=False),
    sa.Column('difficulty', sa.Enum('beginner', 'intermediate', 'advanced', name='difficulty', native_enum=False, create_constraint=True, length=20), nullable=False),
    sa.Column('question_count', sa.SmallInteger(), nullable=False),
    sa.Column('status', sa.Enum('in_progress', 'completed', name='status', native_enum=False, create_constraint=True, length=20), nullable=False),
    sa.Column('overall_score', sa.SmallInteger(), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(status = 'completed') = (completed_at IS NOT NULL)", name=op.f('ck_interview_sessions_completed_at_matches_status')),
    sa.CheckConstraint('overall_score BETWEEN 0 AND 100', name=op.f('ck_interview_sessions_overall_score_range')),
    sa.CheckConstraint('question_count > 0', name=op.f('ck_interview_sessions_question_count_positive')),
    sa.ForeignKeyConstraint(['cv_id'], ['cvs.id'], name=op.f('fk_interview_sessions_cv_id_cvs'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_interview_sessions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_interview_sessions'))
    )
    op.create_index(op.f('ix_interview_sessions_cv_id'), 'interview_sessions', ['cv_id'], unique=False)
    op.create_index('ix_interview_sessions_user_id_created_at', 'interview_sessions', ['user_id', 'created_at'], unique=False)
    op.create_table('interview_questions',
    sa.Column('session_id', sa.Uuid(), nullable=False),
    sa.Column('bank_question_id', sa.Uuid(), nullable=True),
    sa.Column('position', sa.SmallInteger(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('question_type', sa.Enum('technical', 'behavioral', name='question_type', native_enum=False, create_constraint=True, length=20), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('position >= 1', name=op.f('ck_interview_questions_position_positive')),
    sa.ForeignKeyConstraint(['bank_question_id'], ['question_bank.id'], name=op.f('fk_interview_questions_bank_question_id_question_bank'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['session_id'], ['interview_sessions.id'], name=op.f('fk_interview_questions_session_id_interview_sessions'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_interview_questions')),
    sa.UniqueConstraint('session_id', 'position', name=op.f('uq_interview_questions_session_id_position'))
    )
    op.create_index(op.f('ix_interview_questions_bank_question_id'), 'interview_questions', ['bank_question_id'], unique=False)
    op.create_table('answers',
    sa.Column('question_id', sa.Uuid(), nullable=False),
    sa.Column('answer_text', sa.Text(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('length(answer_text) > 0', name=op.f('ck_answers_answer_text_not_empty')),
    sa.ForeignKeyConstraint(['question_id'], ['interview_questions.id'], name=op.f('fk_answers_question_id_interview_questions'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_answers')),
    sa.UniqueConstraint('question_id', name=op.f('uq_answers_question_id'))
    )
    op.create_table('evaluations',
    sa.Column('answer_id', sa.Uuid(), nullable=False),
    sa.Column('score', sa.SmallInteger(), nullable=False),
    sa.Column('relevance_score', sa.SmallInteger(), nullable=True),
    sa.Column('clarity_score', sa.SmallInteger(), nullable=True),
    sa.Column('technical_depth_score', sa.SmallInteger(), nullable=True),
    sa.Column('confidence_score', sa.SmallInteger(), nullable=True),
    sa.Column('strengths', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('weaknesses', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('improvement_tip', sa.Text(), nullable=True),
    sa.Column('ideal_answer', sa.Text(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('clarity_score BETWEEN 0 AND 100', name=op.f('ck_evaluations_clarity_score_range')),
    sa.CheckConstraint('confidence_score BETWEEN 0 AND 100', name=op.f('ck_evaluations_confidence_score_range')),
    sa.CheckConstraint('relevance_score BETWEEN 0 AND 100', name=op.f('ck_evaluations_relevance_score_range')),
    sa.CheckConstraint('score BETWEEN 0 AND 100', name=op.f('ck_evaluations_score_range')),
    sa.CheckConstraint('technical_depth_score BETWEEN 0 AND 100', name=op.f('ck_evaluations_technical_depth_score_range')),
    sa.ForeignKeyConstraint(['answer_id'], ['answers.id'], name=op.f('fk_evaluations_answer_id_answers'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_evaluations')),
    sa.UniqueConstraint('answer_id', name=op.f('uq_evaluations_answer_id'))
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('evaluations')
    op.drop_table('answers')
    op.drop_index(op.f('ix_interview_questions_bank_question_id'), table_name='interview_questions')
    op.drop_table('interview_questions')
    op.drop_index('ix_interview_sessions_user_id_created_at', table_name='interview_sessions')
    op.drop_index(op.f('ix_interview_sessions_cv_id'), table_name='interview_sessions')
    op.drop_table('interview_sessions')
    op.drop_index(op.f('ix_cvs_user_id'), table_name='cvs')
    op.drop_table('cvs')
    op.drop_table('users')
    op.drop_table('question_bank')
