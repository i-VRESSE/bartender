from importlib import import_module
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from bartender.user import User

if TYPE_CHECKING:
    from bartender.context import Context

DestinationPicker = Callable[[Path, str, User, "Context"], str]


def pick_first(
    job_dir: Path,
    application_name: str,
    submitter: User,
    context: "Context",
) -> str:
    """Always picks first available destination from context.

    Args:
        job_dir: Location where job input files are located.
        application_name: Application name that should be run.
        submitter: User that submitted the job.
        context: Context with applications and destinations.

    Returns:
        Destination name.
    """
    destination_names = list(context.destinations.keys())
    return destination_names[0]


def pick_byname(
    job_dir: Path,
    application_name: str,
    submitter: User,
    context: "Context",
) -> str:
    """Picks destination with same name as application name.

    Args:
        job_dir: Location where job input files are located.
        application_name: Application name that should be run.
        submitter: User that submitted the job.
        context: Context with applications and destinations.

    Returns:
        Destination name.

    Raises:
        KeyError: If application has no destination.
    """
    if application_name in context.destinations:
        return application_name
    raise KeyError(f"Application {application_name} has no destination.")


def pick_byindex(
    job_dir: Path,
    application_name: str,
    submitter: User,
    context: "Context",
) -> str:
    """Picks destination by index.

    For example the 2nd application will be submitted to the 2nd destination.

    Args:
        job_dir: Location where job input files are located.
        application_name: Application name that should be run.
        submitter: User that submitted the job.
        context: Context with applications and destinations.

    Returns:
        Destination name.
    """
    application_index = list(context.applications.keys()).index(application_name)
    destination_names = list(context.destinations.keys())
    return destination_names[application_index]


class PickRound:
    """Builder for round robin destination picker."""

    def __init__(self) -> None:
        self.last = ""

    def __call__(
        self,
        job_dir: Path,
        application_name: str,
        submitter: User,
        context: "Context",
    ) -> str:
        """Always picks the next destination.

        Takes list of destinations and each time it is called will pick the next
        destination in the destination list. Going around to start when end is
        reached.

        Args:
            job_dir: Location where job input files are located.
            application_name: Application name that should be run.
            submitter: User that submitted the job.
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
    """Import a picker function.

    Args:
        destination_picker_name: function import as string.
            Format `<module>:<function>` or `<path to python file>:<function>`

    Returns:
        Function that can be used to pick to which destination a job should be
        submitted.

    Raises:
        ValueError: If the function could not be imported.
    """
    (module_name, function_name) = destination_picker_name.split(":")
    if module_name.endswith(".py"):
        file_path = Path(module_name)
        spec = spec_from_file_location(file_path.name, file_path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Could not load {file_path}")
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
    else:
        module = import_module(module_name)
    return getattr(module, function_name)
