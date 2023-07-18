"""egi access token >1024 chars

Revision ID: 02d0b8af4831
Revises: cf2424f395bc
Create Date: 2023-06-16 12:39:04.813291

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "02d0b8af4831"
down_revision = "cf2424f395bc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "oauth_account",
        "access_token",
        type_=sa.VARCHAR(length=2048),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "oauth_account",
        "access_token",
        type_=sa.VARCHAR(length=1048),
        nullable=False,
    )
