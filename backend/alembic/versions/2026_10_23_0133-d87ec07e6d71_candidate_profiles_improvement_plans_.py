"""candidate profiles, improvement plans, adaptive interviews, rubric evaluation

Milestone 4. Additive only: two new tables and new nullable / defaulted columns.
Existing rows are untouched (old interviews: adaptive=false, no follow-ups;
old evaluations: dimensions NULL, shown with their original four categories).

* candidate_profiles: one reviewed, structured profile per user
* improvement_plans: one plan per completed interview
* interview_sessions: adaptive, max_follow_ups, personalized, job_description
* interview_questions: category, selection_reason, focus_skills, misconceptions,
  parent_question_id (follow-ups) and follow_up_kind
* evaluations: dimensions, missing_concepts, suggestions, explanation
* question_bank: misconceptions; `kind` may now be 'project_template'

Revision ID: d87ec07e6d71
Revises: 285a552def9d
Create Date: 2026-10-23 01:33:41.385196

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd87ec07e6d71'
down_revision: Union[str, Sequence[str], None] = '285a552def9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('candidate_profiles',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('cv_id', sa.Uuid(), nullable=True),
    sa.Column('status', sa.Enum('draft', 'confirmed', name='status', native_enum=False, create_constraint=True, length=20), nullable=False),
    sa.Column('data', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('extractor_version', sa.String(length=30), nullable=True),
    sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['cv_id'], ['cvs.id'], name=op.f('fk_candidate_profiles_cv_id_cvs'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_candidate_profiles_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_candidate_profiles')),
    sa.UniqueConstraint('user_id', name=op.f('uq_candidate_profiles_user_id'))
    )
    op.create_index(op.f('ix_candidate_profiles_cv_id'), 'candidate_profiles', ['cv_id'], unique=False)
    op.create_table('improvement_plans',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('interview_id', sa.Uuid(), nullable=False),
    sa.Column('target_role', sa.String(length=100), nullable=False),
    sa.Column('plan_version', sa.String(length=30), nullable=False),
    sa.Column('data', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['interview_id'], ['interview_sessions.id'], name=op.f('fk_improvement_plans_interview_id_interview_sessions'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_improvement_plans_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_improvement_plans')),
    sa.UniqueConstraint('interview_id', name=op.f('uq_improvement_plans_interview_id'))
    )
    op.create_index(op.f('ix_improvement_plans_user_id'), 'improvement_plans', ['user_id'], unique=False)
    op.add_column('evaluations', sa.Column('dimensions', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True))
    op.add_column('evaluations', sa.Column('missing_concepts', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), server_default=sa.text("'[]'"), nullable=False))
    op.add_column('evaluations', sa.Column('suggestions', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), server_default=sa.text("'[]'"), nullable=False))
    op.add_column('evaluations', sa.Column('explanation', sa.Text(), nullable=True))
    op.add_column('interview_questions', sa.Column('misconceptions', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), server_default=sa.text("'[]'"), nullable=False))
    op.add_column('interview_questions', sa.Column('category', sa.String(length=20), nullable=True))
    op.add_column('interview_questions', sa.Column('selection_reason', sa.Text(), nullable=True))
    op.add_column('interview_questions', sa.Column('focus_skills', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), server_default=sa.text("'[]'"), nullable=False))
    op.add_column('interview_questions', sa.Column('parent_question_id', sa.Uuid(), nullable=True))
    op.add_column('interview_questions', sa.Column('follow_up_kind', sa.String(length=12), nullable=True))
    op.create_index(op.f('ix_interview_questions_parent_question_id'), 'interview_questions', ['parent_question_id'], unique=False)
    op.create_foreign_key(op.f('fk_interview_questions_parent_question_id_interview_questions'), 'interview_questions', 'interview_questions', ['parent_question_id'], ['id'], ondelete='CASCADE')
    op.add_column('interview_sessions', sa.Column('adaptive', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('interview_sessions', sa.Column('max_follow_ups', sa.SmallInteger(), server_default='0', nullable=False))
    op.add_column('interview_sessions', sa.Column('personalized', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('interview_sessions', sa.Column('job_description', sa.Text(), nullable=True))
    op.add_column('question_bank', sa.Column('misconceptions', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), server_default=sa.text("'[]'"), nullable=False))
    # Allow the new project templates (autogenerate does not detect CHECK changes).
    op.drop_constraint(op.f('ck_question_bank_kind'), 'question_bank', type_='check')
    op.create_check_constraint(op.f('ck_question_bank_kind'), 'question_bank',
                               "kind IN ('generic', 'skill_template', 'project_template')")


def downgrade() -> None:
    """Downgrade schema.

    Data that only exists because of Milestone 4 features is removed first:
    follow-up questions (and their answers/evaluations) and project-template
    bank entries, which the previous schema cannot represent.
    """
    op.execute("DELETE FROM interview_questions WHERE parent_question_id IS NOT NULL")
    op.execute("UPDATE interview_questions SET bank_question_id = NULL WHERE bank_question_id IN "
               "(SELECT id FROM question_bank WHERE kind = 'project_template')")
    op.execute("DELETE FROM question_bank WHERE kind = 'project_template'")
    op.drop_constraint(op.f('ck_question_bank_kind'), 'question_bank', type_='check')
    op.create_check_constraint(op.f('ck_question_bank_kind'), 'question_bank', "kind IN ('generic', 'skill_template')")
    op.drop_column('question_bank', 'misconceptions')
    op.drop_column('interview_sessions', 'job_description')
    op.drop_column('interview_sessions', 'personalized')
    op.drop_column('interview_sessions', 'max_follow_ups')
    op.drop_column('interview_sessions', 'adaptive')
    op.drop_constraint(op.f('fk_interview_questions_parent_question_id_interview_questions'), 'interview_questions', type_='foreignkey')
    op.drop_index(op.f('ix_interview_questions_parent_question_id'), table_name='interview_questions')
    op.drop_column('interview_questions', 'follow_up_kind')
    op.drop_column('interview_questions', 'parent_question_id')
    op.drop_column('interview_questions', 'focus_skills')
    op.drop_column('interview_questions', 'selection_reason')
    op.drop_column('interview_questions', 'category')
    op.drop_column('interview_questions', 'misconceptions')
    op.drop_column('evaluations', 'explanation')
    op.drop_column('evaluations', 'suggestions')
    op.drop_column('evaluations', 'missing_concepts')
    op.drop_column('evaluations', 'dimensions')
    op.drop_index(op.f('ix_improvement_plans_user_id'), table_name='improvement_plans')
    op.drop_table('improvement_plans')
    op.drop_index(op.f('ix_candidate_profiles_cv_id'), table_name='candidate_profiles')
    op.drop_table('candidate_profiles')
