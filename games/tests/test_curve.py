"""Curve engine tests."""

from __future__ import annotations

import pytest
from vibewarz_games import GAMES
from vibewarz_games.curve.game import (
    ARENA_H,
    ARENA_W,
    POWERUP_DURATION,
    POWERUP_KINDS,
    POWERUP_SPAWN_INTERVAL,
    SLOW_FACTOR,
    SPEED,
    SPEED_BOOST_FACTOR,
    Curve,
)


@pytest.fixture
def curve() -> Curve:
    return Curve()


def test_registered_in_global_registry() -> None:
    assert "curve" in GAMES
    assert GAMES["curve"] is Curve


def test_initial_state_shape(curve: Curve) -> None:
    state = curve.initial_state(seed=42, num_players=4)
    assert state["tick"] == 0
    assert state["arena"] == {"w": ARENA_W, "h": ARENA_H}
    assert len(state["players"]) == 4
    assert all(p["alive"] for p in state["players"])
    for seat, p in enumerate(state["players"]):
        assert p["seat"] == seat
        assert 0.0 <= p["x"] <= ARENA_W
        assert 0.0 <= p["y"] <= ARENA_H
        assert 0.0 <= p["heading_deg"] <= 360.0
    assert len(state["trails"]) == 4
    assert all(len(t) == 1 for t in state["trails"])


def test_initial_state_is_seeded(curve: Curve) -> None:
    a = curve.initial_state(seed=123, num_players=4)
    b = curve.initial_state(seed=123, num_players=4)
    c = curve.initial_state(seed=124, num_players=4)
    assert [(p["x"], p["y"], p["heading_deg"]) for p in a["players"]] == [
        (p["x"], p["y"], p["heading_deg"]) for p in b["players"]
    ]
    assert [(p["x"], p["y"], p["heading_deg"]) for p in a["players"]] != [
        (p["x"], p["y"], p["heading_deg"]) for p in c["players"]
    ]


def test_wrong_player_count(curve: Curve) -> None:
    with pytest.raises(ValueError):
        curve.initial_state(seed=1, num_players=2)
    with pytest.raises(ValueError):
        curve.initial_state(seed=1, num_players=5)


def test_legal_actions(curve: Curve) -> None:
    state = curve.initial_state(seed=1, num_players=4)
    legal = curve.legal_actions(state, seat=0)
    turns = {a["turn"] for a in legal}
    assert turns == {"LEFT", "STRAIGHT", "RIGHT"}


def test_is_legal(curve: Curve) -> None:
    state = curve.initial_state(seed=1, num_players=4)
    assert curve.is_legal(state, 0, {"turn": "LEFT"})
    assert curve.is_legal(state, 0, {"turn": "STRAIGHT"})
    assert curve.is_legal(state, 0, {"turn": "RIGHT"})
    assert not curve.is_legal(state, 0, {"turn": "BACKWARDS"})
    assert not curve.is_legal(state, 0, {})
    assert not curve.is_legal(state, 0, "STRAIGHT")  # type: ignore[arg-type]


def test_default_action_is_straight(curve: Curve) -> None:
    state = curve.initial_state(seed=1, num_players=4)
    assert curve.default_action(state, 0) == {"turn": "STRAIGHT"}


def test_step_advances_position(curve: Curve) -> None:
    state = curve.initial_state(seed=7, num_players=4)
    p0 = state["players"][0]
    res = curve.step(state, {s: {"turn": "STRAIGHT"} for s in range(4)})
    p1 = res.state["players"][0]
    assert res.state["tick"] == 1
    # head advanced by SPEED in direction `heading_deg`
    assert abs(((p1["x"] - p0["x"]) ** 2 + (p1["y"] - p0["y"]) ** 2) ** 0.5 - SPEED) < 1e-6
    # heading unchanged for STRAIGHT
    assert p1["heading_deg"] == p0["heading_deg"]
    # trail grew by 1
    assert len(res.state["trails"][0]) == 2


def test_step_turning_changes_heading(curve: Curve) -> None:
    state = curve.initial_state(seed=7, num_players=4)
    p0_h = state["players"][0]["heading_deg"]
    res = curve.step(state, {0: {"turn": "LEFT"}, 1: {"turn": "RIGHT"}, 2: {"turn": "STRAIGHT"}, 3: {"turn": "STRAIGHT"}})
    assert (res.state["players"][0]["heading_deg"] - (p0_h - 6.0)) % 360.0 < 1e-6
    assert (res.state["players"][1]["heading_deg"] - (state["players"][1]["heading_deg"] + 6.0)) % 360.0 < 1e-6


def test_wall_collision_kills_player(curve: Curve) -> None:
    state = curve.initial_state(seed=1, num_players=4)
    # place seat 0 facing right one step from the right wall
    state["players"][0]["x"] = ARENA_W - 1.0
    state["players"][0]["y"] = 500.0
    state["players"][0]["heading_deg"] = 0.0
    state["trails"][0] = [(state["players"][0]["x"], state["players"][0]["y"])]
    res = curve.step(state, {s: {"turn": "STRAIGHT"} for s in range(4)})
    assert not res.state["players"][0]["alive"]
    assert 0 in res.eliminated_this_tick


def test_head_on_collision_kills_both(curve: Curve) -> None:
    state = curve.initial_state(seed=1, num_players=4)
    # Put seats 0 and 1 head-on, far from others
    state["players"][0]["x"] = 500.0
    state["players"][0]["y"] = 500.0
    state["players"][0]["heading_deg"] = 0.0
    state["trails"][0] = [(500.0, 500.0)]
    state["players"][1]["x"] = 500.0 + SPEED * 0.5  # half a tick away facing left
    state["players"][1]["y"] = 500.0
    state["players"][1]["heading_deg"] = 180.0
    state["trails"][1] = [(state["players"][1]["x"], state["players"][1]["y"])]
    # move others out of the way
    state["players"][2]["x"] = 100.0
    state["players"][2]["y"] = 100.0
    state["players"][3]["x"] = 900.0
    state["players"][3]["y"] = 900.0
    state["trails"][2] = [(100.0, 100.0)]
    state["trails"][3] = [(900.0, 900.0)]
    res = curve.step(state, {s: {"turn": "STRAIGHT"} for s in range(4)})
    assert not res.state["players"][0]["alive"]
    assert not res.state["players"][1]["alive"]


def test_game_ends_when_one_left(curve: Curve) -> None:
    state = curve.initial_state(seed=1, num_players=4)
    # Kill seats 1, 2, 3 manually by walling them off — easier: mark them dead.
    for seat in (1, 2, 3):
        state["players"][seat]["alive"] = False
        state["placement"].append(seat)
    res = curve.step(state, {0: {"turn": "STRAIGHT"}})
    assert res.done
    assert res.placement is not None
    assert res.placement[0] == 0  # last survivor wins


def test_placement_order_reverses_death_order(curve: Curve) -> None:
    state = curve.initial_state(seed=1, num_players=4)
    # seat 2 died first, then seat 1, then seat 3. Seat 0 alive.
    for seat in (2, 1, 3):
        state["players"][seat]["alive"] = False
        state["placement"].append(seat)
    res = curve.step(state, {0: {"turn": "STRAIGHT"}})
    # Expected placement: [0 (winner), 3 (last to die), 1, 2 (first to die, last)]
    assert res.placement == [0, 3, 1, 2]


def test_step_is_deterministic(curve: Curve) -> None:
    s1 = curve.initial_state(seed=99, num_players=4)
    s2 = curve.initial_state(seed=99, num_players=4)
    actions = {0: {"turn": "LEFT"}, 1: {"turn": "STRAIGHT"}, 2: {"turn": "RIGHT"}, 3: {"turn": "STRAIGHT"}}
    for _ in range(50):
        r1 = curve.step(s1, actions)
        r2 = curve.step(s2, actions)
        assert r1.state["players"] == r2.state["players"]
        assert r1.state["trails"] == r2.state["trails"]
        s1, s2 = r1.state, r2.state
        if r1.done:
            break


def test_step_does_not_mutate_input(curve: Curve) -> None:
    state = curve.initial_state(seed=11, num_players=4)
    snapshot_tick = state["tick"]
    snapshot_p0 = dict(state["players"][0])
    snapshot_trail0 = list(state["trails"][0])
    _ = curve.step(state, {s: {"turn": "STRAIGHT"} for s in range(4)})
    assert state["tick"] == snapshot_tick
    assert state["players"][0] == snapshot_p0
    assert state["trails"][0] == snapshot_trail0


def test_alive_seats(curve: Curve) -> None:
    state = curve.initial_state(seed=1, num_players=4)
    assert curve.alive_seats(state) == [0, 1, 2, 3]
    state["players"][1]["alive"] = False
    assert curve.alive_seats(state) == [0, 2, 3]


# ── powerups ───────────────────────────────────────────────────────────────


def _all_straight(num_players: int = 4) -> dict[int, dict]:
    return {s: {"turn": "STRAIGHT"} for s in range(num_players)}


def _isolate(state: dict, seat: int, x: float, y: float, heading: float) -> None:
    """Move a player to (x, y) with the given heading and reset its trail head."""
    state["players"][seat]["x"] = x
    state["players"][seat]["y"] = y
    state["players"][seat]["heading_deg"] = heading
    state["trails"][seat] = [(x, y)]


def test_state_carries_powerup_fields(curve: Curve) -> None:
    state = curve.initial_state(seed=42, num_players=4)
    assert state["powerups"] == []
    assert state["next_powerup_id"] == 0
    assert state["seed"] == 42
    for p in state["players"]:
        assert p["effects"] == {}


def test_view_for_never_leaks_seed(curve: Curve) -> None:
    """Curve uses the default `view_for` (no hidden info), but the seed
    must still be stripped: it drives deterministic powerup spawn coords,
    so a client that learns it can predict future spawn positions.
    """
    state = curve.initial_state(seed=42, num_players=4)
    assert state["seed"] == 42  # authoritative state retains it
    for seat in range(4):
        assert "seed" not in curve.view_for(state, seat)


def test_snapshot_view_for_carries_full_trails(curve: Curve) -> None:
    state = curve.initial_state(seed=42, num_players=4)
    for seat in range(4):
        view = curve.snapshot_view_for(state, seat)
        assert "seed" not in view
        assert view["trails"] == state["trails"]
        assert view["trail_delta"] == state["trail_delta"]


def test_delta_view_for_omits_trails_keeps_trail_delta(curve: Curve) -> None:
    """The whole point of the framework: per-tick view ships the
    constant-size `trail_delta`, never the cumulative `trails`."""
    state = curve.initial_state(seed=42, num_players=4)
    # Step a few ticks so trails grows past length 1
    for _ in range(5):
        state = curve.step(state, _all_straight()).state
    assert all(len(t) > 1 for t in state["trails"])  # cumulative growth happened
    for seat in range(4):
        view = curve.delta_view_for(state, seat)
        assert "seed" not in view
        assert "trails" not in view
        assert view["trail_delta"] == state["trail_delta"]


def test_apply_deltas_reconstructs_authoritative_trails(curve: Curve) -> None:
    """SDK accumulator semantics: client starts from `snapshot_view_for`
    at game_start and appends each tick's `trail_delta` element-wise onto
    its cumulative `trails`. After N ticks the client's reconstructed
    trails must equal the authoritative engine state's trails."""
    state = curve.initial_state(seed=42, num_players=4)
    client_view: dict = curve.snapshot_view_for(state, seat=0)
    # Defensive copy so we mutate the client view, not the engine state.
    client_trails: list[list[tuple[float, float]]] = [
        list(t) for t in client_view["trails"]
    ]

    for _ in range(40):
        state = curve.step(state, _all_straight()).state
        delta = curve.delta_view_for(state, seat=0)
        # SDK accumulator: append per-player trail_delta into cumulative trails.
        for i, segs in enumerate(delta["trail_delta"]):
            client_trails[i].extend(segs)

    assert client_trails == [list(t) for t in state["trails"]]


def test_powerup_spawns_at_interval(curve: Curve) -> None:
    state = curve.initial_state(seed=7, num_players=4)
    actions = _all_straight()
    for _ in range(POWERUP_SPAWN_INTERVAL):
        res = curve.step(state, actions)
        state = res.state
        if res.done:
            break
    # By the SPAWN_INTERVAL-th tick at least one powerup should have appeared,
    # though some may have already been picked up.
    assert state["tick"] == POWERUP_SPAWN_INTERVAL
    assert state["next_powerup_id"] >= 1


def test_powerup_spawn_is_deterministic(curve: Curve) -> None:
    s1 = curve.initial_state(seed=99, num_players=4)
    s2 = curve.initial_state(seed=99, num_players=4)
    actions = _all_straight()
    for _ in range(POWERUP_SPAWN_INTERVAL * 2):
        r1 = curve.step(s1, actions)
        r2 = curve.step(s2, actions)
        assert r1.state["powerups"] == r2.state["powerups"]
        assert r1.state["next_powerup_id"] == r2.state["next_powerup_id"]
        s1, s2 = r1.state, r2.state
        if r1.done:
            break


def test_speed_boost_increases_displacement(curve: Curve) -> None:
    state = curve.initial_state(seed=1, num_players=4)
    # seat 0 boosted, isolated facing right
    _isolate(state, 0, 200.0, 500.0, 0.0)
    state["players"][0]["effects"] = {"speed": 5}
    # move others far away to avoid interactions
    _isolate(state, 1, 800.0, 100.0, 180.0)
    _isolate(state, 2, 100.0, 100.0, 0.0)
    _isolate(state, 3, 900.0, 900.0, 90.0)
    p0_before = (state["players"][0]["x"], state["players"][0]["y"])
    res = curve.step(state, _all_straight())
    p0_after = res.state["players"][0]
    dx = p0_after["x"] - p0_before[0]
    expected = SPEED * SPEED_BOOST_FACTOR
    assert abs(dx - expected) < 1e-6
    # And the effect ticked down.
    assert res.state["players"][0]["effects"]["speed"] == 4


def test_slow_affects_only_others(curve: Curve) -> None:
    state = curve.initial_state(seed=1, num_players=4)
    _isolate(state, 0, 200.0, 500.0, 0.0)
    state["players"][0]["effects"] = {"slow": 5}
    _isolate(state, 1, 500.0, 200.0, 0.0)
    _isolate(state, 2, 100.0, 800.0, 0.0)
    _isolate(state, 3, 800.0, 800.0, 0.0)
    res = curve.step(state, _all_straight())
    # seat 0 carries slow → moves at base SPEED (slow doesn't slow self).
    assert abs((res.state["players"][0]["x"] - 200.0) - SPEED) < 1e-6
    # seats 1–3 are slowed.
    for seat in (1, 2, 3):
        moved = res.state["players"][seat]["x"] - state["players"][seat]["x"]
        assert abs(moved - SPEED * SLOW_FACTOR) < 1e-6


def test_god_mode_ignores_wall(curve: Curve) -> None:
    state = curve.initial_state(seed=1, num_players=4)
    _isolate(state, 0, ARENA_W - 1.0, 500.0, 0.0)
    state["players"][0]["effects"] = {"god": 5}
    _isolate(state, 1, 100.0, 100.0, 90.0)
    _isolate(state, 2, 100.0, 800.0, 90.0)
    _isolate(state, 3, 800.0, 100.0, 90.0)
    res = curve.step(state, _all_straight())
    assert res.state["players"][0]["alive"]
    # head walked past the wall — confirms the wall check was skipped.
    assert res.state["players"][0]["x"] > ARENA_W


def test_god_mode_ignores_trail(curve: Curve) -> None:
    state = curve.initial_state(seed=1, num_players=4)
    # seat 0 about to walk into seat 1's planted trail.
    _isolate(state, 0, 500.0, 500.0, 0.0)
    state["players"][0]["effects"] = {"god": 5}
    # seat 1's trail crosses seat 0's path
    state["players"][1]["alive"] = False
    state["trails"][1] = [(504.0, 480.0), (504.0, 520.0)]
    _isolate(state, 2, 100.0, 100.0, 0.0)
    _isolate(state, 3, 900.0, 900.0, 0.0)
    res = curve.step(state, _all_straight())
    assert res.state["players"][0]["alive"]
    # And god-mode still leaves a trail (others can crash into it).
    assert len(res.state["trails"][0]) == 2


def test_pickup_consumes_powerup_and_applies_effect(curve: Curve) -> None:
    state = curve.initial_state(seed=1, num_players=4)
    _isolate(state, 0, 500.0, 500.0, 0.0)
    # place a speed pickup one step ahead of seat 0
    state["powerups"] = [{"id": "p0", "kind": "speed", "x": 500.0 + SPEED, "y": 500.0}]
    state["next_powerup_id"] = 1
    _isolate(state, 1, 100.0, 100.0, 90.0)
    _isolate(state, 2, 900.0, 100.0, 90.0)
    _isolate(state, 3, 100.0, 900.0, 90.0)
    res = curve.step(state, _all_straight())
    assert res.state["powerups"] == []
    assert res.state["players"][0]["effects"]["speed"] == POWERUP_DURATION["speed"]


def test_effect_expires_after_duration(curve: Curve) -> None:
    state = curve.initial_state(seed=1, num_players=4)
    state["players"][0]["effects"] = {"speed": 1}
    res = curve.step(state, _all_straight())
    assert "speed" not in res.state["players"][0]["effects"]


def test_powerup_kinds_constant() -> None:
    assert set(POWERUP_KINDS) == {"speed", "slow", "god"}
    assert set(POWERUP_DURATION) == set(POWERUP_KINDS)
