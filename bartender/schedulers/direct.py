from asyncio import create_subprocess_shell
from pathlib import Path
from string import Template

from bartender.settings import AppSetting


async def submit(job_dir: Path, app: AppSetting) -> None:
    """Run the command of a application inside the job directory immediatly.

    After executation the following files will be written to `job_dir`:

    * stdout.txt
    * stderr.txt
    * returncode

    :param job_dir: Directory where input files for application are located.
    :param app: Which application to execute
    """
    cmd = Template(app.command).substitute(config=app.config)

    with open(job_dir / "stderr.txt", "w") as stderr:
        with open(job_dir / "stdout.txt", "w") as stdout:
            proc = await create_subprocess_shell(
                cmd,
                stdout=stdout,
                stderr=stderr,
                cwd=job_dir,
            )
            returncode = await proc.wait()
            (job_dir / "returncode").write_text(str(returncode))
