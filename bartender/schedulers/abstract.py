from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel

from bartender.db.models.job_model import State


class JobDescription(BaseModel):
    """Description for a job."""

    job_dir: Path
    app: str


class AbstractScheduler(ABC):
    """Abstract scheduler."""

    @abstractmethod
    async def close(self) -> None:
        """Cancel all runnning jobs and become unable to run new ones."""

    @abstractmethod
    async def submit(self, description: JobDescription) -> str:
        """Submit a job description to a scheduler for running.

        :param description: Description for a job.
        :return: Identifier that can be used later to interact with job.
        """

    @abstractmethod
    async def state(self, job_id: str) -> State:
        """Get state of a job.

        Once job is completed, the scheduler can forget about job.

        :param job_id: Identifier of job.
        :return: State of job.
        """

    @abstractmethod
    async def cancel(self, job_id: str) -> None:
        """Cancel queued or running job.

        :param job_id: Identifier of job.
        """
