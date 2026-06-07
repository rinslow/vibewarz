"""Reads the visible lane and builds the counter to whatever is threatening.

A demonstration of the intended Vibelords play loop: you can't see the
opponent's hidden build queue, but you *can* see the units already marching, so
you build the class that counters the nearest threat — and mix randomly when you
have no read (so you stay unpredictable). It airstrikes when its base is swarmed
and teches up when it has spare XP.
"""

from __future__ import annotations

import random

from vibewarz import (
    VibelordsAdvanceAgeAction,
    VibelordsBot,
    VibelordsNoopAction,
    VibelordsSpecialAction,
    VibelordsState,
)
from vibewarz_games.vibelords import units as U

# Inverse of the counter map: PREDATOR[t] is the unit that beats type ``t``.
PREDATOR = {beaten: beater for beater, beaten in U.COUNTERS.items()}


class VibelordsCounterBot(VibelordsBot):
    display_name = "VibelordsCounterBot"

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def act(self, state: VibelordsState):
        seat = self.seat
        me = state.player(seat)
        enemies = [u for u in state.units if u.owner != seat]
        mid = state.lane.length / 2.0

        # 1) Panic airstrike if the base is being swarmed.
        if me.special_cd == 0:
            if seat == 0:
                threat = [e for e in enemies if e.x <= mid]
            else:
                threat = [e for e in enemies if e.x >= mid]
            if len(threat) >= 3:
                return VibelordsSpecialAction()

        # 2) Tech up when there's spare XP (doesn't compete with the gold economy).
        cost = U.age_up_cost(me.age)
        if cost is not None and me.xp >= cost + 40:
            return VibelordsAdvanceAgeAction()

        # 3) Decide what to build. Counter the enemy unit nearest my base; with no
        #    read at all, mix randomly so I'm not predictable.
        if enemies:
            front = (min if seat == 0 else max)(enemies, key=lambda e: e.x)
            want = PREDATOR[front.unit]
        else:
            want = self._rng.choice(U.UNIT_TYPES)

        builds = {
            a["unit"]: a
            for a in self.legal_actions(state)
            if a["type"] == "build"
        }
        if want in builds:
            return builds[want]
        if builds:  # can't afford the counter — take the cheapest thing I can
            return min(
                builds.values(),
                key=lambda a: U.unit_stats(a["unit"], me.age)["gold_cost"],
            )
        return VibelordsNoopAction()  # save up
