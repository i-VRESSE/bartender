import asyncio
import sys
from argparse import (
    ArgumentDefaultsHelpFormatter,
    ArgumentParser,
    RawDescriptionHelpFormatter,
)
from importlib.metadata import version
from pathlib import Path
from textwrap import dedent
from typing import Any, Optional

import uvicorn

from bartender.config import build_config
from bartender.schedulers.arq import ArqSchedulerConfig, run_workers
from bartender.settings import settings
from bartender.user import generate_token_subcommand


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
        default=[],
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
    generate_token_sp.set_defaults(func=generate_token_subcommand)


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
