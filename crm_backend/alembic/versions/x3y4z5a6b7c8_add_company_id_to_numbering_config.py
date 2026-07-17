"""Add company_id to numbering_configurations for multi-tenant isolation."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "x3y4z5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "w2x3y4z5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "numbering_configurations",
        sa.Column("company_id", sa.Integer(), nullable=True),
    )

    op.execute(
        """
        UPDATE numbering_configurations
        SET company_id = (SELECT id FROM companies ORDER BY id LIMIT 1)
        WHERE company_id IS NULL
        """
    )

    op.alter_column("numbering_configurations", "company_id", nullable=False)
    op.create_foreign_key(
        "fk_numbering_configurations_company_id",
        "numbering_configurations",
        "companies",
        ["company_id"],
        ["id"],
    )

    op.drop_index("ix_numbering_configurations_entity_name", table_name="numbering_configurations")
    op.create_index(
        "ix_numbering_configurations_entity_name",
        "numbering_configurations",
        ["entity_name"],
        unique=False,
    )
    op.create_index(
        "uq_numbering_configurations_company_entity",
        "numbering_configurations",
        ["company_id", "entity_name"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_numbering_configurations_company_entity", table_name="numbering_configurations")
    op.drop_index("ix_numbering_configurations_entity_name", table_name="numbering_configurations")
    op.drop_constraint(
        "fk_numbering_configurations_company_id",
        "numbering_configurations",
        type_="foreignkey",
    )
    op.drop_column("numbering_configurations", "company_id")
    op.create_index(
        "ix_numbering_configurations_entity_name",
        "numbering_configurations",
        ["entity_name"],
        unique=True,
    )
