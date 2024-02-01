from datetime import datetime
from typing import Literal, Optional

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.sqltypes import DateTime, String

from bartender.db.base import Base
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

MAX_LENGTH_NAME = 200


class Job(Base):
    """Model for the Job."""

    __tablename__ = "job"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(length=MAX_LENGTH_NAME))
    application: Mapped[str] = mapped_column(
        String(length=MAX_LENGTH_NAME),
    )
    state: Mapped[State] = mapped_column(
        String(length=20),  # noqa: WPS432
        default="new",
    )
    submitter: Mapped[str] = mapped_column(String(length=254))  # noqa: WPS432
    # Identifier for job used by the scheduler
    internal_id: Mapped[Optional[str]] = mapped_column(
        String(length=MAX_LENGTH_NAME),
    )
    destination: Mapped[Optional[str]] = mapped_column(
        String(length=MAX_LENGTH_NAME),
    )
    created_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now,
    )
    updated_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        onupdate=now,
        default=now,
    )
