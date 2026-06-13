"""Rock Paper Scissors engine tests."""

from __future__ import annotations

import json

import pytest
from vibewarz_games import GAMES
from vibewarz_games.rock_paper_scissors.game import (
    BLUE,
    RED,
    RockPaperScissors,
    from_algebraic,
)


@pytest.fixture
def rps() -> RockPaperScissors:
    return RockPaperScissors()


def _setup_both(engine: RockPaperScissors, state: dict) -> dict:
    return engine.step(
        state,
        {
            RED: engine.default_action(state, RED),
            BLUE: engine.default_action(state, BLUE),
        },
    ).state


def _empty_play_state(engine: RockPaperScissors) -> dict:
    state = _setup_both(engine, engine.initial_state(seed=1, num_players=2))
    state["board"]["squares"] = [None] * 64
    state["phase"] = "play"
    state["current_turn"] = RED
    state["winner"] = None
    state["placement"] = []
    return state


def _piece(piece_type: str, color: int) -> dict:
    return {"type": piece_type, "color": color, "visible_to_enemy": False}


def test_registered_in_global_registry() -> None:
    assert "rock-paper-scissors" in GAMES
    assert GAMES["rock-paper-scissors"] is RockPaperScissors


def test_initial_state_shape_and_setup_transition(rps: RockPaperScissors) -> None:
    state = rps.initial_state(seed=42, num_players=2)
    assert state["phase"] == "setup"
    assert state["current_turn"] == RED
    assert len(state["board"]["squares"]) == 64
    assert [p["type"] for p in state["board"]["squares"][:16]].count("unassigned") == 16
    assert [p["type"] for p in state["board"]["squares"][48:]].count("unassigned") == 16
    assert rps.acting_seats(state) == [RED, BLUE]

    result = rps.step(
        state,
        {
            RED: rps.default_action(state, RED),
            BLUE: rps.default_action(state, BLUE),
        },
    )

    assert result.state["phase"] == "play"
    assert result.state["tick"] == 1
    assert rps.acting_seats(result.state) == [RED]
    json.dumps(result.state)


def test_wrong_player_count(rps: RockPaperScissors) -> None:
    with pytest.raises(ValueError):
        rps.initial_state(seed=1, num_players=1)
    with pytest.raises(ValueError):
        rps.initial_state(seed=1, num_players=3)


def test_view_for_hides_enemy_piece_types(rps: RockPaperScissors) -> None:
    state = _setup_both(rps, rps.initial_state(seed=1, num_players=2))
    view = rps.view_for(state, RED)

    assert "seed" not in view
    assert view["board"]["squares"][0]["type"] == "flag"
    assert view["board"]["squares"][63] == {
        "type": "hidden",
        "color": BLUE,
        "visible_to_enemy": False,
    }

    state["board"]["squares"][63]["visible_to_enemy"] = True
    revealed = rps.view_for(state, RED)
    assert revealed["board"]["squares"][63]["type"] == "flag"


def test_legal_moves_do_not_wrap_files(rps: RockPaperScissors) -> None:
    state = _empty_play_state(rps)
    state["board"]["squares"][from_algebraic("h1")] = _piece("rock", RED)

    moves = rps.legal_actions(state, RED)
    targets = {move["to"] for move in moves if move["type"] == "move"}

    assert from_algebraic("a2") not in targets
    assert from_algebraic("h2") in targets
    assert from_algebraic("g1") in targets


def test_movement_is_pure_and_switches_turn(rps: RockPaperScissors) -> None:
    state = _empty_play_state(rps)
    state["board"]["squares"][from_algebraic("a3")] = _piece("rock", RED)
    original_tick = state["tick"]

    result = rps.step(
        state,
        {RED: {"type": "move", "from": from_algebraic("a3"), "to": from_algebraic("b3")}},
    )

    assert state["tick"] == original_tick
    assert state["board"]["squares"][from_algebraic("a3")]["type"] == "rock"
    assert result.state["board"]["squares"][from_algebraic("a3")] is None
    assert result.state["board"]["squares"][from_algebraic("b3")]["type"] == "rock"
    assert result.state["current_turn"] == BLUE


def test_attacker_wins_rps_capture(rps: RockPaperScissors) -> None:
    state = _empty_play_state(rps)
    state["board"]["squares"][from_algebraic("a3")] = _piece("rock", RED)
    state["board"]["squares"][from_algebraic("a4")] = _piece("scissors", BLUE)

    result = rps.step(
        state,
        {RED: {"type": "move", "from": from_algebraic("a3"), "to": from_algebraic("a4")}},
    )

    winner = result.state["board"]["squares"][from_algebraic("a4")]
    assert winner["type"] == "rock"
    assert winner["color"] == RED
    assert winner["visible_to_enemy"]
    assert result.state["board"]["squares"][from_algebraic("a3")] is None
    assert result.state["current_turn"] == BLUE


def test_trap_defeats_attacker(rps: RockPaperScissors) -> None:
    state = _empty_play_state(rps)
    state["board"]["squares"][from_algebraic("a3")] = _piece("paper", RED)
    state["board"]["squares"][from_algebraic("a4")] = _piece("trap", BLUE)

    result = rps.step(
        state,
        {RED: {"type": "move", "from": from_algebraic("a3"), "to": from_algebraic("a4")}},
    )

    assert result.state["board"]["squares"][from_algebraic("a3")] is None
    defender = result.state["board"]["squares"][from_algebraic("a4")]
    assert defender["type"] == "trap"
    assert defender["color"] == BLUE
    assert defender["visible_to_enemy"]
    assert result.state["current_turn"] == BLUE


def test_flag_capture_ends_game(rps: RockPaperScissors) -> None:
    state = _empty_play_state(rps)
    state["board"]["squares"][from_algebraic("a3")] = _piece("scissors", RED)
    state["board"]["squares"][from_algebraic("a4")] = _piece("flag", BLUE)

    result = rps.step(
        state,
        {RED: {"type": "move", "from": from_algebraic("a3"), "to": from_algebraic("a4")}},
    )

    assert result.done
    assert result.reason == "flag_captured"
    assert result.placement == [RED, BLUE]
    assert result.state["winner"] == RED


def test_equal_piece_capture_enters_and_resolves_fight(rps: RockPaperScissors) -> None:
    state = _empty_play_state(rps)
    state["board"]["squares"][from_algebraic("a3")] = _piece("rock", RED)
    state["board"]["squares"][from_algebraic("a4")] = _piece("rock", BLUE)

    fight = rps.step(
        state,
        {RED: {"type": "move", "from": from_algebraic("a3"), "to": from_algebraic("a4")}},
    ).state

    assert fight["phase"] == "fight"
    assert fight["fight_attacker"] == from_algebraic("a3")
    assert fight["fight_location"] == from_algebraic("a4")
    assert fight["board"]["squares"][from_algebraic("a3")]["color"] == RED
    assert fight["board"]["squares"][from_algebraic("a4")]["color"] == BLUE

    resolved = rps.step(
        fight,
        {
            RED: {"type": "fight", "piece": "paper"},
            BLUE: {"type": "fight", "piece": "rock"},
        },
    ).state

    assert resolved["phase"] == "play"
    assert resolved["fight_attacker"] is None
    assert resolved["fight_location"] is None
    assert resolved["board"]["squares"][from_algebraic("a3")] is None
    winner = resolved["board"]["squares"][from_algebraic("a4")]
    assert winner["color"] == RED
    assert winner["visible_to_enemy"]
    assert resolved["current_turn"] == BLUE


def test_tied_fight_restarts_commitment(rps: RockPaperScissors) -> None:
    state = _empty_play_state(rps)
    state["board"]["squares"][from_algebraic("a3")] = _piece("scissors", RED)
    state["board"]["squares"][from_algebraic("a4")] = _piece("scissors", BLUE)
    fight = rps.step(
        state,
        {RED: {"type": "move", "from": from_algebraic("a3"), "to": from_algebraic("a4")}},
    ).state

    tied = rps.step(
        fight,
        {
            RED: {"type": "fight", "piece": "rock"},
            BLUE: {"type": "fight", "piece": "rock"},
        },
    ).state

    assert tied["phase"] == "fight"
    assert tied["players"][RED]["fight_commit"] is None
    assert tied["players"][BLUE]["fight_commit"] is None
    assert tied["board"]["squares"][from_algebraic("a3")]["color"] == RED
    assert tied["board"]["squares"][from_algebraic("a4")]["color"] == BLUE
