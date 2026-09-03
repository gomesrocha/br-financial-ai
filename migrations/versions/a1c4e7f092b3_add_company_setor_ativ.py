"""add company setor_ativ

Revision ID: a1c4e7f092b3
Revises: d4f8a1c2b390
Create Date: 2026-09-02 17:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel  # noqa: F401
from alembic import op

revision: str = "a1c4e7f092b3"
down_revision: str | Sequence[str] | None = "d4f8a1c2b390"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column(
            "setor_ativ",
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("companies", "setor_ativ")
