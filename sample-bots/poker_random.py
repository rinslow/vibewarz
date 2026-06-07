"""Uniform-random over legal actions. Useful as a stylistic foil and as a
chaos baseline for the leaderboard.
"""

from __future__ import annotations

import random

from vibewarz import PokerBot, PokerCheckAction, PokerState


class PokerRandomBot(PokerBot):
    display_name = "PokerRandomBot"

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def act(self, state: PokerState):
        legal = self.legal_actions(state)
        if not legal:
            return PokerCheckAction()  # shouldn't be reached if we got asked
        return self._rng.choice(legal)
