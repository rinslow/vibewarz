"""Bot-side helpers for common per-game state plumbing.

These are optional — bots can ignore them and parse `state` directly.
"""

from __future__ import annotations

from typing import Any


class TrailTracker:
    """Surfaces the full per-seat trails out of the live state.

    Historically this class accumulated `trail_delta` into a local
    cumulative list because the server sent only deltas mid-match.
    The SDK's `StateAccumulator` (auto-installed by the runner) now
    performs that accumulation centrally — `state.trails` for typed bots
    and `state["trails"]` for legacy bots is always populated — so this
    class is a backward-compatible shim that simply re-exposes the
    cumulative trails.

    Existing bot code keeps working unchanged:

        class MyBot(Bot):
            game = "curve"
            def __init__(self):
                self.trails = TrailTracker()
            def on_start(self, initial_state):
                self.trails.on_start(initial_state)
            def act(self, state):
                self.trails.update(state)
                full = self.trails.trails  # list[list[(x, y)]]
                ...

    Bots written from scratch can read `state.trails` directly when using
    `CurveBot`, or `state["trails"]` from a legacy `Bot`.
    """

    def __init__(self) -> None:
        self.trails: list[list[tuple[float, float]]] = []

    def on_start(self, initial_state: dict[str, Any] | Any) -> None:
        self.trails = [list(t) for t in _state_get(initial_state, "trails", [])]

    def update(self, state: dict[str, Any] | Any) -> list[list[tuple[float, float]]]:
        """Return the cumulative per-seat trails from the bot state.

        The SDK accumulator keeps trails cumulative, so this is just a
        passthrough. Falls back to seeding from the snapshot on first call
        if `on_start` was skipped (e.g. bot mid-match reconnect — not
        currently supported by the platform but the defensive read costs
        nothing).
        """
        trails = _state_get(state, "trails", None)
        if isinstance(trails, list):
            self.trails = [list(t) if isinstance(t, list) else t for t in trails]
        return self.trails


def _state_get(state: dict[str, Any] | Any, key: str, default: Any) -> Any:
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)
