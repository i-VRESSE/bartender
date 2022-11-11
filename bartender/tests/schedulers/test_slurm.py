from asyncio import sleep
from pathlib import Path

import pytest
from testcontainers.core.container import DockerContainer

from bartender.schedulers.abstract import JobDescription
from bartender.schedulers.slurm import SlurmScheduler, SSHTerminal


class SlurmContainer(DockerContainer):
    def __init__(self, image="xenonmiddleware/slurm:20"):
        super(SlurmContainer, self).__init__(image=image)
        self.port_to_expose = 22
        self.with_exposed_ports(self.port_to_expose)

    def terminal(self):
        username = "xenon"
        password = "javagat"
        hostname = self.get_container_host_ip()
        port = self.get_exposed_port(self.port_to_expose)
        # TODO configure terminal
        return SSHTerminal()


@pytest.fixture
def slurm_server_terminal():
    with SlurmContainer() as container:
        yield container.terminal()


@pytest.mark.anyio
async def test_ok_running_job(tmp_path: Path, slurm_server_terminal) -> None:
    try:
        scheduler = SlurmScheduler(slurm_server_terminal)
        description = JobDescription(command="echo -n hello", job_dir=str(tmp_path))

        jid = await scheduler.submit(description)

        # Wait for job to complete
        # TODO poll state as slurm is slower
        await sleep(0.01)
        assert (await scheduler.state(jid)) == "ok"
        assert (tmp_path / "returncode").read_text() == "0"
        assert (tmp_path / "stdout.txt").read_text() == "hello"
    finally:
        await scheduler.close()
