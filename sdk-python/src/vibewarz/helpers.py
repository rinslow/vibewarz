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
    performs that accumulation centrally — `state["trails"]` is always
    populated for the bot — so this class is a backward-compatible
    shim that simply re-exposes the cumulative trails.

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

    Bots written from scratch can read `state["trails"]` directly.
    """

    def __init__(self) -> None:
        self.trails: list[list[tuple[float, float]]] = []

    def on_start(self, initial_state: dict[str, Any]) -> None:
        self.trails = [list(t) for t in initial_state.get("trails", [])]

    def update(self, state: dict[str, Any]) -> list[list[tuple[float, float]]]:
        """Return the cumulative per-seat trails from `state["trails"]`.

        The SDK accumulator keeps `state["trails"]` cumulative, so this
        is just a passthrough. Falls back to seeding from the snapshot
        on first call if `on_start` was skipped (e.g. bot mid-match
        reconnect — not currently supported by the platform but the
        defensive read costs nothing).
        """
        trails = state.get("trails")
        if isinstance(trails, list):
            self.trails = [list(t) if isinstance(t, list) else t for t in trails]
        return self.trails
