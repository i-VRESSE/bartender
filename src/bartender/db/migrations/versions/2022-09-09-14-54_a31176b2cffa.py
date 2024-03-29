"""job application, state and submitter columns added

Revision ID: a31176b2cffa
Revises: ef872771a841
Create Date: 2022-09-09 14:54:25.919290

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a31176b2cffa"
down_revision = "ef872771a841"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "job",
        sa.Column("application", sa.String(length=200), nullable=False),
    )
    op.add_column("job", sa.Column("state", sa.String(length=20), nullable=False))
    op.add_column(
        "job",
        sa.Column(
            "submitter",
            sa.String(length=254),
            nullable=False,
        ),
    )
    op.add_column(
        "job",
        sa.Column("created_on", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column(
        "job",
        sa.Column("updated_on", sa.DateTime(timezone=True), nullable=False),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("job", "updated_on")
    op.drop_column("job", "created_on")
    op.drop_column("job", "submitter")
    op.drop_column("job", "state")
    op.drop_column("job", "application")
    # ### end Alembic commands ###
