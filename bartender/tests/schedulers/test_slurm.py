from asyncio import new_event_loop, sleep
from pathlib import Path
from typing import Generator

import pytest
from asyncssh.misc import ConnectionLost
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_container_is_ready

from bartender._ssh_utils import SshConnectConfig
from bartender.db.models.job_model import CompletedStates
from bartender.filesystems.sftp import SftpFileSystem
from bartender.schedulers.abstract import JobDescription
from bartender.schedulers.runner import SshCommandRunner
from bartender.schedulers.slurm import SlurmScheduler


class SlurmContainer(DockerContainer):
    def __init__(self, image: str = "xenonmiddleware/slurm:20"):
        super().__init__(image=image)
        self.port_to_expose = 22
        self.with_exposed_ports(self.port_to_expose)

    def get_config(self) -> SshConnectConfig:
        username = "xenon"
        password = "javagat"  # noqa: S105
        hostname = self.get_container_host_ip()
        port = int(self.get_exposed_port(self.port_to_expose))
        return {
            "hostname": hostname,
            "port": port,
            "username": username,
            "password": password,
        }

    def get_runner(self) -> SshCommandRunner:
        return SshCommandRunner(self.get_config())

    def get_filesystem(self) -> SftpFileSystem:
        home_dir = Path("/home/xenon")
        return SftpFileSystem(entry=home_dir, config=self.get_config())

    def start(self) -> "SlurmContainer":
        super().start()
        self._connect()
        return self

    async def _ping(self) -> None:
        with self.get_runner() as conn:
            await conn.run("echo", [])

    @wait_container_is_ready(ConnectionLost)
    def _connect(self) -> None:
        loop = new_event_loop()
        try:
            loop.run_until_complete(self._ping())
        finally:
            loop.close()


@pytest.fixture
def slurm_server() -> Generator[SlurmContainer, None, None]:
    with SlurmContainer() as container:
        yield container


@pytest.mark.anyio
async def test_ok_running_job_with_input_and_output_file(
    tmp_path: Path,
    slurm_server: SlurmContainer,
) -> None:
    job_dir = tmp_path
    try:
        client = slurm_server.get_runner()
        scheduler = SlurmScheduler(runner=client)
        (job_dir / "input").write_text("Lorem ipsum")
        description = JobDescription(
            command="echo -n hello && wc input > output",
            job_dir=str(job_dir),
        )
        fs = slurm_server.get_filesystem()
        localized_description = fs.localize_description(description, job_dir.parent)

        await fs.upload(description, localized_description)

        jid = await scheduler.submit(localized_description)

        await wait_for_job(scheduler, jid)

        await fs.download(localized_description, description)

        assert_output(job_dir)
    finally:
        await scheduler.close()


def assert_output(job_dir: Path) -> None:
    assert (job_dir / "returncode").read_text() == "0"
    assert (job_dir / "stdout.txt").read_text() == "hello"
    assert (job_dir / "stderr.txt").read_text() == ""
    assert (job_dir / "input").exists()
    assert (job_dir / "output").read_text().strip() == "0  2 11 input"


async def wait_for_job(scheduler: SlurmScheduler, job_id: str) -> None:
    for _ in range(30):
        state = await scheduler.state(job_id)
        if state in CompletedStates:
            break
        await sleep(0.5)

    assert state == "ok"


@pytest.mark.anyio
async def test_ok_running_job_without_iofiles(
    tmp_path: Path,
    slurm_server: SlurmContainer,
) -> None:
    job_dir = tmp_path
    try:
        client = slurm_server.get_runner()
        scheduler = SlurmScheduler(runner=client)
        description = JobDescription(command="echo -n hello", job_dir=str(job_dir))
        fs = slurm_server.get_filesystem()
        localized_description = fs.localize_description(description, job_dir.parent)

        await fs.upload(description, localized_description)

        jid = await scheduler.submit(localized_description)

        await wait_for_job(scheduler, jid)

        await fs.download(localized_description, description)

        assert (job_dir / "returncode").read_text() == "0"
        assert (job_dir / "stdout.txt").read_text() == "hello"
        assert (job_dir / "stderr.txt").read_text() == ""
    finally:
        await scheduler.close()
