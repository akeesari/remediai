"""Add approval columns to incidents table

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-24 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("incidents", sa.Column("approval_status", sa.String(20), nullable=True))
    op.add_column("incidents", sa.Column("approved_by", sa.String(255), nullable=True))
    op.add_column(
        "incidents",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "incidents",
        sa.Column("approved_recommendation_rank", sa.Integer, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("incidents", "approved_recommendation_rank")
    op.drop_column("incidents", "approved_at")
    op.drop_column("incidents", "approved_by")
    op.drop_column("incidents", "approval_status")
