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
            ssh_config:
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
            ssh_config:
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
from importlib import import_module
from pathlib import Path
from string import Template
from tempfile import gettempdir
from typing import Any, Callable, Optional

from fastapi import Request
from yaml import safe_load as load_yaml

from bartender.destinations import Destination
from bartender.destinations import build as build_destinations
from bartender.schedulers.abstract import JobDescription

DEFAULT_JOB_ROOT_DIR = Path(gettempdir()) / "jobs"


@dataclass
class ApplicatonConfiguration:
    """Command to run application.

    `$config` in command string will be replaced
    with value of ApplicatonConfiguration.config.
    """

    command: str
    config: str

    def description(self, job_dir: Path) -> JobDescription:
        """Construct job description for this application.

        :param job_dir: In which directory are the input files.
        :return: A job description.
        """
        command = Template(self.command).substitute(
            config=self.config,
        )
        return JobDescription(job_dir=job_dir, command=command)


DestinationPicker = Callable[[Path, str, "Config"], tuple[Destination, str]]


# TODO move to own module, without causing a circular import
def pick_first(
    job_dir: Path,
    application_name: str,
    config: "Config",
) -> tuple[Destination, str]:
    """Pick to which destination a job should be submitted.

    :param job_dir: Location where job input files are located.
    :param application_name: Application name that should be run.
    :param config: Config with applications and destinations.
    :return: Destination where job should be submitted to.
    """
    destination_names = list(config.destinations.keys())
    destination_name = destination_names[0]
    destination = config.destinations[destination_name]
    return destination, destination_name


DEFAULT_DESTINATION_PICKER: DestinationPicker = pick_first


def import_picker(destination_picker_name: Optional[str]) -> DestinationPicker:
    """Import a picker function based on a `<module>:<function>` string.

    :param destination_picker_name: function import as string.
    :return: Function that can be used to pick to
        which destination a job should be submitted.
    """
    if destination_picker_name is None:
        return DEFAULT_DESTINATION_PICKER
    # TODO allow somedir/somefile.py:pick_round_robin
    (module_name, function_name) = destination_picker_name.split(":")
    module = import_module(module_name)
    return getattr(module, function_name)


@dataclass
class Config:
    """Bartender configuration.

    The bartender.settings.Settings class is for FastAPI settings.
    The bartender.config.Config class is for non-FastAPI configuration.
    """

    applications: dict[str, ApplicatonConfiguration]
    destinations: dict[str, Destination]
    job_root_dir: Path = DEFAULT_JOB_ROOT_DIR
    destination_picker: DestinationPicker = DEFAULT_DESTINATION_PICKER


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
    destination_picker_fn = import_picker(config.get("destination_picker"))
    return Config(
        applications=_build_applications(config["applications"]),
        destinations=build_destinations(config["destinations"]),
        job_root_dir=config.get("job_root_dir", DEFAULT_JOB_ROOT_DIR),
        destination_picker=destination_picker_fn,
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
