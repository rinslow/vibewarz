"""Tests for the client-side state accumulator.

Wire contract:
  - `GameStartS2C` / `GameEndS2C` carry a full snapshot.
  - `TickRequestS2C` / `TickResultS2C` carry per-tick deltas.
  - Most fields are full-replace; per-game append rules in
    `state_accumulator._APPEND_RULES` are applied element-wise.
  - Same-tick deltas (server sends one in tick_request pre-step and
    again in tick_result post-step when the state hasn't advanced)
    don't double-apply append rules.

End-to-end correctness against the real Curve engine is exercised in
the vibewarz-games test suite (see `test_curve.py::
test_apply_deltas_reconstructs_authoritative_trails`).
"""

from __future__ import annotations

from vibewarz.state_accumulator import StateAccumulator


def test_snapshot_replaces_state() -> None:
    acc = StateAccumulator()
    acc.on_snapshot({"tick": 0, "players": [{"x": 1}], "trails": [[(0.0, 0.0)]]})
    assert acc.current["tick"] == 0
    assert acc.current["trails"] == [[(0.0, 0.0)]]

    acc.on_snapshot({"tick": 0, "players": [{"x": 9}], "trails": [[(5.0, 5.0)]]})
    assert acc.current["players"] == [{"x": 9}]
    assert acc.current["trails"] == [[(5.0, 5.0)]]


def test_snapshot_deep_copies_append_targets() -> None:
    """Subsequent on_delta extends must not mutate the caller's dict."""
    snapshot = {"tick": 0, "trails": [[(0.0, 0.0)]], "trail_delta": [[(0.0, 0.0)]]}
    acc = StateAccumulator()
    acc.on_snapshot(snapshot)
    acc.on_delta({"tick": 1, "trail_delta": [[(1.0, 1.0)]]})
    # caller's snapshot is untouched
    assert snapshot["trails"] == [[(0.0, 0.0)]]
    # accumulator's cumulative trails reflects the appended delta
    assert acc.current["trails"] == [[(0.0, 0.0), (1.0, 1.0)]]


def test_delta_replaces_regular_keys() -> None:
    acc = StateAccumulator()
    acc.on_snapshot({"tick": 0, "score": 0, "players": [{"alive": True}]})
    acc.on_delta({"tick": 1, "score": 7})
    assert acc.current["score"] == 7
    assert acc.current["players"] == [{"alive": True}]


def test_delta_appends_per_player_trail_delta_onto_trails() -> None:
    """Curve append rule: trail_delta is appended element-wise onto trails."""
    acc = StateAccumulator()
    acc.on_snapshot(
        {
            "tick": 0,
            "trails": [[(0.0, 0.0)], [(10.0, 10.0)]],
            "trail_delta": [[(0.0, 0.0)], [(10.0, 10.0)]],
        }
    )
    acc.on_delta({"tick": 1, "trail_delta": [[(1.0, 1.0)], [(11.0, 11.0)]]})
    acc.on_delta({"tick": 2, "trail_delta": [[(2.0, 2.0)], []]})
    assert acc.current["trails"] == [
        [(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)],
        [(10.0, 10.0), (11.0, 11.0)],
    ]
    # Latest raw delta is also accessible for consumers that want it.
    assert acc.current["trail_delta"] == [[(2.0, 2.0)], []]


def test_same_tick_delta_does_not_double_append() -> None:
    """Server sends the same view via tick_request (pre-step) and
    tick_result (post-step) — the accumulator must not double-append."""
    acc = StateAccumulator()
    acc.on_snapshot(
        {
            "tick": 0,
            "trails": [[(0.0, 0.0)]],
            "trail_delta": [[(0.0, 0.0)]],
        }
    )
    acc.on_delta({"tick": 0, "trail_delta": [[(0.0, 0.0)]]})  # redundant
    acc.on_delta({"tick": 0, "trail_delta": [[(0.0, 0.0)]]})  # redundant
    assert acc.current["trails"] == [[(0.0, 0.0)]]

    acc.on_delta({"tick": 1, "trail_delta": [[(1.0, 1.0)]]})
    acc.on_delta({"tick": 1, "trail_delta": [[(1.0, 1.0)]]})  # redundant
    assert acc.current["trails"] == [[(0.0, 0.0), (1.0, 1.0)]]


def test_delta_without_tick_field_still_applies_appends() -> None:
    """No `tick` field → the accumulator can't dedup, so it conservatively
    treats every delta as advancing. Test fixtures and ad-hoc tooling
    benefit; production server payloads always carry tick."""
    acc = StateAccumulator()
    acc.on_snapshot({"trails": [[(0.0, 0.0)]], "trail_delta": [[(0.0, 0.0)]]})
    acc.on_delta({"trail_delta": [[(1.0, 1.0)]]})
    acc.on_delta({"trail_delta": [[(2.0, 2.0)]]})
    assert acc.current["trails"] == [[(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)]]


def test_shape_mismatch_skips_append() -> None:
    """If trail_delta's outer length doesn't match cumulative trails',
    skip the append — the delta key is still stored as a regular replace
    so downstream consumers see something."""
    acc = StateAccumulator()
    acc.on_snapshot({"trails": [[1.0], [2.0]], "trail_delta": [[1.0], [2.0]]})
    acc.on_delta({"tick": 1, "trail_delta": [[3.0]]})  # outer length 1, not 2
    assert acc.current["trails"] == [[1.0], [2.0]]
    assert acc.current["trail_delta"] == [[3.0]]


def test_reset_clears_state() -> None:
    acc = StateAccumulator()
    acc.on_snapshot({"tick": 0, "trails": [[(0.0, 0.0)]]})
    acc.on_delta({"tick": 1, "trail_delta": [[(1.0, 1.0)]]})
    acc.reset()
    assert acc.current == {}
    acc.on_snapshot({"tick": 0, "trails": [[(5.0, 5.0)]]})
    assert acc.current["trails"] == [[(5.0, 5.0)]]
