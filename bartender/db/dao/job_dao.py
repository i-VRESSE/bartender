from typing import List, Optional

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bartender.db.dependencies import get_db_session
from bartender.db.models.job_model import Job


class JobDAO:
    """Class for accessing job table."""

    def __init__(self, session: AsyncSession = Depends(get_db_session)):
        self.session = session

    async def create_job(self, name: str, application: str) -> Optional[int]:
        """
        Add single job to session.

        :param name: name of a job.
        :param application: name of application to run job for.
        :return: id of a job.
        """
        job = Job(name=name, application=application)
        self.session.add(job)
        await self.session.commit()
        return job.id

    async def get_all_jobs(self, limit: int, offset: int) -> List[Job]:
        """
        Get all job models with limit/offset pagination.

        :param limit: limit of jobs.
        :param offset: offset of jobs.
        :return: stream of jobs.
        """
        raw_jobs = await self.session.execute(
            select(Job).limit(limit).offset(offset),
        )

        return raw_jobs.scalars().fetchall()

    async def get_job(
        self,
        jobid: int,
    ) -> Optional[Job]:
        """
        Get specific job model.

        :param jobid: name of job instance.
        :return: job models.
        """
        # This is the Asyncrhonous session;
        #  https://docs.sqlalchemy.org/en/14/orm/extensions/asyncio.html#sqlalchemy.ext.asyncio.AsyncSession.refresh
        return await self.session.get(Job, jobid)

    async def update_job_state(self, jobid: int, state: Job.states) -> None:
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
