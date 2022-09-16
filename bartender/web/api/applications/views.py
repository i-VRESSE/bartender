from fastapi import APIRouter

from bartender.settings import settings

router = APIRouter()


@router.get("/", response_model=list[str])
def list_applications() -> list[str]:
    """List application names.

    :return: The list.
    """
    return list(settings.applications.keys())
