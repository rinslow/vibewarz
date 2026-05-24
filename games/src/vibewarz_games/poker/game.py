"""Poker — single-table No-Limit Texas Hold'em tournament. 2-6 players.

Standard tournament rules: each player starts with a fixed stack, blinds
escalate on a schedule. Last player with chips wins; placement is the
bust-out order (last out = winner).

The state is JSON-serializable and the `step` function is pure. Each
`step(state, actions)` call processes exactly one action by the seat named
in `state["action_on"]`. After applying the action the engine chains
forward through betting-round / phase / hand / tournament transitions as
far as it can without needing another decision — for example, when the
last two players go all-in pre-flop the engine deals the flop, turn,
river, runs the showdown, awards pots, busts losers and starts the next
hand (or ends the tournament) inside the same step.

Hidden information: each player's hole cards belong to them. `view_for`
redacts other seats' hole cards (and the remaining deck) for everyone
except at showdown.
"""

from __future__ import annotations

from typing import Final

from .._core.base import Game, GameMeta, StepResult
from .._core.registry import register
from . import betting
from .betting import PLAYER_COLORS
from .hand_eval import best_seats, rank

STARTING_STACK: Final = 1000

# A short blind schedule that pushes a 6-max table to a conclusion in a
# manageable number of hands. Each level lasts `hands` hands.
BLIND_SCHEDULE: Final = (
    {"sb": 10, "bb": 20, "hands": 6},
    {"sb": 15, "bb": 30, "hands": 6},
    {"sb": 25, "bb": 50, "hands": 6},
    {"sb": 50, "bb": 100, "hands": 6},
    {"sb": 100, "bb": 200, "hands": 6},
    {"sb": 200, "bb": 400, "hands": 6},
    {"sb": 500, "bb": 1000, "hands": 1_000_000},  # terminal level
)


@register
class Poker(Game):
    meta = GameMeta(
        id="poker",
        display_name="No-Limit Hold'em (Single Table)",
        min_players=2,
        max_players=6,
        tick_deadline_ms=15_000,    # 15s per decision
        tick_interval_ms=0,         # no wall-clock floor; deadline is the cadence
        max_ticks=5_000,            # safety bound; tournaments end on chip count
        match_wait_ms=3_000,        # let 6-max tables actually fill up
        description=(
            "Single-table NLH tournament. 1000-chip starting stacks, escalating "
            "blinds. Last stack standing wins; placement is the bust-out order."
        ),
    )

    # ── lifecycle ──────────────────────────────────────────────────────────

    def initial_state(self, seed: int, num_players: int) -> dict:
        if not (self.meta.min_players <= num_players <= self.meta.max_players):
            raise ValueError(
                f"Poker requires {self.meta.min_players}-{self.meta.max_players} players, "
                f"got {num_players}"
            )
        players = []
        for seat in range(num_players):
            players.append({
                "seat": seat,
                "stack": STARTING_STACK,
                "in_tournament": True,
                "in_hand": False,
                "folded": False,
                "all_in": False,
                "committed_round": 0,
                "committed_hand": 0,
                "hole_cards": [],
                "color": PLAYER_COLORS[seat % len(PLAYER_COLORS)],
                "last_action": None,
            })

        state = {
            "tick": 0,
            "seed": seed,
            "hand_number": 0,
            "phase": "between_hands",
            "button": -1,                # bumps to 0 on first hand
            "blind_schedule": [dict(level) for level in BLIND_SCHEDULE],
            "level_idx": 0,
            "hands_at_level": 0,
            "small_blind": BLIND_SCHEDULE[0]["sb"],
            "big_blind": BLIND_SCHEDULE[0]["bb"],
            "deck": [],
            "community_cards": [],
            "pot": 0,
            "side_pots": [],
            "current_bet": 0,
            "min_raise": BLIND_SCHEDULE[0]["bb"],
            "action_on": None,
            "last_aggressor": None,
            "acted_this_round": [],
            "raise_locked_seats": [],
            "players": players,
            "history": [],
            "placement": [],            # bust-out order, last-out first
            "pot_distribution": None,   # filled when a hand resolves
            "showdown_hands": None,     # at showdown, {seat: hand_string}
        }
        return _start_next_hand(state)

    def alive_seats(self, state: dict) -> list[int]:
        # "Alive" here means still in the tournament — used by MatchRunner to
        # know whether the match should continue. A player who folded a hand
        # is still alive in the tournament.
        return betting.in_tournament_seats(state)

    def acting_seats(self, state: dict) -> list[int]:
        # Only the seat named in action_on owes an action. Everyone else is
        # observing.
        if state["action_on"] is None:
            return []
        return [state["action_on"]]

    def view_for(self, state: dict, seat: int) -> dict:
        """Strip the remaining deck and other seats' hole cards. At showdown
        the cards are public (engine sets `showdown_hands`); the deck is
        always hidden because players shouldn't see undealt cards.
        """
        show_all = state.get("showdown_hands") is not None
        view_players = []
        for p in state["players"]:
            visible = (p["seat"] == seat) or show_all or not p["in_hand"]
            view_players.append({
                **p,
                "hole_cards": p["hole_cards"] if (visible and p["hole_cards"]) else [],
            })
        return {
            **state,
            "deck": [],
            "players": view_players,
        }

    def legal_actions(self, state: dict, seat: int) -> list[dict]:
        if state["action_on"] != seat:
            return []
        return betting.legal_actions(state, seat)

    def is_legal(self, state: dict, seat: int, action: dict) -> bool:
        if state["action_on"] != seat:
            return False
        return betting.is_legal(state, seat, action)

    def default_action(self, state: dict, seat: int) -> dict:
        # Check if legal (free), otherwise fold. Never auto-commits chips.
        p = next(pl for pl in state["players"] if pl["seat"] == seat)
        if not p["in_hand"] or p["all_in"]:
            return {"type": "fold"}
        if state["current_bet"] <= p["committed_round"]:
            return {"type": "check"}
        return {"type": "fold"}

    # ── step ───────────────────────────────────────────────────────────────

    def step(self, state: dict, actions: dict[int, dict]) -> StepResult:
        actor = state["action_on"]
        if actor is None:
            # No decision required — engine just advances by one tick.
            new_state = {**state, "tick": state["tick"] + 1}
            return StepResult(state=new_state, done=False)

        action = actions.get(actor)
        if action is None:
            action = self.default_action(state, actor)
        # Caller is supposed to validate via is_legal first. If something
        # invalid slips through, treat as fold.
        if not betting.is_legal(state, actor, action):
            action = {"type": "fold"}

        new_state = betting.apply_action(state, actor, action)
        # Track who just busted in this whole step (across chained hand ends).
        eliminated: list[int] = []

        # Resolve as far as we can without needing another decision.
        while True:
            if _only_one_in_hand(new_state):
                new_state = _award_uncontested(new_state)
                new_state, busted = _settle_busts(new_state)
                eliminated.extend(busted)
                if _tournament_done(new_state):
                    new_state = _finalize_tournament(new_state)
                    return StepResult(
                        state=_bump_tick(new_state),
                        done=True,
                        placement=list(new_state["placement"]),
                        reason="elimination",
                        eliminated_this_tick=tuple(eliminated),
                    )
                new_state = _start_next_hand(new_state)
                break  # _start_next_hand set action_on correctly; await next step

            if not betting.is_round_complete(new_state):
                nxt = betting.next_to_act(new_state, new_state["action_on"])
                new_state = {**new_state, "action_on": nxt}
                break

            # Round complete. Move chips to pot, advance phase.
            new_state = betting.commit_round_to_pot(new_state)
            if new_state["phase"] == "river":
                new_state = {**new_state, "phase": "showdown"}
                new_state = _run_showdown(new_state)
                new_state, busted = _settle_busts(new_state)
                eliminated.extend(busted)
                if _tournament_done(new_state):
                    new_state = _finalize_tournament(new_state)
                    return StepResult(
                        state=_bump_tick(new_state),
                        done=True,
                        placement=list(new_state["placement"]),
                        reason="elimination",
                        eliminated_this_tick=tuple(eliminated),
                    )
                new_state = _start_next_hand(new_state)
                break  # action_on set; next step picks up the new hand

            new_state = betting.advance_phase(new_state)
            # If only one (or zero) eligible-to-act remain — everyone else
            # is all-in — there are no more decisions this hand. Run out the
            # rest of the board and showdown.
            if len(betting.eligible_to_act(new_state)) <= 1:
                # Burn through any remaining streets.
                while new_state["phase"] != "showdown":
                    new_state = betting.commit_round_to_pot(new_state)
                    if new_state["phase"] == "river":
                        new_state = {**new_state, "phase": "showdown"}
                    else:
                        new_state = betting.advance_phase(new_state)
                new_state = _run_showdown(new_state)
                new_state, busted = _settle_busts(new_state)
                eliminated.extend(busted)
                if _tournament_done(new_state):
                    new_state = _finalize_tournament(new_state)
                    return StepResult(
                        state=_bump_tick(new_state),
                        done=True,
                        placement=list(new_state["placement"]),
                        reason="elimination",
                        eliminated_this_tick=tuple(eliminated),
                    )
                new_state = _start_next_hand(new_state)
                break  # action_on set by _start_next_hand; await next step

            # Postflop new round: first eligible seat left of button leads.
            first = betting.first_to_act_postflop(new_state)
            new_state = {**new_state, "action_on": first}
            break

        return StepResult(
            state=_bump_tick(new_state),
            done=False,
            eliminated_this_tick=tuple(eliminated),
        )


# ── module-level helpers (importable by tests) ─────────────────────────────


def _bump_tick(state: dict) -> dict:
    return {**state, "tick": state["tick"] + 1}


def _only_one_in_hand(state: dict) -> bool:
    return len([p for p in state["players"] if p["in_hand"]]) == 1


def _tournament_done(state: dict) -> bool:
    return len([p for p in state["players"] if p["in_tournament"]]) <= 1


def _next_in_tournament(state: dict, after_seat: int) -> int | None:
    return betting.next_clockwise(state, after_seat, lambda p: p["in_tournament"])


def _start_next_hand(state: dict) -> dict:
    """Rotate button, advance blind level if due, deal hole cards, post
    blinds, set action_on to the correct opening seat."""
    # Reset per-hand flags.
    players = []
    for p in state["players"]:
        players.append({
            **p,
            "in_hand": bool(p["in_tournament"]),
            "folded": False,
            "all_in": False,
            "committed_round": 0,
            "committed_hand": 0,
            "hole_cards": [],
            "last_action": None,
        })
    state = {**state, "players": players,
             "pot": 0, "side_pots": [], "community_cards": [],
             "current_bet": 0, "last_aggressor": None,
             "acted_this_round": [], "raise_locked_seats": [],
             "showdown_hands": None, "pot_distribution": None}

    # Blind-level advance.
    state = {**state, "hands_at_level": state["hands_at_level"] + 1}
    schedule = state["blind_schedule"]
    cur_level = state["blind_schedule"][state["level_idx"]]
    if state["hands_at_level"] > cur_level["hands"] and state["level_idx"] + 1 < len(schedule):
        state = {**state, "level_idx": state["level_idx"] + 1, "hands_at_level": 1}
    level = state["blind_schedule"][state["level_idx"]]
    state = {**state, "small_blind": level["sb"], "big_blind": level["bb"],
             "min_raise": level["bb"]}

    state = {**state, "hand_number": state["hand_number"] + 1,
             "phase": "preflop"}

    # Rotate button to next in_tournament seat.
    button = state["button"]
    nxt_button = _next_in_tournament(state, button) if button >= 0 else 0
    if nxt_button is None:
        # Should be impossible — caller should detect tournament-done first.
        return state
    state = {**state, "button": nxt_button}

    # Shuffle a fresh deck and deal 2 hole cards per in_tournament player,
    # starting with the seat left of button (poker convention). Deal in
    # copy-on-write style — accumulate the per-seat dealt cards locally
    # and swap in fresh player dicts once at the end, so an unlikely
    # `view_for` snapshot during the deal can never observe a partially-
    # dealt state.
    deck = list(betting.new_shuffled_deck(state["seed"], state["hand_number"]))
    order = _seat_order_left_of(state, state["button"])
    dealt: dict[int, list[str]] = {seat: [] for seat in order}
    for _round in range(2):
        for seat in order:
            dealt[seat].append(deck.pop(0))
    state = {
        **state,
        "deck": deck,
        "players": [
            {**p, "hole_cards": dealt[p["seat"]]} if p["seat"] in dealt else dict(p)
            for p in state["players"]
        ],
    }

    # Post blinds.
    state = _post_blinds(state)

    # Set first to act preflop.
    state = {**state, "action_on": _first_to_act_preflop(state)}
    return state


def _seat_order_left_of(state: dict, anchor: int) -> list[int]:
    """In-tournament seats in clockwise order starting at anchor+1."""
    n = len(state["players"])
    order = []
    for i in range(1, n + 1):
        seat = (anchor + i) % n
        p = next(pl for pl in state["players"] if pl["seat"] == seat)
        if p["in_tournament"]:
            order.append(seat)
    return order


def _post_blinds(state: dict) -> dict:
    """Post SB and BB. In heads-up the button posts SB; otherwise the seat
    left of button posts SB and the next seat posts BB.
    """
    in_tourney = [p["seat"] for p in state["players"] if p["in_tournament"]]
    button = state["button"]
    if len(in_tourney) == 2:
        sb_seat = button
        bb_seat = next(s for s in in_tourney if s != button)
    else:
        order = _seat_order_left_of(state, button)
        sb_seat = order[0]
        bb_seat = order[1]

    state = _force_post(state, sb_seat, state["small_blind"])
    state = _force_post(state, bb_seat, state["big_blind"])
    return state


def _force_post(state: dict, seat: int, amount: int) -> dict:
    """Force a blind/ante. Caps at remaining stack (short stacks auto-all-in)."""
    players = [dict(p) for p in state["players"]]
    p = next(pl for pl in players if pl["seat"] == seat)
    pay = min(amount, p["stack"])
    p["stack"] -= pay
    p["committed_round"] += pay
    p["committed_hand"] += pay
    if p["stack"] == 0:
        p["all_in"] = True
    current_bet = max(state["current_bet"], p["committed_round"])
    return {**state, "players": players, "current_bet": current_bet}


def _first_to_act_preflop(state: dict) -> int | None:
    """Preflop opener: in heads-up that's the button (small blind); otherwise
    it's the seat left of the big blind (UTG).
    """
    in_tourney = [p["seat"] for p in state["players"] if p["in_tournament"]]
    button = state["button"]
    def eligible(p):
        return p["in_hand"] and not p["all_in"]
    if len(in_tourney) == 2:
        if eligible(_seat_lookup(state, button)):
            return button
        return betting.next_clockwise(state, button, eligible)
    order = _seat_order_left_of(state, button)
    # order[0] = SB, order[1] = BB, order[2] = UTG.
    for seat in order[2:] + order[:2]:
        if eligible(_seat_lookup(state, seat)):
            return seat
    return None


def _seat_lookup(state: dict, seat: int) -> dict:
    return next(p for p in state["players"] if p["seat"] == seat)


def _award_uncontested(state: dict) -> dict:
    """Hand-end via fold-around: the lone in_hand player wins everything
    that's been committed to the pot plus committed_round chips."""
    state = betting.commit_round_to_pot(state)
    winner = next(p["seat"] for p in state["players"] if p["in_hand"])
    return _award_to_winners(state, [{"amount": state["pot"], "winners": [winner]}])


def _run_showdown(state: dict) -> dict:
    """Evaluate all in_hand seats' hands, distribute side pots in layer order.
    Stores per-seat 5-card hand string in `showdown_hands` for UI display.
    """
    contestants = [p["seat"] for p in state["players"] if p["in_hand"]]
    seat_hands = {}
    for seat in contestants:
        p = _seat_lookup(state, seat)
        seat_hands[seat] = rank(p["hole_cards"], state["community_cards"])
    showdown_hands = {seat: str(h) for seat, h in seat_hands.items()}
    state = {**state, "showdown_hands": showdown_hands}

    pots = betting.build_pots(state)
    awards: list[dict] = []
    # Carry-forward bucket: if a pot has no eligible in-hand winner (e.g. the
    # only contributor to a layer subsequently folded), its chips roll forward
    # into the next pot. By construction this is rare — at least one in_hand
    # seat is always eligible for the main pot — but we never want to vanish
    # chips, and the fallback at the bottom guarantees any trailing carry is
    # split among all remaining contestants.
    carry = 0
    for pot in pots:
        eligible = [s for s in pot["eligible_seats"] if s in seat_hands]
        if not eligible:
            carry += pot["amount"]
            continue
        candidates = {s: seat_hands[s] for s in eligible}
        winners = best_seats(candidates)
        awards.append({"amount": pot["amount"] + carry, "winners": winners})
        carry = 0
    if carry > 0 and seat_hands:
        # No subsequent eligible pot ever absorbed the carry. Award it to the
        # overall best hand among contestants.
        winners = best_seats(seat_hands)
        awards.append({"amount": carry, "winners": winners})
    # Reset central pot before awarding — pots already capture everything.
    state = {**state, "pot": 0}
    return _award_to_winners(state, awards)


def _award_to_winners(state: dict, awards: list[dict]) -> dict:
    """Distribute chip awards. Odd chips go to the lowest seat in each split."""
    players = [dict(p) for p in state["players"]]
    distribution: list[dict] = []
    for award in awards:
        amt = award["amount"]
        winners = award["winners"]
        if not winners:
            continue
        share = amt // len(winners)
        remainder = amt - share * len(winners)
        for i, seat in enumerate(winners):
            give = share + (1 if i < remainder else 0)
            next(p for p in players if p["seat"] == seat)["stack"] += give
            distribution.append({"seat": seat, "amount": give})
    return {**state, "players": players, "pot": 0,
            "pot_distribution": distribution, "phase": "hand_complete"}


def _settle_busts(state: dict) -> tuple[dict, list[int]]:
    """Mark zero-stack players as no longer in_tournament. Append them to
    placement in seat-order (deterministic across ties — same hand can bust
    multiple seats with one all-in). Returns (state, newly_busted_seats).
    """
    players = [dict(p) for p in state["players"]]
    newly_busted: list[int] = []
    placement = list(state["placement"])
    for p in sorted(players, key=lambda pp: pp["seat"]):
        if p["in_tournament"] and p["stack"] <= 0:
            p["in_tournament"] = False
            p["in_hand"] = False
            newly_busted.append(p["seat"])
            if p["seat"] not in placement:
                placement.append(p["seat"])
    state = {**state, "players": players, "placement": placement}
    return state, newly_busted


def _finalize_tournament(state: dict) -> dict:
    """Append the chip leader (sole survivor) to placement and mark done."""
    placement = list(state["placement"])
    survivors = sorted(
        (p["seat"] for p in state["players"] if p["in_tournament"]),
    )
    for seat in survivors:
        if seat not in placement:
            placement.append(seat)
    # vibewarz placement convention: index 0 = winner. We've appended in
    # bust-order so reverse to get winner-first.
    final = list(reversed(placement))
    return {**state, "placement": final, "phase": "done", "action_on": None}
