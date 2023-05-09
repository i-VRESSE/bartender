from datetime import datetime

from DIRAC import gLogger, initialize
from DIRAC.FrameworkSystem.Client.ProxyManagerClient import ProxyManagerClient

from bartender.shared.dirac_config import ProxyConfig

class ProxyChecker:
    def __init__(self, config: ProxyConfig) -> None:
        self.config = config
        self.last_check = datetime.now()
        # TODO make sure initialize is only called once per process
        initialize()
        gLogger.setLevel("debug")  # TODO remove
        self.client = ProxyManagerClient()


    async def check(self):
        """Make sure that the DIRAC proxy is valid."""
        # TODO use cache so that we don't have to check every time it is called
        # but every 30 minutes or so
        # TODO check that there is a proxy, if not then create one
        # TODO Check that current proxy is expired or close to expiring
        # TODO If it is then try to renew it
        # TODO implement this
        self.client.renewProxy(newProxyLifeTime=self.config.valid)
        # TODO call this function everytime before we call a DIRAC function
