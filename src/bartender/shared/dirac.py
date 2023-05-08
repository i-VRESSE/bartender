import pkgutil

DIRAC_INSTALLED = (
    pkgutil.find_loader("DIRAC") is not None
)  # noqa: WPS462 sphinx understands
"""True if DIRAC package is installed, False otherwise."""  # noqa: E501, WPS322, WPS428 sphinx understands
