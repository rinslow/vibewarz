"""Uniform-random over legal actions — Vibelords leaderboard floor."""

from __future__ import annotations

import random

from vibewarz import VibelordsBot, VibelordsNoopAction, VibelordsState


class VibelordsRandomBot(VibelordsBot):
    display_name = "VibelordsRandomBot"

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def act(self, state: VibelordsState):
        legal = self.legal_actions(state)
        return self._rng.choice(legal) if legal else VibelordsNoopAction()
