from asyncio import create_subprocess_shell
from pathlib import Path
from string import Template
from typing import Any, Callable, Coroutine

from bartender.settings import AppSetting

UpdateState = Callable[[str], Coroutine[Any, Any, None]]


async def submit(
    job_dir: Path,
    app: AppSetting,
    update_state: UpdateState,
) -> None:
    """Run the command of a application inside the job directory immediatly.

    After executation the following files will be written to `job_dir`:

    * stdout.txt
    * stderr.txt
    * returncode

    :param job_dir: Directory where input files for application are located.
    :param app: Which application to execute
    :param update_state: Function to update the state of the job elsewhere like the db.
    """
    cmd = Template(app.command).substitute(config=app.config)

    with open(job_dir / "stderr.txt", "w") as stderr:
        with open(job_dir / "stdout.txt", "w") as stdout:
            await update_state("running")
            proc = await create_subprocess_shell(
                cmd,
                stdout=stdout,
                stderr=stderr,
                cwd=job_dir,
            )
            # TODO store proc.pid in db,
            # for slurm it would be the slurm job id that needs to be saved in db
            returncode = await proc.wait()
            if returncode == 0:
                await update_state("ok")
            else:
                await update_state("error")
            (job_dir / "returncode").write_text(str(returncode))
