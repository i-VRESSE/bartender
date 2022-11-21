from typing import Any

from bartender.schedulers.abstract import AbstractScheduler

from bartender.schedulers.memory import MemoryScheduler
from bartender.schedulers.runner import LocalCommandRunner, SshCommandRunner
from bartender.schedulers.slurm import SlurmScheduler

def build(config: Any) -> AbstractScheduler:
    """Build scheduler instance from configuration."""
    if "type" not in config:
        raise KeyError("Scheduler without type")
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
                    f"Runner with type {config['runner']['type']} is unknown",
                )
        else:
            runner = LocalCommandRunner()
        return SlurmScheduler(runner=runner, **slurm_config)
    else:
        raise ValueError(f'Scheduler with type {config["type"]} is unknown')
