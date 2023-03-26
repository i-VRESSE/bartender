from asyncio import new_event_loop
from pathlib import Path
from typing import Generator

import pytest
from asyncssh.misc import ConnectionLost
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_container_is_ready

from bartender.filesystems.sftp import SftpFileSystem, SftpFileSystemConfig
from bartender.schedulers.abstract import JobDescription
from bartender.schedulers.runner import SshCommandRunner
from bartender.schedulers.slurm import SlurmScheduler, SlurmSchedulerConfig
from bartender.ssh_utils import SshConnectConfig
from tests.schedulers.helpers import assert_output, prepare_input, wait_for_job


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
        return SshConnectConfig(
            hostname=hostname,
            port=port,
            username=username,
            password=password,
        )

    def get_filesystem(self) -> SftpFileSystem:
        home_dir = Path("/home/xenon")
        return SftpFileSystem(
            SftpFileSystemConfig(entry=home_dir, ssh_config=self.get_config()),
        )

    def start(self) -> "SlurmContainer":
        super().start()
        self._connect()
        return self

    async def _ping(self) -> None:
        with SshCommandRunner(self.get_config()) as conn:
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
        ssh_config = slurm_server.get_config()
        scheduler = SlurmScheduler(SlurmSchedulerConfig(ssh_config=ssh_config))
        description = prepare_input(job_dir)
        fs = slurm_server.get_filesystem()
        localized_description = fs.localize_description(description, job_dir.parent)

        await fs.upload(description, localized_description)

        jid = await scheduler.submit(localized_description)

        await wait_for_job(scheduler, jid)

        await fs.download(localized_description, description)

        assert_output(job_dir)
    finally:
        await scheduler.close()


@pytest.mark.anyio
async def test_ok_running_job_without_iofiles(
    tmp_path: Path,
    slurm_server: SlurmContainer,
) -> None:
    job_dir = tmp_path
    try:
        ssh_config = slurm_server.get_config()
        scheduler = SlurmScheduler(SlurmSchedulerConfig(ssh_config=ssh_config))
        description = JobDescription(command="echo -n hello", job_dir=job_dir)
        fs = slurm_server.get_filesystem()
        localized_description = fs.localize_description(description, job_dir.parent)

        await fs.upload(description, localized_description)

        jid = await scheduler.submit(localized_description)

        await wait_for_job(scheduler, jid)

        await fs.download(localized_description, description)

        assert_output_without_iofiles(job_dir)
    finally:
        await scheduler.close()


def assert_output_without_iofiles(job_dir: Path) -> None:
    assert (job_dir / "returncode").read_text() == "0"
    assert (job_dir / "stdout.txt").read_text() == "hello"
    assert (job_dir / "stderr.txt").read_text() == ""
    files = list(job_dir.iterdir())
    assert len(files) == 3
