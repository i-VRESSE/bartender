import asyncio
import sys
from argparse import (
    ArgumentDefaultsHelpFormatter,
    ArgumentParser,
    RawDescriptionHelpFormatter,
)
from datetime import datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from textwrap import dedent
from typing import Any, Optional

import uvicorn
from jose import jwt

from bartender.config import build_config
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
        log_level=settings.log_level,
        factory=True,
    )


def perform(config: Path, destination_names: Optional[list[str]] = None) -> None:
    """Runs arq worker to run queued jobs.

    Like a bartender performing something entertaining,
    the i-vresse bartender performs by running queued jobs.

    Args:
        config: Path to config file.
        destination_names: Name of destinations to run workers for.
            Each destination must have `scheduler.type:arq`.
            By default runs workers for all destinations with `scheduler.type:arq`.

    Raises:
        ValueError: When no valid destination is found in config file.
    """
    validated_config = build_config(config)
    configs: list[ArqSchedulerConfig] = []
    for destination_name, destination in validated_config.destinations.items():
        included = destination_names is None or destination_name in destination_names
        if isinstance(destination.scheduler, ArqSchedulerConfig) and included:
            print(  # noqa: WPS421 -- user feedback on command line
                f"Worker running for '{destination_name}' destination in {config}.",
            )
            configs.append(destination.scheduler)
    if not configs:
        raise ValueError("No valid destination found in config file.")

    asyncio.run(run_workers(configs))


def generate_token(  # noqa: WPS211 -- too many arguments
    private_key: Path,
    username: str,
    roles: list[str],
    lifetime: int,
    issuer: str,
    oformat: str,
) -> None:
    """Generate a JSON Web Token (JWT) with the given parameters.

    Args:
        private_key: Path to the private key file.
        username: The username to include in the token.
        roles: A list of roles to include in the token.
        lifetime: The lifetime of the token in minutes.
        issuer: The issuer of the token.
        oformat: The format of the token output. Can be "header" or "string".

    Returns:
        None
    """
    # TODO use scope to allow different actions
    # no scope could only be used to list applications and check health
    # scope:read could be used to read your own job
    # scope:write could be used to allow submission/deletion jobs

    # TODO allow super user to read jobs from all users
    # by allowing super user to impersonate other users
    # with act claim
    # see https://www.rfc-editor.org/rfc/rfc8693.html#name-act-actor-claim
    # https://auth0.com/docs/secure/tokens/json-web-tokens/json-web-token-claims
    # https://www.iana.org/assignments/jwt/jwt.xhtml#claims
    # alternativly a super user could also have 'super' role in roles claims

    # TODO allow job to be readable by users who is member of a group
    # use groups claims see https://www.iana.org/assignments/jwt/jwt.xhtml#claims
    # add group column job table, so on submission we store which group can read
    # the job. Add endpoints to add/remove group to/from existing job

    # TODO allow job to be readable by anonymous users aka without token
    # Used for storing example jobs or scenarios
    # User should have super role.
    # Add public boolena column to job table
    # Add endpoints to make job public or private
    # Public job should not expire
    expire = datetime.utcnow() + timedelta(minutes=lifetime)
    payload = {
        "sub": username,
        "exp": expire,
        "roles": roles,
        "iss": issuer,
    }
    private_key_body = Path(private_key).read_bytes()
    token = jwt.encode(payload, private_key_body, algorithm="RS256")
    if oformat == "header":
        print(f"Authorization: Bearer {token}")  # noqa: WPS421 -- user feedback
    else:
        print(token)  # noqa: WPS421 -- user feedback


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

    perform_sp = subparsers.add_parser("perform", help="Async Redis queue job worker")
    perform_sp.add_argument(
        "--config",
        default=Path("config.yaml"),
        type=Path,
        help="Configuration with schedulers that need arq workers",
    )
    perform_sp.add_argument(
        "--destination",
        nargs="+",
        help="""Name of destinations to run workers for.
            Each destination must have `scheduler.type:arq`.
            By default runs workers for all destinations with `scheduler.type:arq`.""",
        dest="destination_names",
    )
    perform_sp.set_defaults(func=perform)

    add_generate_token_subcommand(subparsers)

    return parser


class Formatter(RawDescriptionHelpFormatter, ArgumentDefaultsHelpFormatter):
    """Format help message for subcommands."""

    pass  # noqa: WPS420, WPS604 -- no need to implement methods


def add_generate_token_subcommand(
    subparsers: Any,
) -> None:
    """Add generate-token subcommand to parser.

    Args:
        subparsers: Subparsers to add generate-token subcommand to.
    """
    generate_token_sp = subparsers.add_parser(
        "generate-token",
        formatter_class=Formatter,
        description=dedent(  # noqa: WPS462 -- docs
            """\
            Generate token.

            Token is required to consume the protected endpoints.

            Example:
                ```shell
                # Generate a rsa key pair
                openssl genpkey -algorithm RSA -out private_key.pem \\
                    -pkeyopt rsa_keygen_bits:2048
                openssl rsa -pubout -in private_key.pem -out public_key.pem
                # Generate token
                bartender generate-token --format header > token.txt
                # Use token
                curl -X 'GET' \\
                    'http://127.0.0.1:8000/api/whoami' \\
                    -H 'accept: application/json' \\
                    -H @token.txt | jq .
                ```
        """,
        ),
        help="Generate token.",
    )
    generate_token_sp.add_argument(
        "--private-key",
        default=Path("private_key.pem"),
        type=Path,
        help="Path to RSA private key file",
    )
    generate_token_sp.add_argument(
        "--username",
        default="someone",
        help="Username to use in token",
    )
    generate_token_sp.add_argument(
        "--roles",
        nargs="+",
        default=["expert", "guru"],
        help="Roles to use in token",
    )
    onehour_in_minutes = 60
    generate_token_sp.add_argument(
        "--lifetime",
        default=onehour_in_minutes,
        type=int,
        help="Lifetime of token in minutes",
    )
    generate_token_sp.add_argument(
        "--issuer",
        default="bartendercli",
        help="Issuer of token",
    )
    generate_token_sp.add_argument(
        "--oformat",
        default="plain",
        choices=["header", "plain"],
        help="Format of output",
    )
    generate_token_sp.set_defaults(func=generate_token)


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
