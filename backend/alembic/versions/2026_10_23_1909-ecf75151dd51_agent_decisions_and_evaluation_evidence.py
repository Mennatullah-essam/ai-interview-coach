"""agent decisions and evaluation evidence

Milestone 5. Additive only: one new table and four new evaluation columns with
safe defaults. Existing rows are untouched: old evaluations simply have no
concept evidence (shown as before), and old interviews have no agent decisions.

* agent_decisions: audit trail of the adaptive interview agent (one row per
  decision about an evaluated question: follow-up decision or difficulty change)
* evaluations: concept_evidence, unsupported_claims, incorrect_claims, evidence_level

Revision ID: ecf75151dd51
Revises: d87ec07e6d71
Create Date: 2026-10-23 19:09:40.234883

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ecf75151dd51'
down_revision: Union[str, Sequence[str], None] = 'd87ec07e6d71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('agent_decisions',
    sa.Column('session_id', sa.Uuid(), nullable=False),
    sa.Column('question_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=12), nullable=False),
    sa.Column('action', sa.String(length=20), nullable=False),
    sa.Column('source', sa.String(length=8), nullable=False),
    sa.Column('policy', sa.String(length=40), nullable=False),
    sa.Column('llm_status', sa.String(length=40), nullable=True),
    sa.Column('rationale', sa.Text(), nullable=False),
    sa.Column('evidence', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), server_default=sa.text("'[]'"), nullable=False),
    sa.Column('target_concept', sa.String(length=200), nullable=True),
    sa.Column('result_question_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['question_id'], ['interview_questions.id'], name=op.f('fk_agent_decisions_question_id_interview_questions'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['result_question_id'], ['interview_questions.id'], name=op.f('fk_agent_decisions_result_question_id_interview_questions'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['session_id'], ['interview_sessions.id'], name=op.f('fk_agent_decisions_session_id_interview_sessions'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_agent_decisions')),
    sa.UniqueConstraint('question_id', 'kind', name='uq_agent_decisions_question_kind')
    )
    op.create_index(op.f('ix_agent_decisions_result_question_id'), 'agent_decisions', ['result_question_id'], unique=False)
    op.create_index(op.f('ix_agent_decisions_session_id'), 'agent_decisions', ['session_id'], unique=False)
    op.add_column('evaluations', sa.Column('concept_evidence', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), server_default=sa.text("'[]'"), nullable=False))
    op.add_column('evaluations', sa.Column('unsupported_claims', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), server_default=sa.text("'[]'"), nullable=False))
    op.add_column('evaluations', sa.Column('incorrect_claims', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), server_default=sa.text("'[]'"), nullable=False))
    op.add_column('evaluations', sa.Column('evidence_level', sa.String(length=12), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('evaluations', 'evidence_level')
    op.drop_column('evaluations', 'incorrect_claims')
    op.drop_column('evaluations', 'unsupported_claims')
    op.drop_column('evaluations', 'concept_evidence')
    op.drop_index(op.f('ix_agent_decisions_session_id'), table_name='agent_decisions')
    op.drop_index(op.f('ix_agent_decisions_result_question_id'), table_name='agent_decisions')
    op.drop_table('agent_decisions')
