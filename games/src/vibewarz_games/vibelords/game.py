"""Vibelords — heads-up lane RTS with hidden, simultaneous commitment.

Two bots face off across a single horizontal lane, a base at each end. Every
tick both commit a spend **simultaneously and in secret**: build one of three
rock-paper-scissors units (pike > cavalry > archer > pike), advance an age to
unlock stronger units, fire a recharging airstrike, or save. A built unit sits
in a *hidden* build queue for a few ticks before it deploys and marches; the
opponent only sees it once it walks onto the lane. There is therefore no fixed
optimal build order — you are reacting to a concealed opponent, which makes the
game unsolvable in the same way poker is (and it leans on the same engine hooks:
``view_for`` redaction + the default simultaneous ``acting_seats``).

Units auto-march toward the enemy base, stop to fight whatever they meet, and
chip the base down once they break through. Destroy the enemy base to win; if
the clock runs out, the most base HP wins.

The ``step`` function is pure and fully deterministic — there is no randomness
at all, so identical action streams yield identical state sequences.
"""

from __future__ import annotations

from typing import Final

from .._core.base import Game, GameMeta, StepResult
from .._core.registry import register
from . import combat
from . import units as U

# ── battlefield & timing ───────────────────────────────────────────────────
# Ticks run at 100ms (10 Hz), matching Blast — slow enough for heuristic/LLM
# bots to read the lane and react.
LANE_LENGTH: Final = 1000.0
MAX_TICKS: Final = 3600          # ~6 min ceiling; timeout resolves on base HP
BASE_HP: Final = 1500

# ── economy ─────────────────────────────────────────────────────────────────
STARTING_GOLD: Final = 50.0      # enough for one age-0 unit immediately
STARTING_XP: Final = 0
PASSIVE_GOLD: Final = 2.0        # per tick (kills add more)
PASSIVE_XP: Final = 1            # per tick (kills add more)

# ── special: airstrike ──────────────────────────────────────────────────────
SPECIAL_CD: Final = 250          # ticks (~25s) between airstrikes
AIRSTRIKE_BASE: Final = 90       # flat damage at Stone age
AIRSTRIKE_PER_AGE: Final = 40    # +damage per age of the caster

# Brand palette, mirrored by the frontend renderer (seat 0 lime, seat 1 rose).
PLAYER_COLORS: Final = ("#a3e635", "#f43f5e")

ACTION_TYPES: Final = ("build", "advance_age", "special", "noop")


def _base_x(seat: int) -> float:
    return 0.0 if seat == 0 else LANE_LENGTH


@register
class Vibelords(Game):
    meta = GameMeta(
        id="vibelords",
        display_name="Vibelords",
        min_players=2,
        max_players=2,
        tick_deadline_ms=100,
        tick_interval_ms=100,
        max_ticks=MAX_TICKS,
        match_wait_ms=0,
        description=(
            "Two lords, one lane, four ages — march your army, out-read your "
            "opponent, and raze their keep. A call to vibes."
        ),
    )

    # ── lifecycle ──────────────────────────────────────────────────────────

    def initial_state(self, seed: int, num_players: int) -> dict:
        if num_players != 2:
            raise ValueError(f"Vibelords is heads-up (2 players), got {num_players}")
        players: list[dict] = [
            {
                "seat": seat,
                "color": PLAYER_COLORS[seat],
                "gold": STARTING_GOLD,
                "xp": STARTING_XP,
                "age": 0,
                "special_cd": 0,
                "dmg_dealt": 0.0,
                "queue": [],  # hidden build queue — redacted in view_for
            }
            for seat in range(2)
        ]
        bases = [
            {"seat": seat, "x": _base_x(seat), "hp": BASE_HP, "max_hp": BASE_HP}
            for seat in range(2)
        ]
        return {
            "tick": 0,
            "seed": seed,
            "max_ticks": MAX_TICKS,
            "lane": {"length": LANE_LENGTH},
            "bases": bases,
            "players": players,
            "units": [],
            "fx": [],
            "next_unit_id": 0,
            "placement": [],
        }

    def alive_seats(self, state: dict) -> list[int]:
        return [b["seat"] for b in state["bases"] if b["hp"] > 0]

    # Vibelords is simultaneous-move: the default acting_seats (all alive seats every
    # tick) is exactly the hidden, simultaneous commitment we want.

    def view_for(self, state: dict, seat: int) -> dict:
        """Public view for ``seat``: drop the seed and hide the opponent's
        build queue. Everything else — gold, xp, age, every unit on the lane,
        base HP — is public (the poker analog of open stacks but hidden cards).
        """
        view = {k: v for k, v in state.items() if k != "seed"}
        view["players"] = [
            {**p, "queue": p["queue"] if p["seat"] == seat else []}
            for p in state["players"]
        ]
        return view

    # ── action validation ──────────────────────────────────────────────────

    def legal_actions(self, state: dict, seat: int) -> list[dict]:
        p = state["players"][seat]
        if state["bases"][seat]["hp"] <= 0:
            return [{"type": "noop"}]
        actions: list[dict] = [{"type": "noop"}]
        for unit_type in U.UNIT_TYPES:
            if p["gold"] >= U.unit_stats(unit_type, p["age"])["gold_cost"]:
                actions.append({"type": "build", "unit": unit_type})
        cost = U.age_up_cost(p["age"])
        if cost is not None and p["xp"] >= cost:
            actions.append({"type": "advance_age"})
        if p["special_cd"] == 0:
            actions.append({"type": "special"})
        return actions

    def is_legal(self, state: dict, seat: int, action: dict) -> bool:
        # Structural validation only. Unaffordable builds / age-ups and
        # on-cooldown specials are resolved as harmless no-ops in step() (see
        # the guards there), so they stay legal rather than elimination-worthy —
        # mirroring how Blast treats a wasted drop_bomb.
        if not isinstance(action, dict):
            return False
        atype = action.get("type")
        if atype not in ACTION_TYPES:
            return False
        if atype == "build":
            return action.get("unit") in U.UNIT_TYPES
        return True

    def default_action(self, state: dict, seat: int) -> dict:
        return {"type": "noop"}

    # ── tick ───────────────────────────────────────────────────────────────

    def step(self, state: dict, actions: dict[int, dict]) -> StepResult:
        new_tick = state["tick"] + 1
        lane_length = state["lane"]["length"]

        # Copy-on-write every mutable structure.
        players = [
            {**p, "queue": [dict(q) for q in p["queue"]]} for p in state["players"]
        ]
        bases = [dict(b) for b in state["bases"]]
        unit_list = [dict(u) for u in state["units"]]
        next_unit_id = int(state["next_unit_id"])
        placement = list(state["placement"])
        eliminated_this_tick: list[int] = []
        fx: list[dict] = []

        # 1) Income.
        for p in players:
            if bases[p["seat"]]["hp"] > 0:
                p["gold"] += PASSIVE_GOLD
                p["xp"] += PASSIVE_XP
            if p["special_cd"] > 0:
                p["special_cd"] -= 1

        # 2) Hatch ready queue entries (built on an earlier tick) — before this
        # tick's new builds, so nothing hatches the instant it is queued.
        for p in players:
            kept: list[dict] = []
            for q in p["queue"]:
                if q["ready_tick"] <= new_tick:
                    st = U.unit_stats(q["unit"], q["age"])
                    unit_list.append(
                        {
                            "id": f"u{next_unit_id}",
                            "owner": p["seat"],
                            "unit": q["unit"],
                            "age": q["age"],
                            "x": _base_x(p["seat"]),
                            "hp": float(st["hp"]),
                            "max_hp": st["hp"],
                            "atk_cd": 0,
                        }
                    )
                    next_unit_id += 1
                else:
                    kept.append(q)
            p["queue"] = kept

        # 3) Apply this tick's commands (simultaneous; seat order only matters
        # for the independent per-seat airstrikes).
        for seat in sorted(actions.keys()):
            if seat < 0 or seat >= len(players):
                continue
            p = players[seat]
            if bases[seat]["hp"] <= 0:
                continue
            action = actions.get(seat) or self.default_action(state, seat)
            atype = action.get("type", "noop")

            if atype == "build":
                unit_type = action.get("unit")
                if unit_type not in U.UNIT_TYPES:
                    continue
                st = U.unit_stats(unit_type, p["age"])
                if p["gold"] >= st["gold_cost"]:
                    p["gold"] -= st["gold_cost"]
                    p["queue"].append(
                        {
                            "unit": unit_type,
                            "age": p["age"],
                            "ready_tick": new_tick + st["build_ticks"],
                        }
                    )
            elif atype == "advance_age":
                cost = U.age_up_cost(p["age"])
                if cost is not None and p["xp"] >= cost:
                    p["xp"] -= cost
                    p["age"] += 1
            elif atype == "special":
                if p["special_cd"] == 0:
                    unit_list = self._airstrike(seat, p, unit_list, lane_length, fx)
                    unit_list = self._collect_dead(unit_list, players, fx)
                    p["special_cd"] = SPECIAL_CD

        # 4) Lane combat.
        unit_list, dead, cfx, dmg_by_owner = combat.resolve_tick(
            unit_list, bases, lane_length
        )
        fx.extend(cfx)
        for owner, dmg in dmg_by_owner.items():
            players[owner]["dmg_dealt"] += dmg
        for u in dead:
            st = U.unit_stats(u["unit"], u["age"])
            opp = players[1 - u["owner"]]
            opp["gold"] += st["kill_gold"]
            opp["xp"] += st["kill_xp"]

        # 5) Resolve base destruction & end conditions.
        for b in sorted(bases, key=lambda b: b["seat"]):
            if b["hp"] <= 0 and b["seat"] not in placement:
                placement.append(b["seat"])
                eliminated_this_tick.append(b["seat"])

        new_state = {
            **state,
            "tick": new_tick,
            "players": players,
            "bases": bases,
            "units": unit_list,
            "fx": fx,
            "next_unit_id": next_unit_id,
            "placement": placement,
        }

        alive = [b["seat"] for b in bases if b["hp"] > 0]
        done = len(alive) <= 1 or new_tick >= self.meta.max_ticks
        final_placement: list[int] | None = None
        reason: str | None = None
        if done:
            if len(alive) == 1:
                final_placement = [alive[0], 1 - alive[0]]
                reason = "base_destroyed"
            elif len(alive) == 0:
                final_placement = self._tiebreak(bases, players)
                reason = "base_destroyed"
            else:
                final_placement = self._tiebreak(bases, players)
                reason = "timeout"

        return StepResult(
            state=new_state,
            done=done,
            placement=final_placement,
            reason=reason,
            eliminated_this_tick=tuple(eliminated_this_tick),
        )

    # ── helpers ──────────────────────────────────────────────────────────────

    def _airstrike(
        self,
        seat: int,
        player: dict,
        unit_list: list[dict],
        lane_length: float,
        fx: list[dict],
    ) -> list[dict]:
        """Damage every enemy unit in the caster's defensive half of the lane."""
        mid = lane_length / 2.0
        dmg = AIRSTRIKE_BASE + AIRSTRIKE_PER_AGE * player["age"]
        if seat == 0:
            in_band = lambda x: x <= mid  # noqa: E731
            x0, x1 = 0.0, mid
        else:
            in_band = lambda x: x >= mid  # noqa: E731
            x0, x1 = mid, lane_length
        hit = 0.0
        for u in unit_list:
            if u["owner"] != seat and in_band(u["x"]):
                u["hp"] -= dmg
                hit += dmg
        player["dmg_dealt"] += hit
        fx.append(
            {"kind": "airstrike", "owner": seat, "age": player["age"], "x0": x0, "x1": x1}
        )
        return unit_list

    def _collect_dead(
        self, unit_list: list[dict], players: list[dict], fx: list[dict]
    ) -> list[dict]:
        """Remove units killed outside combat (airstrike), reward the opponent."""
        survivors: list[dict] = []
        for u in unit_list:
            if u["hp"] <= 0:
                st = U.unit_stats(u["unit"], u["age"])
                opp = players[1 - u["owner"]]
                opp["gold"] += st["kill_gold"]
                opp["xp"] += st["kill_xp"]
                fx.append(
                    {"kind": "death", "owner": u["owner"], "unit": u["unit"], "x": u["x"]}
                )
            else:
                survivors.append(u)
        return survivors

    def _tiebreak(self, bases: list[dict], players: list[dict]) -> list[int]:
        """Order seats best-first by base HP, then damage dealt, then seat."""
        order = sorted(
            range(2),
            key=lambda s: (-bases[s]["hp"], -players[s]["dmg_dealt"], s),
        )
        return order

    # ── debug ──────────────────────────────────────────────────────────────

    def render_ascii(self, state: dict) -> str:
        length = state["lane"]["length"]
        cols = 60
        row = ["."] * cols
        for b in state["bases"]:
            col = min(cols - 1, int(b["x"] / length * (cols - 1)))
            row[col] = "#"
        for u in state["units"]:
            col = min(cols - 1, int(u["x"] / length * (cols - 1)))
            row[col] = {"pike": "P", "cavalry": "C", "archer": "A"}.get(
                u["unit"], "?"
            ) if u["owner"] == 0 else {"pike": "p", "cavalry": "c", "archer": "a"}.get(
                u["unit"], "?"
            )
        hp = " | ".join(f"s{b['seat']}:{int(b['hp'])}" for b in state["bases"])
        return "".join(row) + "   " + hp
