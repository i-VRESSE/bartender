import enum
import logging
from pathlib import Path
from tempfile import gettempdir

from pydantic import BaseSettings, Field
from pydantic.types import FilePath
from yarl import URL

logger = logging.getLogger(__name__)

TEMP_DIR = Path(gettempdir())


class LogLevel(str, enum.Enum):  # noqa: WPS600
    """Possible log levels."""

    NOTSET = "NOTSET"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    FATAL = "FATAL"


def default_config_filename() -> Path:
    """The default configuration filename.

    Depends on whether default or fallback files exist.

    Returns:
        Default file name for configuration file.
    """
    default = Path("config.yaml")
    fallback = Path("config-example.yaml")
    if not default.exists() and fallback.exists():
        logger.warn(f"Unable to find {default} falling back to {fallback}")
        return fallback
    return default


class Settings(BaseSettings):
    """Application settings.

    These parameters can be configured
    with environment variables.
    """

    host: str = "127.0.0.1"
    port: int = 8000
    # quantity of workers for uvicorn
    workers_count: int = 1
    # Enable uvicorn reloading
    reload: bool = False

    # Current environment
    environment: str = "dev"

    log_level: LogLevel = LogLevel.INFO

    # Variables for the database
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "bartender"
    db_pass: str = "bartender"
    db_base: str = "bartender"
    db_echo: bool = False

    # User auth
    secret: str = "SECRET"  # TODO should not have default when running in production

    # Social OAuth logins
    # must set to non '' to have GitHub social login enabled
    github_client_id: str = ""
    github_client_secret: str = ""
    orcidsandbox_client_id: str = ""
    orcidsandbox_client_secret: str = ""
    orcid_client_id: str = ""
    orcid_client_secret: str = ""

    # Settings for configuration
    config_filename: FilePath = Field(default_factory=default_config_filename)

    @property
    def db_url(self) -> URL:
        """Assemble database URL from settings.

        Returns:
            database URL.
        """
        return URL.build(
            scheme="postgresql+asyncpg",
            host=self.db_host,
            port=self.db_port,
            user=self.db_user,
            password=self.db_pass,
            path=f"/{self.db_base}",
        )

    class Config:
        env_file = ".env"
        env_prefix = "BARTENDER_"
        env_file_encoding = "utf-8"


settings = Settings()
