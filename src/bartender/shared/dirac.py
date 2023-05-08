import pkgutil

DIRAC_INSTALLED = (
    pkgutil.find_loader("DIRAC") is not None
)  # noqa: WPS462 sphinx understands
"""True if DIRAC package is installed, False otherwise."""  # noqa: E501, WPS322, WPS428 sphinx understands


async def make_dirac_proxy_valid() -> None:
    """Make sure that the DIRAC proxy is valid."""
    # TODO use cache so that we don't have to check every time it is called
    # but every 30 minutes or so
    # TODO Check that current proxy is expired or close to expiring
    # TODO If it is then try to renew it
    # TODO implement this
    pass  # noqa: WPS420
    # TODO call this function everytime before we call a DIRAC function
