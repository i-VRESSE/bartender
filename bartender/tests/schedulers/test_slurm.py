import asyncio
from asyncio import sleep
from pathlib import Path

import asyncssh
import pytest
from asyncssh.misc import ConnectionLost
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_container_is_ready

from bartender.db.models.job_model import CompletedStates
from bartender.schedulers.abstract import JobDescription
from bartender.schedulers.slurm import SlurmScheduler, SSHCommandRunner


class SlurmContainer(DockerContainer):
    def __init__(self, image="xenonmiddleware/slurm:20"):
        super(SlurmContainer, self).__init__(image=image)
        self.port_to_expose = 22
        self.with_exposed_ports(self.port_to_expose)

    async def _ping(self):
        vargs = {
            "host": self.get_container_host_ip(),
            "port": int(self.get_exposed_port(self.port_to_expose)),
            "username": "xenon",
            "password": "javagat",
            "known_hosts": None,
            "agent_path": None,
        }
        async with asyncssh.connect(**vargs) as conn:
            await conn.run('echo "ping"', check=True)

    @wait_container_is_ready(ConnectionLost)
    def _connect(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self._ping())

    def get_client(self):
        username = "xenon"
        password = "javagat"
        hostname = self.get_container_host_ip()
        port = int(self.get_exposed_port(self.port_to_expose))
        print((hostname, port))
        return SSHCommandRunner(hostname, port, username, password)

    def start(self):
        super().start()
        self._connect()
        return self


@pytest.fixture
def slurm_server():
    with SlurmContainer() as container:
        yield container


@pytest.mark.anyio
async def test_ok_running_job(tmp_path: Path, slurm_server) -> None:
    try:
        client = slurm_server.get_client()
        scheduler = SlurmScheduler(runner=client)
        print("submit")
        description = JobDescription(
            command="echo -n hello"
            # , job_dir=str(tmp_path)
            # tmp_path is not owned by xenon user, so cd fails, use writeable path
            ,
            job_dir="/tmp",
        )

        jid = await scheduler.submit(description)

        print("submitted")
        print(jid)
        for _ in range(30):
            state = await scheduler.state(jid)
            if state in CompletedStates:
                break
            await sleep(0.5)

        assert state == "ok"
        # TODO deal with files in container
        # assert (tmp_path / "returncode").read_text() == "0"
        # assert (tmp_path / "stdout.txt").read_text() == "hello"
    finally:
        await scheduler.close()
