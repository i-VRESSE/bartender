import contextlib
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Dict, Generator, TypedDict, cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Mapped
from starlette import status
from testcontainers.redis import RedisContainer

from bartender.config import ApplicatonConfiguration, Config, get_config
from bartender.context import Context, get_context
from bartender.db.base import Base
from bartender.db.dao.user_dao import get_user_db
from bartender.db.dependencies import get_db_session
from bartender.db.models.user import User
from bartender.db.utils import create_database, drop_database
from bartender.destinations import Destination, DestinationConfig
from bartender.filesystems.local import LocalFileSystem, LocalFileSystemConfig
from bartender.filesystems.queue import (
    FileStagingQueue,
    build_file_staging_queue,
    get_file_staging_queue,
    stop_file_staging_queue,
)
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
    await create_database()

    engine = create_async_engine(str(settings.db_url))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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

    Args:
        _engine: current engine.

    Yields:
        async session.
    """
    connection = await _engine.connect()
    trans = await connection.begin()

    session_maker = async_sessionmaker(
        connection,
        expire_on_commit=False,
    )
    async with session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()
            await connection.close()


@pytest.fixture
def session_maker(dbsession: AsyncSession) -> Callable[[], AsyncSession]:
    """Get session maker.

    Fixture that returns a SQLAlchemy session with a SAVEPOINT, and the rollback to it
    after the test completes.

    Args:
        dbsession: async session.

    Returns:
        session maker
    """
    # use same session everywhere so sqlalchemy does not get confused.
    return lambda: dbsession


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
            allowed_roles=[],
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
async def demo_file_staging_queue(
    demo_config: Config,
    demo_context: Context,
    session_maker: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[FileStagingQueue, None]:
    queue, task = build_file_staging_queue(
        demo_config.job_root_dir,
        demo_context.destinations,
        session_maker,
    )
    yield queue
    await stop_file_staging_queue(task)


@pytest.fixture
async def fastapi_app(
    dbsession: AsyncSession,
    demo_config: Config,
    demo_context: Context,
    demo_file_staging_queue: FileStagingQueue,
) -> FastAPI:
    """Fixture for creating FastAPI app.

    Returns:
        fastapi app with mocked dependencies.
    """
    application = get_app()
    application.dependency_overrides[get_db_session] = lambda: dbsession
    application.dependency_overrides[get_config] = lambda: demo_config
    application.dependency_overrides[get_context] = lambda: demo_context
    application.dependency_overrides[
        get_file_staging_queue
    ] = lambda: demo_file_staging_queue
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


async def new_user(
    email: str,
    password: str,
    fastapi_app: FastAPI,
    client: AsyncClient,
) -> Any:
    new_user = {"email": email, "password": password}
    register_url = fastapi_app.url_path_for("register:register")
    return await client.post(register_url, json=new_user)


MockUser = TypedDict("MockUser", {"id": str, "email": str, "password": str})


@pytest.fixture
async def current_user_model(fastapi_app: FastAPI, client: AsyncClient) -> MockUser:
    email = "me@example.com"
    password = "mysupersecretpassword"  # noqa: S105 needed for tests
    response = await new_user(email, password, fastapi_app, client)
    body = response.json()
    body["password"] = password
    return body


@pytest.fixture
def current_user_id(current_user_model: MockUser) -> str:
    return current_user_model["id"]


async def new_user_token(
    email: str,
    password: str,
    fastapi_app: FastAPI,
    client: AsyncClient,
) -> str:
    await new_user(email, password, fastapi_app, client)
    login_url = fastapi_app.url_path_for("auth:local.login")
    login_response = await client.post(
        login_url,
        data={
            "grant_type": "password",
            "username": email,
            "password": password,
        },
    )
    return login_response.json()["access_token"]


@pytest.fixture
async def current_user_token(
    fastapi_app: FastAPI,
    client: AsyncClient,
    current_user_model: MockUser,
) -> str:
    """Registers dummy user and returns its auth token.

    :return: token
    """
    return await new_user_token(
        current_user_model["email"],
        current_user_model["password"],
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
async def current_user(dbsession: AsyncSession, current_user_token: str) -> User:
    # User.email is typed as str in fastapi-user package, which confuses mypy,
    # cast it to correct type
    user_column = cast(Mapped[str], User.email)
    query = select(User).where(user_column == "me@example.com")
    result = await dbsession.execute(query)
    return result.unique().scalar_one()


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


@pytest.fixture
async def current_user_is_super(dbsession: AsyncSession, current_user_id: str) -> None:
    # First user can not become super user by calling routes,
    # Must make user user super by talking to db directly.
    get_user_db_context = contextlib.asynccontextmanager(get_user_db)
    async with get_user_db_context(dbsession) as user_db:
        user = await user_db.get(UUID(current_user_id))
        if user is None:
            raise ValueError(f"User with {current_user_id} id not found")
        await user_db.give_super_powers(user)


@pytest.fixture
def app_with_roles(
    fastapi_app: FastAPI,
    demo_applications: dict[str, ApplicatonConfiguration],
) -> FastAPI:
    demo_applications["app1"].allowed_roles = ["role1"]
    return fastapi_app


@pytest.fixture
async def current_user_with_role(
    app_with_roles: FastAPI,
    current_user_is_super: None,
    current_user_id: str,
    auth_headers: Dict[str, str],
    client: AsyncClient,
) -> None:
    url = app_with_roles.url_path_for(
        "assign_role_to_user",
        role_id="role1",
        user_id=current_user_id,
    )
    response = await client.put(url, headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == ["role1"]
