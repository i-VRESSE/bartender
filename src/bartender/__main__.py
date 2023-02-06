import asyncio
import contextlib
import sys
from argparse import ArgumentParser
from importlib.metadata import version
from pathlib import Path

import uvicorn

from bartender.config import build_config
from bartender.db.dao.user_dao import get_user_db
from bartender.db.session import make_engine, make_session_factory
from bartender.schedulers.arq import ArqSchedulerConfig, run_workers
from bartender.settings import settings


def serve() -> None:
    """Serve the web servce."""
    uvicorn.run(
        "bartender.web.application:get_app",
        workers=settings.workers_count,
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level.value.lower(),
        factory=True,
    )


async def make_super_async(email: str) -> None:
    """Async method to grant a user super rights.

    Args:
        email: Email of user

    Raises:
        ValueError: When user can not be found
    """
    session_factory = make_session_factory(make_engine())
    get_user_db_context = contextlib.asynccontextmanager(get_user_db)
    async with session_factory() as session:
        async with get_user_db_context(session) as user_db:
            user = await user_db.get_by_email(email)
            if user is None:
                raise ValueError(f"User with {email} not found")
            await user_db.update(user, {"is_superuser": True})
            print(  # noqa: WPS421 -- user feedback on command line
                f"User with {email} is now super user",
            )


def make_super(email: str) -> None:
    """Grant a user super rights.

    Args:
        email: Email of user
    """
    asyncio.run(make_super_async(email))


def mix(config: Path) -> None:
    """Runs arq worker to run queued jobs.

    Like a bartender mixes the cocktails,
    the i-vresse bartender mixes aka runs queued jobs.

    Args:
        config: Path to config file.

    Raises:
        ValueError: When no useful destination found in config file.
    """
    validated_config = build_config(config)
    configs: list[ArqSchedulerConfig] = []
    for destination in validated_config.destinations.values():
        if isinstance(destination.scheduler, ArqSchedulerConfig):
            configs.append(destination.scheduler)
    if not configs:
        raise ValueError("No destination found in config file using arq scheduler")

    asyncio.run(run_workers(configs))


def build_parser() -> ArgumentParser:
    """Build an argument parser.

    Returns:
        parser
    """
    parser = ArgumentParser(prog="bartender")
    parser.add_argument("--version", action="version", version=version("bartender"))
    subparsers = parser.add_subparsers(dest="subcommand")

    serve_sp = subparsers.add_parser("serve", help="Serve web service")
    serve_sp.set_defaults(func=serve)

    super_sp = subparsers.add_parser("super", help="Grant super rights to user")
    super_sp.add_argument("email", help="Email address of logged in user")
    super_sp.set_defaults(func=make_super)

    mix_sp = subparsers.add_parser("mix", help="Async Redis queue job worker")
    mix_sp.add_argument(
        "--config",
        default=Path("config.yaml"),
        type=Path,
        help="Configuration with schedulers that need arq workers",
    )
    mix_sp.set_defaults(func=mix)

    return parser


def main(argv: list[str] = sys.argv[1:]) -> None:
    """Entrypoint of the application.

    Args:
        argv: Arguments to parse
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    fargs = args.__dict__
    if "func" in fargs:
        func = args.func
        fargs.pop("subcommand")
        fargs.pop("func")
        func(**fargs)
    else:
        if "subcommand" in args:
            parser.parse_args([args.subcommand, "--help"])
        else:
            parser.print_help()


if __name__ == "__main__":
    main()
