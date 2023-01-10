from datetime import datetime

from pydantic import BaseModel

from bartender.db.models.job_model import State

# DTO = Data Transfer Object


class JobModelDTO(BaseModel):
    """
    DTO for job models.

    It returned when accessing job models from the API.
    """

    id: int
    name: str
    application: str
    state: State
    created_on: datetime
    updated_on: datetime

    class Config:
        orm_mode = True


class JobModelInputDTO(BaseModel):
    """DTO for creating new job model."""

    name: str
