"""Authoritative server-side game engines for vibewarz.

Importing this package registers all games into `_core.registry.GAMES`.
"""

from ._core import GAMES, Game, GameMeta, StepResult, register
from .blast import game as _blast_module  # noqa: F401  side-effect: registers Blast
from .curve import game as _curve_module  # noqa: F401  side-effect: registers Curve
from .poker import game as _poker_module  # noqa: F401  side-effect: registers Poker

__all__ = ["GAMES", "Game", "GameMeta", "StepResult", "register"]
__version__ = "0.1.0"
