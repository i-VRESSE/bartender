from typing import List, Optional

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bartender.db.dependencies import get_db_session
from bartender.db.models.job_model import Job, States
from bartender.db.models.user import User


class JobDAO:
    """Class for accessing job table."""

    def __init__(self, session: AsyncSession = Depends(get_db_session)):
        self.session = session

    async def create_job(
        self,
        name: str,
        application: str,
        submitter: User,
    ) -> Optional[int]:
        """
        Add single job to session.

        :param name: name of a job.
        :param application: name of application to run job for.
        :param submitter: User who submitted the job.
        :return: id of a job.
        """
        job = Job(name=name, application=application, submitter=submitter)
        self.session.add(job)
        await self.session.commit()
        return job.id

    async def get_all_jobs(self, limit: int, offset: int, user: User) -> List[Job]:
        """
        Get all job models of user with limit/offset pagination.

        :param limit: limit of jobs.
        :param offset: offset of jobs.
        :param user: Which user to get jobs from.
        :return: stream of jobs.
        """
        raw_jobs = await self.session.execute(
            select(Job)
            .filter(Job.submitter == user)
            .limit(limit)
            .offset(offset),  # TODO also return shared jobs
        )

        return raw_jobs.scalars().fetchall()

    async def get_job(self, jobid: int, user: User) -> Job:
        """
        Get specific job model.

        :param jobid: name of job instance.
        :param user: Which user to get jobs from.
        :return: job model.
        """
        # This is the Asyncrhonous session;
        #  https://docs.sqlalchemy.org/en/14/orm/extensions/asyncio.html#sqlalchemy.ext.asyncio.AsyncSession.refresh
        result = await self.session.execute(
            select(Job)
            .filter(Job.id == jobid)
            .filter(Job.submitter == user),  # TODO also return shared jobs
        )
        return result.scalar_one()

    async def update_job_state(self, jobid: int, state: States | str) -> None:
        """
        Update state of a job.

        :param jobid: name of job instance.
        :param state: new state of job instance.
        """
        job = await self.session.get(Job, jobid)
        if job is None:
            return
        job.state = state
        await self.session.commit()
