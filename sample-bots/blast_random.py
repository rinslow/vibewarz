"""Uniform-random over legal actions — Blast leaderboard floor."""

from __future__ import annotations

import random

from vibewarz import BlastAction, BlastBot, BlastState


class BlastRandomBot(BlastBot):
    display_name = "BlastRandomBot"

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def act(self, state: BlastState):
        legal = self.legal_actions(state)
        if not legal:
            return BlastAction(move="stay", drop_bomb=False)
        return self._rng.choice(legal)
