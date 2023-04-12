from typing import TYPE_CHECKING, Optional

from fastapi_users_db_sqlalchemy import (
    SQLAlchemyBaseOAuthAccountTableUUID,
    SQLAlchemyBaseUserTableUUID,
)
from sqlalchemy import BigInteger
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.sqltypes import String

from bartender.db.base import Base

# From app/db.py at
# https://fastapi-users.github.io/fastapi-users/10.1/configuration/full-example/
# https://fastapi-users.github.io/fastapi-users/10.1/configuration/oauth/#sqlalchemy_1


class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
    """Model for the social OAuth accounts."""

    if TYPE_CHECKING:  # pragma: no cover # noqa: WPS604 -- Python and mypy like it
        expires_at: Optional[int]
    else:
        # Orcid returns expire of 2293079986 which is greater then Integer|int32
        expires_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)


if TYPE_CHECKING:
    from bartender.db.models.job_model import Job


class User(SQLAlchemyBaseUserTableUUID, Base):
    """Model for the User."""

    oauth_accounts: Mapped[list[OAuthAccount]] = relationship(lazy="joined")
    jobs: Mapped[list["Job"]] = relationship(
        back_populates="submitter",
    )
    roles: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(ARRAY(String(100), dimensions=1)),
        default=[],
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"
