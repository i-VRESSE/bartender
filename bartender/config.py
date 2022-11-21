"""
Parses config file into a list of applications, schedulers and filesystems.

Example config:
```yaml
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
```
"""

from pathlib import Path
from typing import Any

from yaml import safe_load

from bartender.destinations import build as build_destinations
from bartender.settings import AppSetting

def build(config_filename: Path):
    config = load(config_filename)
    return parse(config)

def parse(config: Any):
    return {
        'applications': build_applications(config['applications']),
        'destinations': build_destinations(config['destinations'])
    }

def load(config_filename: Path) -> Any:
    with open(config_filename) as f:
        return safe_load(f)

def build_applications(config: Any) -> dict[str, AppSetting]:
    applications = {}
    for name, config in config.items():
        applications[name] = AppSetting(**config)
    return applications
