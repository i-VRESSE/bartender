from asyncio import sleep
from pathlib import Path

import pytest

from bartender.db.models.job_model import CompletedStates, State
from bartender.filesystems.dirac import DiracFileSystem, DiracFileSystemConfig
from bartender.schedulers.abstract import AbstractScheduler, JobDescription
from bartender.schedulers.dirac import DiracScheduler, DiracSchedulerConfig
from bartender.schedulers.runner import SshCommandRunner
from bartender.shared.ssh import SshConnectConfig


def prepare_input(job_dir: Path) -> JobDescription:
    (job_dir / "input").write_text("Lorem ipsum")
    return JobDescription(
        command="echo -n hello && mkdir output && wc input > output/output.txt",
        job_dir=job_dir,
    )


def assert_output(job_dir: Path) -> None:
    assert (job_dir / "returncode").read_text() == "0"
    assert (job_dir / "stdout.txt").read_text() == "hello"
    assert (job_dir / "stderr.txt").read_text() == ""
    assert (job_dir / "input").exists()
    assert (job_dir / "output" / "output.txt").read_text().strip() == "0  2 11 input"


async def wait_for_job(
    scheduler: AbstractScheduler,
    job_id: str,
    expected: State = "ok",
    delay: float = 0.5,
    attempts: int = 1200,  # 10 minutes max runtime
) -> None:
    state = "new"
    for _ in range(attempts):
        state = await scheduler.state(job_id)
        if state in CompletedStates:
            break
        await sleep(delay)

    assert state == expected


@pytest.mark.anyio
async def test_it(  # noqa: WPS217 single piece of code for readablilty
    tmp_path: Path,
) -> None:
    """Happy path test of the DIRAC scheduler and filesystem.

    # Manual setup
    tmp_path = Path("/tmp/test_it")
    tmp_path.mkdir()

    # Manual cleanup
    rm -rf /tmp/test_it/
    dirac-dms-filecatalog-cli
    rm /tutoVO/user/c/ciuser/bartenderjobs/job1/input.tar
    rm /tutoVO/user/c/ciuser/bartenderjobs/job1/output.tar
    rmdir /tutoVO/user/c/ciuser/bartenderjobs/job1
    """
    fs_config = DiracFileSystemConfig(
        lfn_root="/tutoVO/user/c/ciuser/bartenderjobs",
        storage_element="StorageElementOne",
    )
    fs = DiracFileSystem(fs_config)
    sched_config = DiracSchedulerConfig(storage_element=fs_config.storage_element)
    scheduler = DiracScheduler(sched_config)
    # emulate external job id with job1 subdir
    # job_dir.name is used as directory to upload inputfiles to lfn_root
    job_dir = tmp_path / "job1"
    job_dir.mkdir()
    description = prepare_input(job_dir)
    gdescription = fs.localize_description(description, tmp_path)
    try:
        await fs.upload(description, gdescription)

        job_id = await scheduler.submit(gdescription)

        assert job_id

        await wait_for_job(scheduler, job_id)

        await fs.download(gdescription, description)

        assert_output(job_dir)
    finally:
        # So next time the test does not complain about existing files
        await fs.delete(gdescription)
        await fs.close()
        await scheduler.close()


@pytest.fixture(scope="session")
async def apptainer_image() -> Path:
    """Adds alpine.sif to DIRAC server.

    Raises:
        RuntimeError: If the image could not be built.
    """
    runner = SshCommandRunner(
        SshConnectConfig(  # noqa: S106 container has password hardcoded
            hostname="dirac-tuto",
            username="diracuser",
            password="password",
        ),
    )
    docker_image = "docker://alpine"
    image = Path("/cvmfs/my.repo.name/applications/alpine.sif")
    mkdir_returncode, _, _ = await runner.run(
        command="mkdir",
        args=["-p", str(image.parent)],
    )
    if mkdir_returncode:
        raise RuntimeError(f"Failed to mkdir {image.parent}")
    cmd = f". /opt/dirac/bashrc && apptainer build --force {image.name} {docker_image}"
    build_returncode, _, _ = await runner.run(
        command="bash",
        args=[],
        stdin=cmd,
        cwd=image.parent,
    )
    if build_returncode:
        raise RuntimeError(f"Failed to build {image}")
    return image


@pytest.mark.anyio
async def test_it_with_apptainer(  # noqa: WPS217 single piece of code for readablilty
    apptainer_image: Path,
    tmp_path: Path,
) -> None:
    fs_config = DiracFileSystemConfig(
        lfn_root="/tutoVO/user/c/ciuser/bartenderjobs",
        storage_element="StorageElementOne",
    )
    fs = DiracFileSystem(fs_config)
    sched_config = DiracSchedulerConfig(
        storage_element=fs_config.storage_element,
        apptainer_image=apptainer_image,
    )
    scheduler = DiracScheduler(sched_config)
    job_dir = tmp_path / "job2"
    job_dir.mkdir()
    # The tests are running on Ubuntu
    # The DIRAC server is running CERN CentOS 7
    # So to check job is running in apptainer check for OS
    description = JobDescription(
        command="cat /etc/os-release",
        job_dir=job_dir,
    )
    gdescription = fs.localize_description(description, tmp_path)
    try:
        await fs.upload(description, gdescription)

        job_id = await scheduler.submit(gdescription)

        assert job_id

        await wait_for_job(scheduler, job_id)

        await fs.download(gdescription, description)

        assert "Alpine Linux" in (job_dir / "stdout.txt").read_text()
    finally:
        # So next time the test does not complain about existing files
        await fs.delete(gdescription)
        await fs.close()
        await scheduler.close()


@pytest.mark.anyio
async def test_states_and_cancel(tmp_path: Path) -> None:  # noqa: WPS217 readablilty
    fs_config = DiracFileSystemConfig(
        lfn_root="/tutoVO/user/c/ciuser/bartenderjobs",
        storage_element="StorageElementOne",
    )
    fs = DiracFileSystem(fs_config)
    sched_config = DiracSchedulerConfig(storage_element=fs_config.storage_element)
    scheduler = DiracScheduler(sched_config)
    job_dir = tmp_path / "job3"
    job_dir.mkdir()
    description = JobDescription(
        command="sleep 900",
        job_dir=job_dir,
    )
    gdescription = fs.localize_description(description, tmp_path)
    try:
        await fs.upload(description, gdescription)

        job_id = await scheduler.submit(gdescription)

        await sleep(1)
        states = await scheduler.states([job_id])
        assert states == ["queued"]

        await scheduler.cancel(job_id)

        await sleep(1)
        states = await scheduler.states([job_id])
        assert states == ["error"]
    finally:
        # So next time the test does not complain about existing files
        await fs.delete(gdescription)
        await fs.close()
        await scheduler.close()
