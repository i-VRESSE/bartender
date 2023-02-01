from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from bartender.context import Context

DestinationPicker = Callable[[Path, str, "Context"], str]


def pick_first(
    job_dir: Path,
    application_name: str,
    context: "Context",
) -> str:
    """Always picks first available destination from context.

    Args:
        job_dir: Location where job input files are located.
        application_name: Application name that should be run.
        context: Context with applications and destinations.

    Returns:
        Destination name.
    """
    destination_names = list(context.destinations.keys())
    return destination_names[0]


class PickRound:
    """Builder for round robin destination picker."""

    def __init__(self) -> None:
        self.last = ""

    def __call__(
        self,
        job_dir: Path,
        application_name: str,
        context: "Context",
    ) -> str:
        """Always picks the next destination.

        Takes list of destinations and each time it is called will
        pick the next destination in the destination list.
        Going around to start when end is reached.

        Args:
            job_dir: Location where job input files are located.
            application_name: Application name that should be run.
            context: Context with applications and destinations.

        Returns:
            Destination name.
        """
        destination_names = list(context.destinations.keys())
        if self.last == "":
            self.last = destination_names[0]
        else:
            for index, name in enumerate(destination_names):
                if name == self.last:
                    new_index = (index + 1) % len(destination_names)
                    self.last = destination_names[new_index]
                    break

        return self.last


pick_round: DestinationPicker = PickRound()


def import_picker(destination_picker_name: str) -> DestinationPicker:
    """Import a picker function based on a `<module>:<function>` string.

    Args:
        destination_picker_name: function import as string.

    Returns:
        Function that can be used to pick to which destination a job
        should be submitted.
    """
    # TODO allow somedir/somefile.py:pick_round_robin
    (module_name, function_name) = destination_picker_name.split(":")
    module = import_module(module_name)
    return getattr(module, function_name)
