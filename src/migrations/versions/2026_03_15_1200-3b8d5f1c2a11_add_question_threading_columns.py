"""add question threading columns

Revision ID: 3b8d5f1c2a11
Revises: 6a0fb3f723d4
Create Date: 2026-03-15 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3b8d5f1c2a11"
down_revision: Union[str, None] = "6a0fb3f723d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "question_logs",
        sa.Column(
            "root_question_id",
            sa.Uuid(),
            nullable=True,
            comment="Root question id for this Q&A thread",
        ),
    )
    op.add_column(
        "question_logs",
        sa.Column(
            "parent_question_id",
            sa.Uuid(),
            nullable=True,
            comment="Immediate previous question id for supplementary turns",
        ),
    )
    op.add_column(
        "question_logs",
        sa.Column(
            "follow_up_index",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="0 for root question, 1..N for supplementary questions",
        ),
    )

    op.create_index(
        op.f("ix_question_logs_root_question_id"),
        "question_logs",
        ["root_question_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_question_logs_parent_question_id"),
        "question_logs",
        ["parent_question_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_question_logs_root_question_id_question_logs",
        "question_logs",
        "question_logs",
        ["root_question_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_question_logs_parent_question_id_question_logs",
        "question_logs",
        "question_logs",
        ["parent_question_id"],
        ["id"],
    )

    op.execute("UPDATE question_logs SET root_question_id = id WHERE root_question_id IS NULL")

    op.alter_column(
        "question_logs",
        "root_question_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.alter_column(
        "question_logs",
        "follow_up_index",
        existing_type=sa.Integer(),
        server_default=None,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_question_logs_parent_question_id_question_logs",
        "question_logs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_question_logs_root_question_id_question_logs",
        "question_logs",
        type_="foreignkey",
    )

    op.drop_index(op.f("ix_question_logs_parent_question_id"), table_name="question_logs")
    op.drop_index(op.f("ix_question_logs_root_question_id"), table_name="question_logs")

    op.drop_column("question_logs", "follow_up_index")
    op.drop_column("question_logs", "parent_question_id")
    op.drop_column("question_logs", "root_question_id")
