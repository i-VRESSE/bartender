"""
Parses config file into a list of applications, schedulers and filesystems.

Example config:

.. code-block: yaml

    applications:
    haddock3:
        command: haddock3 $config
    recluster:
        command: haddock3 recluster
    destinations:
    cluster1:
        filesystem: &cluster1fs
            type: sftp
            hostname: localhost
            port: 10022
            username: xenon
            password: javagat
            entry: /home/xenon
        scheduler: &cluster1sched
            type: slurm
            partition: mypartition
            time: '60' # max time is 60 minutes
            extra_options:
            - --nodes 1
            runner:
            type: ssh  # or local
            hostname: localhost
            port: 10022
            username: xenon
            password: javagat
        local:
            scheduler:
                type: memory
                slots: 4
        cluster2: # bartender is being run on head node of cluster
            scheduler:
                type: slurm
        cluster3: # show of reuse using yaml anchor and aliases
            scheduler:
                <<: *cluster1sched
                parition: otherpartition
            filesystem: *cluster1fs
        grid:
            scheduler:
                type: grid
            filesystem:
                type: dirac
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import Request
from yaml import safe_load as load_yaml

from bartender.destinations import Destination
from bartender.destinations import build as build_destinations


@dataclass
class ApplicatonConfiguration:
    """Command to run application.

    `$config` in command string will be replaced
    with value of ApplicatonConfiguration.config.
    """

    command: str
    config: str


@dataclass
class Config:
    """Bartender configuration.

    The bartender.settings.Settings class is for FastAPI settings.
    The bartender.config.Config class is for non-FastAPI configuration.
    """

    applications: dict[str, ApplicatonConfiguration]
    destinations: dict[str, Destination]


def build_config(config_filename: Path) -> Config:
    """Build a config instance from a yaml formatted file.

    :param config_filename: File name of configuration file.
    :return: A config instance.
    """
    config = _load(config_filename)
    return parse_config(config)


def parse_config(config: Any) -> Config:
    """Parses a plain configuration dict to a config instance.

    :param config: A plain configuration dict
    :return: A config instance.
    """
    return Config(
        applications=_build_applications(config["applications"]),
        destinations=build_destinations(config["destinations"]),
    )


def _load(config_filename: Path) -> Any:
    with open(config_filename) as handle:
        return load_yaml(handle)


def _build_applications(config: Any) -> dict[str, ApplicatonConfiguration]:
    applications = {}
    for name, setting in config.items():
        applications[name] = ApplicatonConfiguration(**setting)
    return applications


def get_config(request: Request) -> Config:
    """Get config based on current request.

    :param request: The current FastAPI request.
    :return: The config.
    """
    return request.app.state.config
