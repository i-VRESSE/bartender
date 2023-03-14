from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Generator

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.redis import RedisContainer

from bartender.config import ApplicatonConfiguration, Config, get_config
from bartender.context import Context, get_context
from bartender.db.dependencies import get_db_session
from bartender.db.utils import create_database, drop_database
from bartender.destinations import Destination, DestinationConfig
from bartender.filesystems.local import LocalFileSystem, LocalFileSystemConfig
from bartender.picker import pick_first
from bartender.schedulers.memory import MemoryScheduler, MemorySchedulerConfig
from bartender.settings import settings
from bartender.web.application import get_app


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Backend for anyio pytest plugin.

    Returns:
        backend name.
    """
    return "asyncio"


@pytest.fixture(scope="session")
async def _engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create engine and databases.

    Yields:
        new engine.
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
    """Get session to database.

    Fixture that returns a SQLAlchemy session with a SAVEPOINT, and the rollback to it
    after the test completes.

    Args:
        _engine: current engine.

    Yields:
        async session.
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
def job_root_dir(tmp_path: Path) -> Path:
    root = tmp_path / "jobs"
    root.mkdir()
    return root


@pytest.fixture
def demo_applications() -> dict[str, ApplicatonConfiguration]:
    return {
        "app1": ApplicatonConfiguration(
            command="wc $config",
            config="job.ini",
        ),
    }


@pytest.fixture
async def demo_destination() -> AsyncGenerator[Destination, None]:
    destination = Destination(
        scheduler=MemoryScheduler(MemorySchedulerConfig()),
        filesystem=LocalFileSystem(),
    )
    yield destination
    await destination.close()


@pytest.fixture
async def demo_destinations(demo_destination: Destination) -> dict[str, Destination]:
    return {"dest1": demo_destination}


@pytest.fixture
def demo_config(
    job_root_dir: Path,
    demo_applications: dict[str, ApplicatonConfiguration],
) -> Config:
    return Config(
        applications=demo_applications,
        job_root_dir=job_root_dir,
        destinations={
            "dest1": DestinationConfig(
                scheduler=MemorySchedulerConfig(),
                filesystem=LocalFileSystemConfig(),
            ),
        },
    )


@pytest.fixture
def demo_context(
    job_root_dir: Path,
    demo_applications: dict[str, ApplicatonConfiguration],
    demo_destinations: dict[str, Destination],
) -> Context:
    return Context(
        destination_picker=pick_first,
        job_root_dir=job_root_dir,
        applications=demo_applications,
        destinations=demo_destinations,
    )


@pytest.fixture
def fastapi_app(
    dbsession: AsyncSession,
    demo_config: Config,
    demo_context: Context,
) -> FastAPI:
    """Fixture for creating FastAPI app.

    Returns:
        fastapi app with mocked dependencies.
    """
    application = get_app()
    application.dependency_overrides[get_db_session] = lambda: dbsession
    application.dependency_overrides[get_config] = lambda: demo_config
    application.dependency_overrides[get_context] = lambda: demo_context
    settings.secret = "testsecret"  # noqa: S105
    return application


@pytest.fixture
async def client(
    fastapi_app: FastAPI,
    anyio_backend: Any,
) -> AsyncGenerator[AsyncClient, None]:
    """Fixture that creates client for requesting server.

    Args:
        fastapi_app: the application.

    Yields:
        client for the app.
    """
    async with AsyncClient(app=fastapi_app, base_url="http://test") as ac:
        yield ac


async def new_user_token(
    email: str,
    password: str,
    fastapi_app: FastAPI,
    client: AsyncClient,
) -> str:
    new_user = {"email": email, "password": password}
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
async def current_user_token(fastapi_app: FastAPI, client: AsyncClient) -> str:
    """Registers dummy user and returns its auth token.

    :return: token
    """
    return await new_user_token(
        "me@example.com",
        "mysupersecretpassword",
        fastapi_app,
        client,
    )


@pytest.fixture
def auth_headers(current_user_token: str) -> Dict[str, str]:
    """Headers for AsyncClient to do authenticated requests.

    Returns:
        Headers needed for auth.
    """
    return {"Authorization": f"Bearer {current_user_token}"}


@pytest.fixture
async def second_user_token(fastapi_app: FastAPI, client: AsyncClient) -> str:
    """Registers second dummy user and returns its auth token.

    :return: token
    """
    return await new_user_token(
        "user2@example.com",
        "mysupersecretpassword2",
        fastapi_app,
        client,
    )


@pytest.fixture
def redis_server() -> Generator[RedisContainer, None, None]:
    with RedisContainer("redis:7") as container:
        yield container


@pytest.fixture
def redis_dsn(redis_server: RedisContainer) -> str:
    host = redis_server.get_container_host_ip()
    port = redis_server.get_exposed_port(redis_server.port_to_expose)
    return f"redis://{host}:{port}/0"
