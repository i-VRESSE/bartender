"""
Parses config file into a list of applications, schedulers and filesystems.

Example config:

.. code-block: yaml

    applications:
        haddock3:
            command: haddock3 $config
            config: workflow.cfg
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

from pathlib import Path
from string import Template
from tempfile import gettempdir
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dataclasses import dataclass
else:
    from pydantic.dataclasses import dataclass  # noqa: WPS440

from fastapi import Request
from pydantic import Field, validator
from pydantic.types import DirectoryPath
from yaml import safe_load as load_yaml

from bartender.destinations import DestinationConfig, default_destinations
from bartender.schedulers.abstract import JobDescription


@dataclass
class ApplicatonConfiguration:
    """Command to run application.

    `$config` in command string will be replaced
    with value of ApplicatonConfiguration.config.

    .. code-block:: yaml

        command: wc $config
        config: README.md
    """

    command: str
    config: str
    # TODO make config optional,
    # as some commands don't need a config file name as argument

    def description(self, job_dir: Path) -> JobDescription:
        """Construct job description for this application.

        :param job_dir: In which directory are the input files.
        :return: A job description.
        """
        command = Template(self.command).substitute(
            config=self.config,
        )
        return JobDescription(job_dir=job_dir, command=command)


@dataclass
class Config:
    """Bartender configuration.

    The bartender.settings.Settings class is for FastAPI settings.
    The bartender.config.Config class is for non-FastAPI configuration.

    If config is empty will create a single slot in memory scheduler
    with a local file system.

    """

    applications: dict[str, ApplicatonConfiguration]
    destinations: dict[str, DestinationConfig] = Field(
        default_factory=default_destinations,
    )
    job_root_dir: DirectoryPath = Path(gettempdir()) / "jobs"
    destination_picker: str = "bartender.picker:pick_first"

    @validator("applications")
    def applications_non_empty(
        cls,  # noqa: N805 following pydantic docs
        v: dict[str, ApplicatonConfiguration],  # noqa: WPS111 following pydantic docs
    ) -> dict[str, ApplicatonConfiguration]:
        """Validates that applications dict is filled.

        :param v: The given dict.
        :raises ValueError: When dict is empty.
        :returns: The given dict.
        """
        if not v:
            raise ValueError("must contain a at least one application")
        return v

    # TODO validate destination_picker
    # check string format
    # optionally check if it can be imported


def build_config(config_filename: Path) -> Config:
    """Build a config instance from a yaml formatted file.

    :param config_filename: File name of configuration file.
    :return: A config instance.
    """
    raw_config = _load(config_filename)
    return Config(**raw_config)


def _load(config_filename: Path) -> Any:
    with open(config_filename) as handle:
        return load_yaml(handle)


def get_config(request: Request) -> Config:
    """Get config based on current request.

    :param request: The current FastAPI request.
    :return: The config.
    """
    return request.app.state.config
