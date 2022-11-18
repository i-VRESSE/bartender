from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yaml import safe_load

from bartender.schedulers.memory import MemoryScheduler
from bartender.schedulers.runner import LocalCommandRunner, SshCommandRunner
from bartender.schedulers.slurm import SlurmScheduler


def build(config_filename: Path):
    config = load(config_filename)
    return assemble(config)


def load(config_filename: Path):
    with open(config_filename) as f:
        return safe_load(f)


def assemble(config: Any):
    if "schedulers" not in config:
        raise ValueError("No schedulers found")
    if len(config["schedulers"]) == 0:
        raise ValueError("No schedulers found")
    schedulers = {}
    for scheduler_name, scheduler_config in config["schedulers"].items():
        schedulers[scheduler_name] = assemble_scheduler(scheduler_config)
    return schedulers


def assemble_scheduler(config: Any):
    if "type" not in config:
        raise ValueError("Scheduler without type")
    if config["type"] == "memory":
        if "slots" in config:
            return MemoryScheduler(config["slots"])
        return MemoryScheduler()
    if config["type"] == "slurm":
        slurm_config = {k: v for k, v in config.items() if k not in {"type", "runner"}}
        if "runner" in config:
            if "type" not in config["runner"]:
                raise ValueError("Runner without type")

            if config["runner"]["type"] == "ssh":
                if "hostname" not in config["runner"]:
                    raise ValueError("Ssh runner without hostname")
                runner_config = {
                    k: v for k, v in config["runner"].items() if k not in {"type"}
                }
                runner = SshCommandRunner(config=runner_config)
            else:
                raise ValueError(
                    f"Runner with type {config['runner']['type']} is unknown"
                )
        else:
            runner = LocalCommandRunner()
        return SlurmScheduler(runner=runner, **slurm_config)
    else:
        raise ValueError(f'Scheduler with type {config["type"]} is unknown')
