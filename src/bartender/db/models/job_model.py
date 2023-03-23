from typing import Literal

from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql.schema import Column, ForeignKey
from sqlalchemy.sql.sqltypes import DateTime, Integer, String

from bartender.db.base import Base
from bartender.db.models.user import User
from bartender.db.utils import now

State = Literal[
    "new",
    "queued",
    "running",
    "staging_out",
    "ok",
    "error",
]  # noqa: WPS462
"""Possible states of a job.

* new: Job has been created by web service,
    but not yet submitted to a scheduler.
* queued: Job has been submitted to scheduler
    and is waiting in queue to be run.
* running: Job is being executed.
* staging_out: Files of job are being copied back to web service.
    Job is no longer executing.
* ok: Job has completed succesfully and files of job have been copied back.
* error: Job has completed unsuccesfully and
    files of job have been copied back.
    Look at stdout/stderr/returncode to get more information.
"""  # noqa: WPS428

CompletedStates: set[State] = {"ok", "error"}


class Job(Base):
    """Model for the Job."""

    __tablename__ = "job"

    id = Column(Integer(), primary_key=True, autoincrement=True)
    name = Column(String(length=200))  # noqa: WPS432
    application = Column(String(length=200), nullable=False)  # noqa: WPS432
    state = Column(String(length=20), default="new", nullable=False)  # noqa: WPS432
    submitter_id = Column(GUID(), ForeignKey("user.id"), nullable=False)
    submitter: User = relationship("User", back_populates="jobs")
    # Identifier for job used by the scheduler
    internal_id = Column(String(length=200))  # noqa: WPS432
    destination = Column(String(length=200))  # noqa: WPS432
    created_on = Column(DateTime(timezone=True), default=now, nullable=False)
    updated_on = Column(
        DateTime(timezone=True),
        onupdate=now,
        default=now,
        nullable=False,
    )
