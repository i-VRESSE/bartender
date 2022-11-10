from pathlib import Path
from typing import Any, AsyncGenerator, Dict

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from bartender.db.dependencies import get_db_session
from bartender.db.utils import create_database, drop_database
from bartender.schedulers.abstract import AbstractScheduler
from bartender.schedulers.memory import MemoryScheduler
from bartender.settings import AppSetting, settings
from bartender.web.application import get_app
from bartender.web.lifetime import get_scheduler


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """
    Backend for anyio pytest plugin.

    :return: backend name.
    """
    return "asyncio"


@pytest.fixture(scope="session")
async def _engine() -> AsyncGenerator[AsyncEngine, None]:
    """
    Create engine and databases.

    :yield: new engine.
    """
    from bartender.db.meta import meta  # noqa: WPS433
    from bartender.db.models import load_all_models  # noqa: WPS433

    load_all_models()

    await create_database()

    engine = create_async_engine(str(settings.db_url))
    async with engine.begin() as conn:
        await conn.run_sync(meta.create_all)

    try:
        yield engine
    finally:
        await engine.dispose()
        await drop_database()


@pytest.fixture
async def dbsession(
    _engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Get session to database.

    Fixture that returns a SQLAlchemy session with a SAVEPOINT, and the rollback to it
    after the test completes.

    :param _engine: current engine.
    :yields: async session.
    """
    connection = await _engine.connect()
    trans = await connection.begin()

    session_maker = sessionmaker(
        connection,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    session = session_maker()

    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()
        await connection.close()


@pytest.fixture
async def scheduler() -> AsyncGenerator[AbstractScheduler, None]:
    my_scheduler = MemoryScheduler()
    try:
        yield my_scheduler
    finally:
        await my_scheduler.close()


@pytest.fixture
def fastapi_app(
    dbsession: AsyncSession,
    scheduler: AbstractScheduler,
) -> FastAPI:
    """
    Fixture for creating FastAPI app.

    :return: fastapi app with mocked dependencies.
    """
    application = get_app()
    application.dependency_overrides[get_db_session] = lambda: dbsession
    application.dependency_overrides[get_scheduler] = lambda: scheduler
    settings.secret = "testsecret"  # noqa: S105
    settings.applications = {
        "app1": AppSetting(
            command="wc $config",
            config="job.ini",
        ),
    }
    return application  # noqa: WPS331


@pytest.fixture
async def client(
    fastapi_app: FastAPI,
    anyio_backend: Any,
) -> AsyncGenerator[AsyncClient, None]:
    """
    Fixture that creates client for requesting server.

    :param fastapi_app: the application.
    :yield: client for the app.
    """
    async with AsyncClient(app=fastapi_app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def job_root_dir(tmp_path: Path) -> Path:
    """
    Fixture that overrides settings.job_root_dir with temporary test directory.

    :return: Path of job root dir.
    """
    settings.job_root_dir = tmp_path
    return settings.job_root_dir


@pytest.fixture
async def current_user_token(fastapi_app: FastAPI, client: AsyncClient) -> str:
    """Registers dummy user and returns its auth token.

    :return: token
    """
    new_user = {"email": "me@example.com", "password": "mysupersecretpassword"}
    register_url = fastapi_app.url_path_for("register:register")
    await client.post(register_url, json=new_user)

    login_url = fastapi_app.url_path_for("auth:local.login")
    login_response = await client.post(
        login_url,
        data={
            "grant_type": "password",
            "username": new_user["email"],
            "password": new_user["password"],
        },
    )
    return login_response.json()["access_token"]


@pytest.fixture
async def auth_headers(current_user_token: str) -> Dict[str, str]:
    """Headers for AsyncClient to do authenticated requests.

    :return: Headers needed for auth.
    """
    return {"Authorization": f"Bearer {current_user_token}"}
