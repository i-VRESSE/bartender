from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Dict, Generator

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from rsa.key import PrivateKey, PublicKey
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.redis import RedisContainer

from bartender.config import ApplicatonConfiguration, Config, get_config
from bartender.context import Context, get_context
from bartender.db.base import Base
from bartender.db.dependencies import get_db_session
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
from bartender.user import JwtDecoder, User, generate_token
from bartender.web.application import get_app
from bartender.web.users import get_jwt_decoder


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
def rsa_private_key() -> bytes:
    # Generating key pair takes a long time, so we use a pre-generated one.
    return PrivateKey(
        16527233807183266269587235774365684740774442848897320223621644242162708075059004841994812461818551827813820028470541786594824951798924962833196937230332653347198242638972401822735075360903329143434122437254590842505520000637777584258863217840733503759046884365443875217172374074672632511614003376644212446501060173045618568392384402659352797171568914979982599935263980121157653531287731867867326624158720037621597557065975115568717924320256636245212365326666346692788428023844882564782417147188015148534865863136348561301497209141595301187823693513544644608177477609585687544044700889309819613155368700909410083294879,  # noqa: E501
        65537,
        16036992530939857666384806820562994792560983018599070524753516674425944041033725909287518636562966971118059372118454671939892017635061647030707735009056630976522847309766573830251486144100666954825612221376187427673734430940662372641010247831694549713124929695464735289769790874325292877471773224196003464927888430829809896707363739035492071190604807795076177158622133953913251698586467753318006753650104814965278886101243804987384744165994550506467931731657793604361723532290798162824052964643382452657694969218202591179563541368032631796737297278407443583396564933401588994826686823168536008646497707732114719774753,  # noqa: E501
        3171967619107811069817361866821354854560605851348765969643669560644751648434285601101280062817063639695049513708445583547887807170050138218912545320896949050175144991491657826856804357927098073351793115431246799523325080335397219305826816519226967228208697717903201527652952239459621368951904879478366851746631123668687306758641,  # noqa: E501
        5210404326836076382067892473139554034909041503501665437923474045215820466047899918700828184145139200036788456268704594084460724877064607773425827543403046979191340362536974491902533344983810692931792294710343456528614405630142620960411772083200797551925562926976727904019758115353594552719,  # noqa: E501
    ).save_pkcs1()


@pytest.fixture
def rsa_publc_key() -> bytes:
    return PublicKey(
        16527233807183266269587235774365684740774442848897320223621644242162708075059004841994812461818551827813820028470541786594824951798924962833196937230332653347198242638972401822735075360903329143434122437254590842505520000637777584258863217840733503759046884365443875217172374074672632511614003376644212446501060173045618568392384402659352797171568914979982599935263980121157653531287731867867326624158720037621597557065975115568717924320256636245212365326666346692788428023844882564782417147188015148534865863136348561301497209141595301187823693513544644608177477609585687544044700889309819613155368700909410083294879,  # noqa: E501
        65537,
    ).save_pkcs1()


@pytest.fixture
def demo_jwt_decoder(rsa_publc_key: bytes) -> JwtDecoder:
    return JwtDecoder.from_bytes(rsa_publc_key)


@pytest.fixture
async def fastapi_app(
    dbsession: AsyncSession,
    demo_config: Config,
    demo_context: Context,
    demo_file_staging_queue: FileStagingQueue,
    demo_jwt_decoder: JwtDecoder,
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
    application.dependency_overrides[get_jwt_decoder] = lambda: demo_jwt_decoder
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


def generate_test_token(rsa_private_key: bytes, username: str, roles: list[str]) -> str:
    # Expire long enough in the future so it does not expire during tests.
    expire = datetime.utcnow() + timedelta(days=1)
    return generate_token(
        private_key=rsa_private_key,
        username=username,
        roles=roles,
        issuer="pytest",
        expire=expire,
    )


@pytest.fixture
def current_user_token(rsa_private_key: bytes) -> str:
    return generate_test_token(rsa_private_key, "me@example.com", ["role1"])


@pytest.fixture
async def second_user_token(rsa_private_key: bytes) -> str:
    return generate_test_token(rsa_private_key, "user@example.com", [])


@pytest.fixture
def auth_headers(current_user_token: str) -> Dict[str, str]:
    """Headers for AsyncClient to do authenticated requests.

    Returns:
        Headers needed for auth.
    """
    return {"Authorization": f"Bearer {current_user_token}"}


@pytest.fixture
def current_user(current_user_token: str) -> User:
    return User(
        username="me@example.com",
        roles=["role1"],
        apikey=current_user_token,
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
def app_with_roles(
    fastapi_app: FastAPI,
    demo_applications: dict[str, ApplicatonConfiguration],
) -> FastAPI:
    demo_applications["app1"].allowed_roles = ["role1"]
    return fastapi_app
