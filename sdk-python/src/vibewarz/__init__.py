"""vibewarz Python SDK — write bots that play vibewarz games."""

from importlib.metadata import PackageNotFoundError, version

# Source the version from installed package metadata so `vibewarz.__version__`
# always matches the PyPI release. Falls back to "dev" when running from a
# source checkout that wasn't pip-installed. Defined BEFORE the submodule
# imports below so `from . import __version__` works from inside the package
# without a partial-import error.
try:
    __version__ = version("vibewarz")
except PackageNotFoundError:
    __version__ = "dev"

from .bot import Bot
from .client import Client
from .helpers import TrailTracker
from .runner import run

__all__ = ["Bot", "Client", "TrailTracker", "run", "__version__"]
