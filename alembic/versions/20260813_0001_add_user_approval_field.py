"""add is_approved to users table

Revision ID: 20260813_0001
Revises: 
Create Date: 2026-08-13 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260813_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_approved", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.create_index(op.f("ix_users_is_approved"), "users", ["is_approved"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_is_approved"), table_name="users")
    op.drop_column("users", "is_approved")
