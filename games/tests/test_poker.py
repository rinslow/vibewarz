"""Tests for the Poker (single-table NLH) game engine.

These tests exercise the pure engine — no server, no WebSocket. They cover
determinism, basic betting flow, side pots, bust-out / tournament-end, and
the `view_for` hidden-info redaction.
"""

from __future__ import annotations

from typing import Any

import pytest
from vibewarz_games.poker.betting import build_pots, new_shuffled_deck
from vibewarz_games.poker.game import Poker
from vibewarz_games.poker.hand_eval import best_seats, rank


def _play_until_decision(p: Poker, state: dict, actions_by_actor: dict[int, dict[str, Any]] | None = None) -> dict:
    """Apply `actions_by_actor[actor]` repeatedly until the engine yields a
    decision point that isn't in the dict, the tournament ends, or we hit a
    safety cap. Returns the resulting state.
    """
    actions_by_actor = actions_by_actor or {}
    for _ in range(5_000):
        if state["phase"] == "done":
            return state
        actor = state["action_on"]
        if actor is None:
            state = p.step(state, {}).state
            continue
        action = actions_by_actor.get(actor)
        if action is None:
            return state
        result = p.step(state, {actor: action})
        state = result.state
        if result.done:
            return state
    raise AssertionError("safety cap hit")


# ── determinism ────────────────────────────────────────────────────────────


def test_deck_shuffle_is_deterministic_from_seed_and_hand():
    d1 = new_shuffled_deck(42, 1)
    d2 = new_shuffled_deck(42, 1)
    d3 = new_shuffled_deck(42, 2)
    d4 = new_shuffled_deck(43, 1)
    assert d1 == d2
    assert d1 != d3
    assert d1 != d4
    assert len(d1) == 52 and len(set(d1)) == 52


def test_initial_state_is_deterministic_from_seed():
    p = Poker()
    a = p.initial_state(seed=99, num_players=4)
    b = p.initial_state(seed=99, num_players=4)
    assert a == b


# ── shape / opening ────────────────────────────────────────────────────────


@pytest.mark.parametrize("n", [2, 3, 4, 5, 6])
def test_initial_state_shape_across_player_counts(n: int):
    p = Poker()
    s = p.initial_state(seed=1, num_players=n)
    assert s["phase"] == "preflop"
    assert s["hand_number"] == 1
    assert len(s["players"]) == n
    for pl in s["players"]:
        assert len(pl["hole_cards"]) == 2
        assert pl["in_tournament"] is True
        assert pl["in_hand"] is True
    # SB + BB committed; the right two seats by table size.
    committed = sum(pl["committed_round"] for pl in s["players"])
    assert committed == s["small_blind"] + s["big_blind"]
    # Action is on a real seat.
    assert s["action_on"] in [pl["seat"] for pl in s["players"]]


def test_player_count_validation():
    p = Poker()
    with pytest.raises(ValueError):
        p.initial_state(seed=1, num_players=1)
    with pytest.raises(ValueError):
        p.initial_state(seed=1, num_players=7)


def test_heads_up_button_is_small_blind_and_acts_first():
    p = Poker()
    s = p.initial_state(seed=1, num_players=2)
    button = s["button"]
    # Button posts SB.
    sb_player = next(pl for pl in s["players"] if pl["seat"] == button)
    assert sb_player["committed_round"] == s["small_blind"]
    # Button acts first preflop.
    assert s["action_on"] == button


def test_six_max_utg_acts_first_preflop():
    p = Poker()
    s = p.initial_state(seed=1, num_players=6)
    button = s["button"]
    n = 6
    sb = (button + 1) % n
    bb = (button + 2) % n
    utg = (button + 3) % n
    assert next(pl for pl in s["players"] if pl["seat"] == sb)["committed_round"] == s["small_blind"]
    assert next(pl for pl in s["players"] if pl["seat"] == bb)["committed_round"] == s["big_blind"]
    assert s["action_on"] == utg


# ── legal actions / is_legal ───────────────────────────────────────────────


def test_legal_actions_preflop_facing_bb():
    p = Poker()
    s = p.initial_state(seed=1, num_players=4)
    actor = s["action_on"]
    legal = p.legal_actions(s, actor)
    kinds = {a["type"] for a in legal}
    assert kinds == {"fold", "call", "raise"}
    # Raise options include min and all-in.
    raises = [a["to"] for a in legal if a["type"] == "raise"]
    assert s["big_blind"] * 2 in raises  # min raise = current_bet(20) + min_raise(20)
    assert max(raises) == 1000             # all-in


def test_default_action_is_check_or_fold():
    p = Poker()
    s = p.initial_state(seed=1, num_players=4)
    actor = s["action_on"]
    # Preflop facing BB: default = fold (can't check).
    assert p.default_action(s, actor) == {"type": "fold"}
    # BB facing no raise: can check.
    bb_seat = next(pl["seat"] for pl in s["players"] if pl["committed_round"] == s["big_blind"])
    # Construct a synthetic state where action is on BB and everyone called.
    fake = {**s, "action_on": bb_seat, "current_bet": s["big_blind"]}
    fake_players = [dict(pl) for pl in s["players"]]
    for pl in fake_players:
        pl["committed_round"] = s["big_blind"]
    fake["players"] = fake_players
    assert p.default_action(fake, bb_seat) == {"type": "check"}


def test_is_legal_rejects_undersized_raise():
    p = Poker()
    s = p.initial_state(seed=1, num_players=4)
    actor = s["action_on"]
    # current_bet=20, min_raise=20 → min legal raise total is 40. 30 must be illegal.
    assert not p.is_legal(s, actor, {"type": "raise", "to": 30})
    assert p.is_legal(s, actor, {"type": "raise", "to": 40})


def test_is_legal_rejects_out_of_turn():
    p = Poker()
    s = p.initial_state(seed=1, num_players=4)
    other = next(pl["seat"] for pl in s["players"] if pl["seat"] != s["action_on"])
    assert not p.is_legal(s, other, {"type": "fold"})


# ── happy-path hand flow ───────────────────────────────────────────────────


def test_fold_around_awards_pot_to_bb():
    p = Poker()
    s = p.initial_state(seed=11, num_players=4)
    bb_seat = (s["button"] + 2) % 4
    actions = {pl["seat"]: {"type": "fold"} for pl in s["players"] if pl["seat"] != bb_seat}
    s = _play_until_decision(p, s, actions)
    # After fold-around, new hand has started (BB collected blinds and may
    # have re-posted in hand 2). Check chip totals (stack + this-round commit).
    assert s["hand_number"] >= 2
    bb_after = next(pl for pl in s["players"] if pl["seat"] == bb_seat)
    # BB started with 1000, paid 20 BB, won SB 10 + BB 20 = 30 → 1010 net,
    # then may have re-posted a blind in hand 2 (deducted from stack).
    assert bb_after["stack"] + bb_after["committed_round"] == 1010


def test_call_call_check_to_showdown_preserves_chip_conservation():
    p = Poker()
    s = p.initial_state(seed=5, num_players=3)
    total_chips_start = sum(pl["stack"] + pl["committed_round"] for pl in s["players"])
    actions = {seat: {"type": "call"} for seat in range(3)}
    actions[(s["button"] + 2) % 3] = {"type": "check"}  # BB checks when option closes
    # Loop: call when facing bet, check otherwise.
    for _ in range(500):
        if s["phase"] == "done":
            break
        actor = s["action_on"]
        if actor is None:
            s = p.step(s, {}).state
            continue
        legal = p.legal_actions(s, actor)
        kinds = {a["type"] for a in legal}
        pick = {"type": "check"} if "check" in kinds else {"type": "call"}
        s = p.step(s, {actor: pick}).state
        if s["hand_number"] >= 2:
            break
    total_chips_end = sum(pl["stack"] for pl in s["players"]) + s["pot"] + sum(pl["committed_round"] for pl in s["players"])
    assert total_chips_start == total_chips_end


def test_play_a_full_tournament_to_completion():
    p = Poker()
    s = p.initial_state(seed=2026, num_players=4)
    start_chips = sum(pl["stack"] for pl in s["players"]) + sum(pl["committed_round"] for pl in s["players"])
    for _ in range(20_000):
        if s["phase"] == "done":
            break
        actor = s["action_on"]
        if actor is None:
            s = p.step(s, {}).state
            continue
        legal = p.legal_actions(s, actor)
        kinds = {a["type"] for a in legal}
        pick = {"type": "check"} if "check" in kinds else (
            {"type": "call"} if "call" in kinds else legal[0]
        )
        result = p.step(s, {actor: pick})
        s = result.state
        if result.done:
            break
    assert s["phase"] == "done"
    assert len(s["placement"]) == 4
    assert set(s["placement"]) == {0, 1, 2, 3}
    survivors = [pl["seat"] for pl in s["players"] if pl["in_tournament"]]
    assert len(survivors) == 1
    # placement[0] is the winner.
    assert survivors[0] == s["placement"][0]
    # Chip conservation across the whole tournament.
    end_chips = sum(pl["stack"] for pl in s["players"])
    assert end_chips == start_chips


# ── side pots ──────────────────────────────────────────────────────────────


def test_build_pots_single_main_pot_when_all_equal():
    state = {"players": [
        {"seat": 0, "committed_hand": 100, "in_hand": True},
        {"seat": 1, "committed_hand": 100, "in_hand": True},
        {"seat": 2, "committed_hand": 100, "in_hand": True},
    ]}
    pots = build_pots(state)
    assert pots == [{"amount": 300, "eligible_seats": [0, 1, 2]}]


def test_build_pots_creates_side_pot_for_short_stack_all_in():
    # Seat 0 all-in for 50; seats 1+2 commit 200 each.
    state = {"players": [
        {"seat": 0, "committed_hand": 50, "in_hand": True},
        {"seat": 1, "committed_hand": 200, "in_hand": True},
        {"seat": 2, "committed_hand": 200, "in_hand": True},
    ]}
    pots = build_pots(state)
    # Main pot: 50*3 = 150 (all 3 eligible). Side pot: 150*2 = 300 (only 1 & 2).
    assert pots == [
        {"amount": 150, "eligible_seats": [0, 1, 2]},
        {"amount": 300, "eligible_seats": [1, 2]},
    ]


def test_build_pots_three_layer_all_ins():
    # Three different all-in amounts → three pot layers.
    state = {"players": [
        {"seat": 0, "committed_hand": 30, "in_hand": True},
        {"seat": 1, "committed_hand": 100, "in_hand": True},
        {"seat": 2, "committed_hand": 250, "in_hand": True},
    ]}
    pots = build_pots(state)
    # Layer 30 → 30*3=90 eligible {0,1,2}
    # Layer 70 (100-30) → 70*2=140 eligible {1,2}
    # Layer 150 (250-100) → 150*1=150 eligible {2}
    assert pots == [
        {"amount": 90, "eligible_seats": [0, 1, 2]},
        {"amount": 140, "eligible_seats": [1, 2]},
        {"amount": 150, "eligible_seats": [2]},
    ]


def test_build_pots_excludes_folded_from_eligibility_but_includes_their_chips():
    state = {"players": [
        {"seat": 0, "committed_hand": 100, "in_hand": False},  # folded
        {"seat": 1, "committed_hand": 100, "in_hand": True},
        {"seat": 2, "committed_hand": 100, "in_hand": True},
    ]}
    pots = build_pots(state)
    assert pots == [{"amount": 300, "eligible_seats": [1, 2]}]


# ── view_for redaction ─────────────────────────────────────────────────────


def test_view_for_redacts_other_seats_hole_cards():
    p = Poker()
    s = p.initial_state(seed=99, num_players=3)
    v0 = p.view_for(s, 0)
    assert v0["players"][0]["hole_cards"] == s["players"][0]["hole_cards"]
    assert v0["players"][1]["hole_cards"] == []
    assert v0["players"][2]["hole_cards"] == []
    assert v0["deck"] == []  # deck never leaked


def test_view_for_never_leaks_seed():
    """Regression: the seed used to shuffle the deck is deterministic, so
    leaking it lets a client locally reproduce every opponent's hole cards
    via `new_shuffled_deck(seed, hand_number)`. The per-seat view MUST omit
    `seed`; the authoritative state retains it for server-side replay.
    """
    p = Poker()
    s = p.initial_state(seed=99, num_players=3)
    assert s["seed"] == 99  # authoritative state still has it
    for seat in range(3):
        v = p.view_for(s, seat)
        assert "seed" not in v, f"seed leaked to seat {seat}"
    # Also at showdown — the seed is still secret for any subsequent hand.
    s_showdown = {**s, "showdown_hands": {0: "X", 1: "Y", 2: "Z"}}
    for seat in range(3):
        assert "seed" not in p.view_for(s_showdown, seat)


def test_view_for_reveals_all_at_showdown():
    p = Poker()
    s = p.initial_state(seed=99, num_players=2)
    # Synthetic: showdown_hands set means cards public.
    s = {**s, "showdown_hands": {0: "X", 1: "Y"}}
    v = p.view_for(s, 0)
    assert v["players"][0]["hole_cards"] != []
    assert v["players"][1]["hole_cards"] != []  # revealed


def test_view_for_hides_folded_seats_hole_cards():
    """Mucked cards are never shown to other players in real poker. The
    authoritative state retains `hole_cards` after a fold (for audit and
    replay) — the per-seat view MUST hide them from every other seat until
    showdown.
    """
    p = Poker()
    s = p.initial_state(seed=99, num_players=3)
    # Mark seat 1 as folded (in_hand=False) — hole_cards still populated
    # in the authoritative state, matching what betting.apply_action does.
    players = [dict(pl) for pl in s["players"]]
    players[1] = {**players[1], "in_hand": False, "folded": True}
    s = {**s, "players": players}
    assert players[1]["hole_cards"]  # precondition: folded player still holds cards in state
    # Seat 0 (still in hand) must not see seat 1's mucked cards.
    v0 = p.view_for(s, 0)
    assert v0["players"][1]["hole_cards"] == []
    # Seat 1 (the folder themselves) still sees their own cards.
    v1 = p.view_for(s, 1)
    assert v1["players"][1]["hole_cards"] == players[1]["hole_cards"]


# ── hand_eval wrapper ──────────────────────────────────────────────────────


def test_rank_orders_royal_flush_above_quads():
    royal = rank(["As", "Ks"], ["Qs", "Js", "Ts", "2h", "3d"])
    quads = rank(["Ah", "Ad"], ["Ac", "Kd", "Qd", "Jc", "2c"])
    assert royal > quads


def test_best_seats_returns_tied_winners():
    # Both hands are the same straight on the board → split.
    a = rank(["2c", "3d"], ["5s", "6h", "7d", "8c", "9c"])
    b = rank(["4c", "Kd"], ["5s", "6h", "7d", "8c", "9c"])
    assert best_seats({0: a, 1: b}) == [0, 1]


def test_best_seats_resolves_kicker():
    # Both have pair of kings; seat 0 has ace kicker, seat 1 has queen kicker.
    a = rank(["Ks", "Ah"], ["Kd", "2c", "5h", "7d", "9c"])
    b = rank(["Kc", "Qh"], ["Kd", "2c", "5h", "7d", "9c"])
    assert best_seats({0: a, 1: b}) == [0]


# ── ultrareview coverage gaps ──────────────────────────────────────────────


def test_heads_up_split_pot_chip_conservation():
    """Two players reach showdown with hands that tie on the board → split.
    Chip conservation must hold even when the pot doesn't divide evenly."""
    p = Poker()
    s = p.initial_state(seed=2024, num_players=2)
    start = sum(pl["stack"] + pl["committed_round"] for pl in s["players"])

    # Force a synthetic split-on-board: both seats hold a card that can't
    # contribute to the winning straight; the board itself is the nut hand.
    # We hand-build the state so the test is deterministic regardless of seed.
    s = {
        **s,
        "phase": "river",
        "community_cards": ["5s", "6h", "7d", "8c", "9c"],
        "current_bet": 0,
        "min_raise": s["big_blind"],
        "acted_this_round": [],
        "players": [
            {**s["players"][0], "hole_cards": ["2c", "3d"], "committed_round": 0,
             "committed_hand": 100, "stack": 900, "in_hand": True, "folded": False, "all_in": False},
            {**s["players"][1], "hole_cards": ["4c", "Kd"], "committed_round": 0,
             "committed_hand": 100, "stack": 900, "in_hand": True, "folded": False, "all_in": False},
        ],
        "pot": 200,
        "action_on": s["button"],
    }
    # Two checks → showdown → split → next hand auto-starts with blinds
    # posted, so check chip totals (stack + committed_round) per seat.
    legal0 = p.legal_actions(s, s["action_on"])
    assert any(a["type"] == "check" for a in legal0)
    s = p.step(s, {s["action_on"]: {"type": "check"}}).state
    s = p.step(s, {s["action_on"]: {"type": "check"}}).state
    end = sum(pl["stack"] + pl["committed_round"] for pl in s["players"])
    assert end == start, f"chip total drifted: {start} -> {end}"
    # Each player should have 1000 worth of chips after the split.
    for pl in s["players"]:
        assert pl["stack"] + pl["committed_round"] == 1000, (
            f"seat {pl['seat']} chips != 1000: {pl}"
        )


def test_short_stack_under_min_raise_allin_does_not_reopen_action():
    """Under-min-raise all-in is legal but must NOT give already-acted seats
    a fresh decision. The engine implements this in `apply_action` (raise
    branch). This test wires it end-to-end through `step`.
    """
    p = Poker()
    # 3-player table, button=0 → SB=1, BB=2, UTG=0.
    s = p.initial_state(seed=1, num_players=3)
    # Surgically arrange the betting state:
    #   - current_bet = 80, min_raise = 60.
    #   - Seat 0 (UTG) has acted, committed_round=80.
    #   - Seat 1 (SB) folded.
    #   - Seat 2 (BB) is short — stack=20, committed_round=80. They jam to
    #     to=100, which is < 80+60=140. Under-min-raise all-in.
    s = {
        **s,
        "phase": "preflop",
        "current_bet": 80,
        "min_raise": 60,
        "last_aggressor": 0,
        "acted_this_round": [0],
        "action_on": 2,
        "players": [
            {**s["players"][0], "stack": 920, "committed_round": 80,
             "committed_hand": 80, "in_hand": True, "all_in": False, "folded": False},
            {**s["players"][1], "stack": 990, "committed_round": 0,
             "committed_hand": 10, "in_hand": False, "all_in": False, "folded": True},
            {**s["players"][2], "stack": 20, "committed_round": 80,
             "committed_hand": 80, "in_hand": True, "all_in": False, "folded": False},
        ],
    }
    # Seat 2 jams all-in for a raise to 100.
    result = p.step(s, {2: {"type": "raise", "to": 100}})
    s = result.state
    # Critical: seat 0 must NOT be asked again. The round should be considered
    # closed for seat 0 (already acted at current_bet=100 isn't quite right —
    # the under-min-raise all-in doesn't re-open). The next acting seat (if
    # any) must not be seat 0 unless they themselves haven't matched.
    # Concretely: after this step, either the engine moves to flop (round
    # closed for seat 0) or it's seat 0's turn to call/fold the remaining 20.
    # The acceptance criterion: seat 0 is in `acted_this_round` and is not
    # forced to reopen. We assert seat 0 doesn't need to act again at the
    # OLD bet level — only because they're short on the call.
    # Easiest invariant: action_on is either None, or it's a seat that
    # hasn't yet matched the new current_bet=100 (i.e., seat 0 owes 20 more,
    # which is a CALL — not a reopened raise option).
    if s["action_on"] is not None:
        actor = next(p for p in s["players"] if p["seat"] == s["action_on"])
        legal = [a["type"] for a in p_legal_actions(s, actor["seat"])]
        # The reopen test: when action does reopen, raise becomes available
        # to seats who'd already matched the old bet. With under-min-raise
        # all-in, the rule is "no reopen for already-acted seats". Seat 0
        # has already acted, so even if action returns to them they should
        # only see fold/call (not raise).
        # We accept either: (a) action moved off seat 0 entirely, or (b)
        # seat 0 may call/fold but not raise.
        if actor["seat"] == 0:
            assert "raise" not in legal, (
                f"under-min-raise all-in should not reopen action; "
                f"seat 0 sees legal={legal}"
            )


def p_legal_actions(state, seat):
    """Local helper — module-level so the closure above can reference it."""
    return Poker().legal_actions(state, seat)


def test_default_action_when_seat_misses_decision():
    """If the engine receives no action for the seat on the clock, it
    substitutes `default_action`. That's check-if-free, otherwise fold.
    """
    p = Poker()
    s = p.initial_state(seed=42, num_players=3)
    actor = s["action_on"]
    # Preflop, facing the BB → can't check. Default must be fold.
    assert p.default_action(s, actor) == {"type": "fold"}
    # Stepping with an empty actions dict applies the default.
    new = p.step(s, {}).state
    # Seat `actor` should have folded (in_hand=False).
    folded = next(pl for pl in new["players"] if pl["seat"] == actor)
    assert not folded["in_hand"]
    assert folded["folded"]


def test_journal_view_drops_history_keeps_seed_and_rest():
    p = Poker()
    state = p.initial_state(seed=7, num_players=4)
    # Drive a few legal actions so `history` is non-empty (default_action is
    # check-or-fold — enough to log entries without looping the tournament).
    for _ in range(5):
        if state["phase"] == "done":
            break
        actor = state["action_on"]
        if actor is None:
            state = p.step(state, {}).state
            continue
        state = p.step(state, {actor: p.default_action(state, actor)}).state
    assert state.get("history"), "expected some betting history to accumulate"
    jv = p.journal_view(state)
    # The O(N²) field is gone from the per-tick journal view…
    assert "history" not in jv
    # …but the view stays omniscient/unredacted and otherwise intact.
    assert jv["seed"] == state["seed"]
    assert jv["players"] == state["players"]
    assert {k for k in state if k != "history"} == set(jv)


def test_delta_view_for_omits_history_keeps_history_delta():
    """Wire view ships the constant-size `history_delta`, never the
    cumulative `history` — and still redacts like `view_for`."""
    p = Poker()
    state = p.initial_state(seed=42, num_players=4)
    for _ in range(8):
        if state["phase"] == "done":
            break
        actor = state["action_on"]
        action = {} if actor is None else {actor: p.default_action(state, actor)}
        state = p.step(state, action).state
    assert len(state["history"]) > 1  # cumulative growth happened
    for seat in range(4):
        view = p.delta_view_for(state, seat)
        assert "seed" not in view
        assert "history" not in view
        assert view["history_delta"] == state["history_delta"]
        assert view["deck"] == []  # view_for redaction preserved


def test_apply_deltas_reconstructs_authoritative_history():
    """SDK accumulator semantics: client starts from the game_start snapshot
    and concatenates each tick's `history_delta` onto its `history`. After N
    steps the reconstruction must equal the authoritative engine history."""
    p = Poker()
    state = p.initial_state(seed=42, num_players=4)
    client_history = list(p.snapshot_view_for(state, seat=0)["history"])
    for _ in range(40):
        actor = state["action_on"]
        action = {} if actor is None else {actor: p.default_action(state, actor)}
        result = p.step(state, action)
        state = result.state
        client_history.extend(p.delta_view_for(state, seat=0)["history_delta"])
        if result.done:
            break
    assert client_history == state["history"]
    assert len(client_history) > 1  # exercised real growth across hands
