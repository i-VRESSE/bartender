from typing import List

from fastapi_users.db import (
    SQLAlchemyBaseOAuthAccountTableUUID,
    SQLAlchemyBaseUserTableUUID,
)
from sqlalchemy.orm import relationship

from bartender.db.base import Base

# From app/db.py at
# https://fastapi-users.github.io/fastapi-users/10.1/configuration/full-example/
# https://fastapi-users.github.io/fastapi-users/10.1/configuration/oauth/#sqlalchemy_1


class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
    """Model for the social OAuth accounts."""


class User(SQLAlchemyBaseUserTableUUID, Base):
    """Model for the User."""

    oauth_accounts: List[OAuthAccount] = relationship("OAuthAccount", lazy="joined")
