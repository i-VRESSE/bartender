from fastapi_users.db import SQLAlchemyBaseUserTableUUID

from bartender.db.base import Base

# From app/db.py at
# https://fastapi-users.github.io/fastapi-users/10.1/configuration/full-example/


class User(SQLAlchemyBaseUserTableUUID, Base):
    """Model for the User."""
