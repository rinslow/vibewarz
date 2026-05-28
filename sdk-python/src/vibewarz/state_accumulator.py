"""Client-side state accumulator for delta-encoded server views.

The server sends a full snapshot in `GameStartS2C` / `GameEndS2C` and a
per-tick *delta* in `TickRequestS2C` / `TickResultS2C` (see
`vibewarz_games._core.base.Game.delta_view_for`). The wire payload size
is bounded per tick — without this, Curve trails grow O(N) per tick and
the broadcast cost compounds quadratically over a match.

This accumulator runs inside the SDK's WS message loop and reconstructs
the cumulative state so `bot.act(state)` keeps seeing a fully-materialised
dict. Bot authors do not need to opt in; the runner installs one per
match.

Per-game append rules
=====================

Most fields are full-replace: the cumulative value is overwritten with
whatever the delta carries. A few fields are append-only and need
element-wise merging:

  - **Curve**: ``trail_delta`` (list[list[(x, y)]], one per player)
    is appended element-wise onto cumulative ``trails`` (per-seat rule).
  - **Poker**: ``history_delta`` (list of action-log entries) is
    concatenated onto the flat cumulative ``history`` list (flat rule).

Two rule shapes:
  - ``_APPEND_RULES`` — *per-seat parallel* lists: ``delta`` and ``base``
    are both list-of-lists of the same outer length; each inner list is
    extended element-wise (Curve trails).
  - ``_FLAT_APPEND_RULES`` — a single flat list: ``delta`` is concatenated
    onto the flat ``base`` list (Poker history).

If a game adds another append-only field, add its rule to whichever tuple
matches its shape; the accumulator handles the rest.

Same-tick redelivery
====================

The server currently emits the same view via `tick_request` (pre-step)
and `tick_result` (post-step) when the server hasn't advanced its
authoritative state between them — this happens during action
collection. Naïve append would duplicate. The accumulator tracks the
last applied ``state["tick"]`` and skips append-style merges when the
incoming tick is not strictly newer. Replace-style merges are
idempotent under same-tick redelivery and stay enabled.
"""

from __future__ import annotations

from typing import Any

# (delta_field, cumulative_field). When a delta carries `delta_field`
# (a list-of-lists parallel to the cumulative `cumulative_field`), the
# accumulator extends each inner list element-wise.
_APPEND_RULES: tuple[tuple[str, str], ...] = (
    ("trail_delta", "trails"),  # Curve
)

# (delta_field, cumulative_field) for *flat* lists. When a delta carries
# `delta_field` (a flat list), it is concatenated onto the flat
# `cumulative_field` list.
_FLAT_APPEND_RULES: tuple[tuple[str, str], ...] = (
    ("history_delta", "history"),  # Poker
)


class StateAccumulator:
    """Per-session cumulative state for the WS client.

    Lifecycle: one instance per match. ``reset()`` between matches.
    """

    __slots__ = ("_state", "_tick")

    def __init__(self) -> None:
        self._state: dict[str, Any] = {}
        self._tick: int = -1

    def reset(self) -> None:
        self._state = {}
        self._tick = -1

    @property
    def current(self) -> dict[str, Any]:
        """The reconstructed full state as the bot/renderer should see it."""
        return self._state

    def on_snapshot(self, state: dict[str, Any]) -> dict[str, Any]:
        """Replace the cumulative state with a full snapshot — used for
        `game_start` and `game_end`. Returns the new cumulative state."""
        # Deep copy the append-target lists so subsequent in-place
        # extends don't mutate the caller's dict (and so we own the
        # cumulative copy independently of the message object).
        new_state = dict(state)
        for _, base_key in _APPEND_RULES:
            base = new_state.get(base_key)
            if isinstance(base, list):
                new_state[base_key] = [
                    list(inner) if isinstance(inner, list) else inner
                    for inner in base
                ]
        for _, base_key in _FLAT_APPEND_RULES:
            base = new_state.get(base_key)
            if isinstance(base, list):
                new_state[base_key] = list(base)
        self._state = new_state
        tick = state.get("tick")
        self._tick = int(tick) if isinstance(tick, int) else -1
        return self._state

    def on_delta(self, delta: dict[str, Any]) -> dict[str, Any]:
        """Merge a per-tick delta into the cumulative state. Returns the
        cumulative state after merge.

        Append-style merges are gated on the incoming ``tick`` being
        strictly newer than the last applied one — this is the same-tick
        dedup that lets the server emit identical views via
        `tick_request` (pre-step) and `tick_result` (post-step) without
        the client double-appending.
        """
        incoming_tick_raw = delta.get("tick")
        incoming_tick = (
            int(incoming_tick_raw) if isinstance(incoming_tick_raw, int) else None
        )
        advancing = incoming_tick is None or incoming_tick > self._tick

        for key, value in delta.items():
            self._state[key] = value

        if advancing:
            for delta_key, base_key in _APPEND_RULES:
                additions = delta.get(delta_key)
                if not isinstance(additions, list):
                    continue
                base = self._state.get(base_key)
                if (
                    isinstance(base, list)
                    and len(base) == len(additions)
                    and all(isinstance(inner, list) for inner in base)
                    and all(isinstance(inner, list) for inner in additions)
                ):
                    for i, segs in enumerate(additions):
                        base[i].extend(segs)
            for delta_key, base_key in _FLAT_APPEND_RULES:
                additions = delta.get(delta_key)
                if not isinstance(additions, list):
                    continue
                base = self._state.get(base_key)
                if isinstance(base, list):
                    base.extend(additions)

        if advancing and incoming_tick is not None:
            self._tick = incoming_tick

        return self._state
