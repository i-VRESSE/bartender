import asyncio
import subprocess  # noqa: S404 security implications OK
from pathlib import Path
from typing import AsyncGenerator  # security implications OK

import pytest

from bartender.shared.dirac import (
    get_time_left_on_proxy,
    make_valid_dirac_proxy,
    proxy_init,
    setup_proxy_renewer,
    teardown_proxy_renewer,
)
from bartender.shared.dirac_config import ProxyConfig


def destroy_proxy() -> None:
    subprocess.run(  # noqa: S607 security implications OK
        "dirac-proxy-destroy",
        check=True,
        timeout=60,
        shell=True,  # noqa: S602 security implications OK
    )


@pytest.fixture
async def reset_proxy() -> AsyncGenerator[None, None]:
    destroy_proxy()
    yield
    await proxy_init(ProxyConfig())


# All tests in this module should
# start with no proxy and leave default proxy behind
pytestmark = pytest.mark.usefixtures("reset_proxy")


@pytest.mark.anyio
async def test_get_time_left_on_proxy_given_no_proxy() -> None:
    with pytest.raises(ValueError, match="Failed to get proxy info"):
        get_time_left_on_proxy()


@pytest.mark.anyio
async def test_make_valid_dirac_proxy_given_no_proxy() -> None:

    await make_valid_dirac_proxy(ProxyConfig(valid="00:03"))

    time_left = get_time_left_on_proxy()
    assert 160 < time_left < 180


@pytest.mark.anyio
async def test_make_valid_dirac_proxy_given_bad_cert(tmp_path: Path) -> None:
    bad_cert = str(tmp_path / "usercert.pem")

    with pytest.raises(subprocess.CalledProcessError) as excinfo:
        await make_valid_dirac_proxy(ProxyConfig(cert=bad_cert))

    assert excinfo.value.returncode == 1  # noqa: WPS441 according to pytest docs
    assert (
        "Cannot load certificate"
        in excinfo.value.stdout.decode()  # noqa: WPS441 according to pytest docs
    )


@pytest.mark.anyio
async def test_renewer_setup_teardown() -> None:
    setup_proxy_renewer(ProxyConfig(valid="00:03", min_life=30))

    # Give renewer task time to run
    await asyncio.sleep(0.1)

    # TODO check that renewer task was called and initialized a proxy

    await teardown_proxy_renewer()


@pytest.mark.anyio
async def test_renewer_setup_teardown_given_different_config() -> None:
    setup_proxy_renewer(ProxyConfig(valid="00:03", min_life=30))
    with pytest.raises(ValueError, match="Can only have one unique proxy config"):
        setup_proxy_renewer(ProxyConfig(valid="11:11", min_life=3600))

    # Give renewer task time to run
    await asyncio.sleep(0.1)

    await teardown_proxy_renewer()
