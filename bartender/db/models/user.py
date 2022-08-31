from typing import TYPE_CHECKING, List, Optional

from fastapi_users.db import (
    SQLAlchemyBaseOAuthAccountTableUUID,
    SQLAlchemyBaseUserTableUUID,
)
from sqlalchemy import BigInteger, Column
from sqlalchemy.orm import relationship

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
        expires_at: Optional[int] = Column(BigInteger, nullable=True)


class User(SQLAlchemyBaseUserTableUUID, Base):
    """Model for the User."""

    oauth_accounts: List[OAuthAccount] = relationship("OAuthAccount", lazy="joined")
