import asyncio
import contextlib
import sys
from argparse import ArgumentParser
from importlib.metadata import version

import uvicorn

from bartender.db.dao.user_dao import get_user_db
from bartender.db.session import make_engine, make_session_factory
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

    :param email: Email of user
    :raises ValueError: When user can not be found
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

    :param email: Email of user
    """
    asyncio.run(make_super_async(email))


def build_parser() -> ArgumentParser:
    """Build an argument parser.

    :return: parser
    """
    parser = ArgumentParser(prog="bartender")
    parser.add_argument("--version", action="version", version=version("bartender"))
    subparsers = parser.add_subparsers(dest="subcommand")

    serve_sp = subparsers.add_parser("serve", help="Serve web service")
    serve_sp.set_defaults(func=serve)

    super_sp = subparsers.add_parser("super", help="Grant super rights to user")
    super_sp.add_argument("email", help="Email address of logged in user")
    super_sp.set_defaults(func=make_super)

    return parser


def main(argv: list[str] = sys.argv[1:]) -> None:
    """Entrypoint of the application.

    :param argv: Arguments to parse
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
