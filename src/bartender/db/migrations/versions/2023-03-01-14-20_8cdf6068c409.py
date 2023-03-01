"""user_roles

Revision ID: 8cdf6068c409
Revises: 024e0181541b
Create Date: 2023-03-01 14:20:33.153747

"""
import sqlalchemy as sa
from alembic import op
from fastapi_users_db_sqlalchemy.generics import GUID

# revision identifiers, used by Alembic.
revision = "8cdf6068c409"
down_revision = "024e0181541b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "role",
        sa.Column("id", sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "user_roles",
        sa.Column(
            "user_id",
            GUID(),
            nullable=True,
        ),
        sa.Column("role_id", sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["role.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
        ),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("user_roles")
    op.drop_table("role")
    # ### end Alembic commands ###
