from datetime import datetime
from typing import Literal

from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql.schema import Column, ForeignKey
from sqlalchemy.sql.sqltypes import DateTime, Integer, String

from bartender.db.base import Base
from bartender.db.models.user import User

# Possible states of a job.
State = Literal["new", "queued", "running", "ok", "error"]


class Job(Base):
    """Model for the Job."""

    __tablename__ = "job"

    id = Column(Integer(), primary_key=True, autoincrement=True)
    name = Column(String(length=200))  # noqa: WPS432
    application = Column(String(length=200), nullable=False)  # noqa: WPS432
    state = Column(String(length=10), default="new", nullable=False)
    submitter_id = Column(GUID(), ForeignKey("user.id"), nullable=False)
    submitter: User = relationship("User", back_populates="jobs")
    created_on = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_on = Column(
        DateTime,
        onupdate=datetime.utcnow,
        default=datetime.utcnow,
        nullable=False,
    )
