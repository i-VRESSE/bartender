from abc import ABC, abstractmethod
from pathlib import Path
from types import TracebackType
from typing import Optional, Type

from pydantic import BaseModel

from bartender.db.models.job_model import State


class JobDescription(BaseModel):
    """Description for a job."""

    # Directory where job input and output are stored.
    job_dir: Path
    # Command to run
    command: str


class AbstractScheduler(ABC):
    """Abstract scheduler."""

    @abstractmethod
    async def close(self) -> None:
        """Cancel all runnning jobs and make scheduler unable to work."""

    @abstractmethod
    async def submit(self, description: JobDescription) -> str:
        """Submit a job description for running.

        Args:
            description: Description for a job.

        Returns:
            Identifier that can be used later to interact with job.
        """

    @abstractmethod
    async def state(self, job_id: str) -> State:
        """Get state of a job.

        Once job is completed, then scheduler can forget job.

        Args:
            job_id: Identifier of job.

        Returns:
            State of job.
        """

    async def states(self, job_ids: list[str]) -> list[State]:
        """Get state of jobs.

        Once a job is completed, then scheduler can forget job.

        Args:
            job_ids: Identifiers of jobs.

        Returns:
            States of jobs.
        """
        mystates = []
        for job_id in job_ids:
            mystate = await self.state(job_id)
            mystates.append(mystate)
        return mystates

    @abstractmethod
    async def cancel(self, job_id: str) -> None:
        """Cancel a queued or running job.

        Once a queued job is cancelled, then the scheduler can forget job.

        Args:
            job_id: Identifier of job.
        """

    async def __aenter__(self) -> "AbstractScheduler":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        await self.close()
