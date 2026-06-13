"""Uniform-random over legal actions — Rock Paper Scissors baseline."""

from __future__ import annotations

import random

from vibewarz import (
    RockPaperScissorsBot,
    RockPaperScissorsFightAction,
    RockPaperScissorsState,
)


class RockPaperScissorsRandomBot(RockPaperScissorsBot):
    display_name = "RockPaperScissorsRandomBot"

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def act(self, state: RockPaperScissorsState):
        legal = self.legal_actions(state)
        if legal:
            return self._rng.choice(legal)
        return RockPaperScissorsFightAction(piece="rock")
