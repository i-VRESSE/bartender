from datetime import datetime
from typing import Annotated, Optional

from fastapi import Depends
from sqlalchemy import select

from bartender.db.dependencies import CurrentSession
from bartender.db.models.job_model import Job, State
from bartender.db.models.user import User


class JobDAO:
    """Class for accessing job table."""

    def __init__(self, session: CurrentSession):
        self.session = session

    async def create_job(  # noqa: WPS211
        self,
        name: Optional[str],
        application: str,
        submitter: User,
        updated_on: Optional[datetime] = None,
        created_on: Optional[datetime] = None,
    ) -> Optional[int]:
        """Add single job to session.

        Args:
            name: name of a job.
            application: name of application to run job for.
            submitter: User who submitted the job.
            updated_on: Datetime when job was last updated.
            created_on: Datetime when job was created.

        Returns:
            id of a job.
        """
        if name is None:
            name = ""
        job = Job(
            name=name,
            application=application,
            submitter=submitter,
            created_on=created_on,
            updated_on=updated_on,
        )
        self.session.add(job)
        await self.session.commit()
        return job.id

    async def get_all_jobs(self, limit: int, offset: int, user: User) -> list[Job]:
        """Get all job models of user with limit/offset pagination.

        Args:
            limit: limit of jobs.
            offset: offset of jobs.
            user: Which user to get jobs from.

        Returns:
            stream of jobs.
        """
        # TODO also return shared jobs
        raw_jobs = await self.session.scalars(
            select(Job)
            .where(Job.submitter == user)
            .limit(limit)
            .offset(offset),
        )

        return raw_jobs.all()

    async def get_job(self, jobid: int, user: User) -> Job:
        """Get specific job model.

        Args:
            jobid: name of job instance.
            user: Which user to get jobs from.

        Returns:
            job model.
        """
        # This is the Asyncrhonous session;
        #  https://docs.sqlalchemy.org/en/14/orm/extensions/asyncio.html#sqlalchemy.ext.asyncio.AsyncSession.refresh
        result = await self.session.execute(
            select(Job)
            .filter(Job.id == jobid)
            .filter(Job.submitter == user),  # TODO also return shared jobs
        )
        return result.scalar_one()

    async def update_job_state(self, jobid: int, state: State) -> None:
        """Update state of a job.

        Args:
            jobid: name of job instance.
            state: new state of job instance.
        """
        job = await self.session.get(Job, jobid)
        if job is None:
            return
        job.state = state
        await self.session.commit()

    async def update_internal_job_id(
        self,
        jobid: int,
        internal_job_id: str,
        destination: str,
    ) -> None:
        """Update internal id and destination of a job.

        Args:
            jobid: name of job instance.
            internal_job_id: new internal job id of job instance.
            destination: To which scheduler/filesystem the job was submitted.
        """
        job = await self.session.get(Job, jobid)
        if job is None:
            return
        job.internal_id = internal_job_id
        job.destination = destination
        await self.session.commit()


CurrentJobDAO = Annotated[JobDAO, Depends()]
