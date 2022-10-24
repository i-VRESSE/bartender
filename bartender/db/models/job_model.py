from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql.schema import Column, ForeignKey
from sqlalchemy.sql.sqltypes import Integer, String
from strenum import StrEnum

from bartender.db.base import Base
from bartender.db.models.user import User


class Job(Base):
    """Model for the Job."""

    __tablename__ = "job"

    id = Column(Integer(), primary_key=True, autoincrement=True)
    name = Column(String(length=200))  # noqa: WPS432
    application = Column(String(length=200), nullable=False)  # noqa: WPS432
    state = Column(String(length=100), default="new", nullable=False)
    submitter_id = Column(GUID(), ForeignKey("user.id"), nullable=False)
    submitter: User = relationship("User", back_populates="jobs")
    # TODO add submitted_on, finished_on columns


class States(StrEnum):
    """Possible states of a job."""

    NEW = "new"
    QUEUED = "queued"
    RUNNING = "running"
    OK = "ok"
    ERROR = "error"
