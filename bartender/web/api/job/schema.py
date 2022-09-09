from enum import Enum

from pydantic import BaseModel

from bartender.settings import settings

# DTO = Data Transfer Object


class JobModelDTO(BaseModel):
    """
    DTO for job models.

    It returned when accessing job models from the API.
    """

    id: int
    name: str

    class Config:
        orm_mode = True


class JobModelInputDTO(BaseModel):
    """DTO for creating new job model."""

    name: str


# Works for FastAPI, but not for mypy as dict must be literal so ignore type
ApplicationName = Enum(  # type: ignore
    "ApplicationName",
    {app_name: app_name for app_name in settings.applications.keys()},
    module=__name__,
    type=str,
)
