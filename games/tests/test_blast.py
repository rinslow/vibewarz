"""Blast engine tests."""

from __future__ import annotations

import pytest
from vibewarz_games import GAMES
from vibewarz_games.blast.board import BOARD_H, BOARD_W
from vibewarz_games.blast.game import (
    BOMB_CAP,
    BOMB_FUSE,
    FLAME_LIFETIME,
    MAX_TICKS,
    MIN_COOLDOWN,
    RANGE_CAP,
    SHRINK_START_TICK,
    STARTING_BOMBS_MAX,
    STARTING_COOLDOWN,
    STARTING_RANGE,
    Blast,
)


@pytest.fixture
def blast() -> Blast:
    return Blast()


def _stay(num_players: int = 4) -> dict[int, dict]:
    return {s: {"move": "stay", "drop_bomb": False} for s in range(num_players)}


def _isolate_seats(state: dict, positions: dict[int, tuple[int, int]]) -> None:
    """Force-place seats at given tiles, marking everyone else dead and clearing
    soft blocks on their path so individual mechanics can be tested in
    isolation. ``positions`` keys are the seats kept alive."""
    for p in state["players"]:
        seat = p["seat"]
        if seat in positions:
            x, y = positions[seat]
            p["x"], p["y"] = x, y
            p["alive"] = True
            p["move_cooldown_remaining"] = 0
        else:
            p["alive"] = False
            if seat not in state["placement"]:
                state["placement"].append(seat)


def _clear_radius(state: dict, x: int, y: int, r: int = 4) -> None:
    """Wipe soft blocks in a square around (x, y) so they don't interfere
    with movement-related test setups."""
    for yy in range(max(1, y - r), min(BOARD_H - 1, y + r + 1)):
        for xx in range(max(1, x - r), min(BOARD_W - 1, x + r + 1)):
            if state["board"][yy][xx] == "soft":
                state["board"][yy][xx] = "empty"


# ── registration & shape ───────────────────────────────────────────────────


def test_registered_in_global_registry() -> None:
    assert "blast" in GAMES
    assert GAMES["blast"] is Blast


def test_initial_state_shape(blast: Blast) -> None:
    state = blast.initial_state(seed=42, num_players=4)
    assert state["tick"] == 0
    assert state["dims"] == {"w": BOARD_W, "h": BOARD_H}
    assert len(state["players"]) == 4
    assert state["bombs"] == []
    assert state["flames"] == []
    assert state["powerups"] == []
    assert state["placement"] == []
    for seat, p in enumerate(state["players"]):
        assert p["seat"] == seat
        assert p["alive"]
        assert p["bombs_max"] == STARTING_BOMBS_MAX
        assert p["blast_range"] == STARTING_RANGE
        assert p["move_cooldown"] == STARTING_COOLDOWN


def test_initial_state_is_seeded(blast: Blast) -> None:
    a = blast.initial_state(seed=7, num_players=4)
    b = blast.initial_state(seed=7, num_players=4)
    c = blast.initial_state(seed=8, num_players=4)
    assert a["board"] == b["board"]
    assert a["board"] != c["board"]


def test_wrong_player_count(blast: Blast) -> None:
    with pytest.raises(ValueError):
        blast.initial_state(seed=1, num_players=1)
    with pytest.raises(ValueError):
        blast.initial_state(seed=1, num_players=5)


def test_alive_seats(blast: Blast) -> None:
    state = blast.initial_state(seed=1, num_players=4)
    assert blast.alive_seats(state) == [0, 1, 2, 3]
    state["players"][1]["alive"] = False
    assert blast.alive_seats(state) == [0, 2, 3]


# ── action validation ──────────────────────────────────────────────────────


def test_legal_actions_full_with_capacity(blast: Blast) -> None:
    state = blast.initial_state(seed=1, num_players=4)
    actions = blast.legal_actions(state, seat=0)
    # 5 moves × {drop, no-drop} = 10 actions when bomb-drop is legal.
    assert len(actions) == 10
    pairs = {(a["move"], a["drop_bomb"]) for a in actions}
    assert ("stay", True) in pairs
    assert ("up", False) in pairs


def test_legal_actions_drop_gated_by_capacity(blast: Blast) -> None:
    state = blast.initial_state(seed=1, num_players=4)
    state["players"][0]["bombs_active"] = state["players"][0]["bombs_max"]
    actions = blast.legal_actions(state, seat=0)
    assert all(not a["drop_bomb"] for a in actions)
    assert len(actions) == 5


def test_legal_actions_drop_gated_by_bomb_on_tile(blast: Blast) -> None:
    state = blast.initial_state(seed=1, num_players=4)
    p = state["players"][0]
    state["bombs"].append(
        {"x": p["x"], "y": p["y"], "timer": 10, "owner": 0, "range": 2}
    )
    actions = blast.legal_actions(state, seat=0)
    assert all(not a["drop_bomb"] for a in actions)


def test_is_legal_shape_rejection(blast: Blast) -> None:
    state = blast.initial_state(seed=1, num_players=4)
    assert blast.is_legal(state, 0, {"move": "up", "drop_bomb": False})
    assert not blast.is_legal(state, 0, "up")  # type: ignore[arg-type]
    assert not blast.is_legal(state, 0, {"move": "diagonal"})
    assert not blast.is_legal(state, 0, {"move": "up", "drop_bomb": "yes"})


def test_default_action_is_safe(blast: Blast) -> None:
    state = blast.initial_state(seed=1, num_players=4)
    assert blast.default_action(state, 0) == {"move": "stay", "drop_bomb": False}


# ── movement ───────────────────────────────────────────────────────────────


def test_step_advances_tick_without_mutation(blast: Blast) -> None:
    state = blast.initial_state(seed=1, num_players=4)
    snap_tick = state["tick"]
    snap_p0 = {**state["players"][0], "powerup_counts": dict(state["players"][0]["powerup_counts"])}
    snap_board = [row[:] for row in state["board"]]
    res = blast.step(state, _stay())
    assert res.state["tick"] == 1
    assert state["tick"] == snap_tick
    assert state["players"][0] == snap_p0
    assert state["board"] == snap_board


def test_move_into_hard_wall_is_silent_no_op(blast: Blast) -> None:
    state = blast.initial_state(seed=1, num_players=4)
    p = state["players"][0]
    # seat 0 at (1, 1); moving up bumps into the (1, 0) border wall.
    res = blast.step(
        state,
        {
            0: {"move": "up", "drop_bomb": False},
            1: {"move": "stay", "drop_bomb": False},
            2: {"move": "stay", "drop_bomb": False},
            3: {"move": "stay", "drop_bomb": False},
        },
    )
    assert (res.state["players"][0]["x"], res.state["players"][0]["y"]) == (p["x"], p["y"])


def test_move_succeeds_into_empty_tile(blast: Blast) -> None:
    state = blast.initial_state(seed=1, num_players=4)
    _isolate_seats(state, {0: (5, 5), 1: (10, 9)})
    _clear_radius(state, 5, 5, r=1)
    res = blast.step(
        state,
        {0: {"move": "right", "drop_bomb": False}, 1: {"move": "stay", "drop_bomb": False}},
    )
    assert (res.state["players"][0]["x"], res.state["players"][0]["y"]) == (6, 5)


def test_movement_cooldown_skips_alternate_ticks(blast: Blast) -> None:
    state = blast.initial_state(seed=1, num_players=4)
    _isolate_seats(state, {0: (5, 5), 1: (10, 9)})
    _clear_radius(state, 5, 5, r=3)
    # default cooldown=2 → move every other tick.
    actions = {
        0: {"move": "right", "drop_bomb": False},
        1: {"move": "stay", "drop_bomb": False},
    }
    r1 = blast.step(state, actions)
    assert (r1.state["players"][0]["x"], r1.state["players"][0]["y"]) == (6, 5)
    r2 = blast.step(r1.state, actions)
    # cooldown ticking — still on (6, 5)
    assert (r2.state["players"][0]["x"], r2.state["players"][0]["y"]) == (6, 5)
    r3 = blast.step(r2.state, actions)
    assert (r3.state["players"][0]["x"], r3.state["players"][0]["y"]) == (7, 5)


def test_speed_powerup_lets_player_move_every_tick(blast: Blast) -> None:
    state = blast.initial_state(seed=1, num_players=4)
    _isolate_seats(state, {0: (5, 5), 1: (10, 9)})
    _clear_radius(state, 5, 5, r=3)
    state["players"][0]["move_cooldown"] = MIN_COOLDOWN
    actions = {
        0: {"move": "right", "drop_bomb": False},
        1: {"move": "stay", "drop_bomb": False},
    }
    r1 = blast.step(state, actions)
    r2 = blast.step(r1.state, actions)
    assert (r1.state["players"][0]["x"], r1.state["players"][0]["y"]) == (6, 5)
    assert (r2.state["players"][0]["x"], r2.state["players"][0]["y"]) == (7, 5)


def test_simultaneous_same_tile_contention_lowest_seat_wins(blast: Blast) -> None:
    state = blast.initial_state(seed=1, num_players=4)
    _isolate_seats(state, {0: (5, 5), 1: (7, 5)})
    _clear_radius(state, 6, 5, r=2)
    # both want (6, 5) — seat 0 should win, seat 1 stays.
    res = blast.step(
        state,
        {
            0: {"move": "right", "drop_bomb": False},
            1: {"move": "left", "drop_bomb": False},
        },
    )
    p0, p1 = res.state["players"][0], res.state["players"][1]
    assert (p0["x"], p0["y"]) == (6, 5)
    assert (p1["x"], p1["y"]) == (7, 5)


# ── bombs ──────────────────────────────────────────────────────────────────


def test_drop_bomb_places_bomb_at_pre_move_tile(blast: Blast) -> None:
    state = blast.initial_state(seed=1, num_players=4)
    _isolate_seats(state, {0: (5, 5), 1: (10, 9)})
    _clear_radius(state, 5, 5, r=2)
    res = blast.step(
        state,
        {
            0: {"move": "right", "drop_bomb": True},
            1: {"move": "stay", "drop_bomb": False},
        },
    )
    assert len(res.state["bombs"]) == 1
    bomb = res.state["bombs"][0]
    assert (bomb["x"], bomb["y"]) == (5, 5)
    assert bomb["owner"] == 0
    # Drop resolves AFTER bomb-fuse aging, so a freshly placed bomb keeps
    # its full fuse going into the next tick.
    assert bomb["timer"] == BOMB_FUSE
    # player moved off the bomb
    assert (res.state["players"][0]["x"], res.state["players"][0]["y"]) == (6, 5)


def test_bomb_explodes_after_fuse_and_kills_player(blast: Blast) -> None:
    state = blast.initial_state(seed=1, num_players=4)
    _isolate_seats(state, {0: (5, 5), 1: (10, 9)})
    _clear_radius(state, 5, 5, r=3)
    state["bombs"].append(
        {"x": 6, "y": 5, "timer": 1, "owner": 0, "range": 2}
    )
    res = blast.step(
        state,
        {0: {"move": "right", "drop_bomb": False}, 1: {"move": "stay", "drop_bomb": False}},
    )
    # bomb at (6,5) exploded this tick; seat 0 walked into the flame at (6,5).
    assert res.state["bombs"] == []
    assert any(f["x"] == 6 and f["y"] == 5 for f in res.state["flames"])
    assert not res.state["players"][0]["alive"]
    assert 0 in res.eliminated_this_tick


def test_chain_reaction_detonates_neighbour_bomb(blast: Blast) -> None:
    state = blast.initial_state(seed=1, num_players=4)
    _isolate_seats(state, {0: (5, 5), 1: (10, 9)})
    _clear_radius(state, 5, 5, r=3)
    # bomb A about to explode at (5,5). bomb B at (7,5) with full fuse —
    # should chain via the flame on (7,5).
    state["bombs"].append({"x": 5, "y": 5, "timer": 1, "owner": 0, "range": 3})
    state["bombs"].append({"x": 7, "y": 5, "timer": BOMB_FUSE, "owner": 0, "range": 2})
    res = blast.step(
        state,
        {0: {"move": "stay", "drop_bomb": False}, 1: {"move": "stay", "drop_bomb": False}},
    )
    assert res.state["bombs"] == []
    flame_set = {(f["x"], f["y"]) for f in res.state["flames"]}
    # bomb A's range covers up to (8,5); chain from B extends the rightward
    # reach to (9,5).
    assert (8, 5) in flame_set
    assert (9, 5) in flame_set


def test_flame_destroys_soft_block(blast: Blast) -> None:
    state = blast.initial_state(seed=1, num_players=4)
    _isolate_seats(state, {0: (5, 5), 1: (10, 9)})
    _clear_radius(state, 5, 5, r=3)
    state["board"][5][7] = "soft"  # board[y][x]
    state["bombs"].append({"x": 5, "y": 5, "timer": 1, "owner": 0, "range": 3})
    res = blast.step(state, _stay())
    assert res.state["board"][5][7] == "empty"


def test_spawned_powerups_survive_the_flame_that_revealed_them(
    blast: Blast,
) -> None:
    """Regression: powerups dropped from a destroyed soft block must NOT
    be wiped by the flame-vs-powerup filter on the same tick — otherwise
    no powerup ever appears."""
    # Detonate a long line of soft blocks. With 12 destructions at 30%
    # drop rate, the probability of zero spawns is (0.7)^12 ≈ 1.4% — small
    # enough across seeds to be reliable.
    sightings: list[int] = []
    for seed in range(8):
        state = blast.initial_state(seed=seed, num_players=4)
        _isolate_seats(state, {0: (1, 5), 1: (11, 9)})
        # Wipe interior pillars on row 5 and pave it with soft blocks.
        for x in range(2, BOARD_W - 1):
            state["board"][5][x] = "soft"
        state["board"][5][1] = "empty"  # seat 0 stands here
        state["bombs"].append(
            {"x": 1, "y": 5, "timer": 1, "owner": 0, "range": 10}
        )
        res = blast.step(state, _stay())
        sightings.append(len(res.state["powerups"]))
    assert any(n > 0 for n in sightings), f"no powerups ever spawned: {sightings}"


def test_powerup_pickup_increments_capacity(blast: Blast) -> None:
    state = blast.initial_state(seed=1, num_players=4)
    _isolate_seats(state, {0: (5, 5), 1: (10, 9)})
    _clear_radius(state, 6, 5, r=1)
    state["powerups"].append({"id": "pu0", "x": 6, "y": 5, "kind": "bomb"})
    state["next_powerup_id"] = 1
    before = state["players"][0]["bombs_max"]
    res = blast.step(
        state,
        {0: {"move": "right", "drop_bomb": False}, 1: {"move": "stay", "drop_bomb": False}},
    )
    assert res.state["powerups"] == []
    assert res.state["players"][0]["bombs_max"] == before + 1
    assert res.state["players"][0]["powerup_counts"]["bomb"] == 1


def test_powerup_cap_respected(blast: Blast) -> None:
    state = blast.initial_state(seed=1, num_players=4)
    _isolate_seats(state, {0: (5, 5), 1: (10, 9)})
    _clear_radius(state, 6, 5, r=1)
    state["players"][0]["bombs_max"] = BOMB_CAP
    state["powerups"].append({"id": "pu0", "x": 6, "y": 5, "kind": "bomb"})
    res = blast.step(
        state,
        {0: {"move": "right", "drop_bomb": False}, 1: {"move": "stay", "drop_bomb": False}},
    )
    assert res.state["players"][0]["bombs_max"] == BOMB_CAP


# ── sudden death & end conditions ──────────────────────────────────────────


def test_sudden_death_ring_kills_player_on_outer_tile(blast: Blast) -> None:
    state = blast.initial_state(seed=1, num_players=4)
    _isolate_seats(state, {0: (1, 1), 1: (5, 5)})
    _clear_radius(state, 5, 5, r=2)
    # Skip straight to the first shrink-ring trigger.
    state["tick"] = SHRINK_START_TICK - 1
    res = blast.step(state, _stay())
    # Ring 1 = the cells one step inside the border, including (1, 1).
    assert res.state["board"][1][1] == "hard"
    assert not res.state["players"][0]["alive"]
    assert 0 in res.eliminated_this_tick


def test_game_ends_with_last_survivor_first(blast: Blast) -> None:
    state = blast.initial_state(seed=1, num_players=4)
    # seats 2 then 1 then 3 died; seat 0 alive.
    for seat in (2, 1, 3):
        state["players"][seat]["alive"] = False
        state["placement"].append(seat)
    res = blast.step(state, {0: {"move": "stay", "drop_bomb": False}})
    assert res.done
    assert res.placement == [0, 3, 1, 2]
    assert res.reason == "elimination"


def test_timeout_at_max_ticks(blast: Blast) -> None:
    state = blast.initial_state(seed=1, num_players=4)
    state["tick"] = MAX_TICKS - 1
    # All four alive — step pushes tick to MAX_TICKS and must terminate.
    res = blast.step(state, _stay())
    assert res.done
    assert res.reason == "timeout"
    assert res.placement is not None
    assert sorted(res.placement) == [0, 1, 2, 3]


# ── determinism ────────────────────────────────────────────────────────────


def test_step_is_deterministic(blast: Blast) -> None:
    s1 = blast.initial_state(seed=99, num_players=4)
    s2 = blast.initial_state(seed=99, num_players=4)
    actions = {
        0: {"move": "right", "drop_bomb": True},
        1: {"move": "left", "drop_bomb": False},
        2: {"move": "down", "drop_bomb": False},
        3: {"move": "up", "drop_bomb": True},
    }
    for _ in range(80):
        r1 = blast.step(s1, actions)
        r2 = blast.step(s2, actions)
        assert r1.state["players"] == r2.state["players"]
        assert r1.state["board"] == r2.state["board"]
        assert r1.state["bombs"] == r2.state["bombs"]
        assert r1.state["flames"] == r2.state["flames"]
        assert r1.state["powerups"] == r2.state["powerups"]
        s1, s2 = r1.state, r2.state
        if r1.done:
            break


# ── miscellaneous constants sanity ─────────────────────────────────────────


def test_flame_lifetime_positive() -> None:
    assert FLAME_LIFETIME >= 1


def test_caps_are_sane() -> None:
    assert BOMB_CAP >= STARTING_BOMBS_MAX
    assert RANGE_CAP >= STARTING_RANGE
