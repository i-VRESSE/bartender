from enum import Enum

from sqlalchemy.sql.schema import Column
from sqlalchemy.sql.sqltypes import Integer, String

from bartender.db.base import Base


class Job(Base):
    """Model for the Job."""

    __tablename__ = "job"

    id = Column(Integer(), primary_key=True, autoincrement=True)
    name = Column(String(length=200))  # noqa: WPS432
    application = Column(String(length=200))  # noqa: WPS432
    state = Column(String(length=100), default="new")

    class states(str, Enum):
        NEW = "new"
        QUEUED = "queued"
        RUNNING = "running"
        OK = "ok"
        ERROR = "error"
