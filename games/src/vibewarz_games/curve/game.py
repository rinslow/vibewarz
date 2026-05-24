"""Curve — Achtung Die Kurve clone. 4-player free-for-all.

Each player controls a head moving at fixed speed; turning left/right rotates
heading by `turn_rate_deg` per tick. Trail of past positions is left behind.
Crash into any trail (own or others') or the arena wall = die. Last alive wins.

Powerups spawn periodically on the arena. Picking one up grants a temporary
effect: green speeds the picker up, red slows every other living player, and
rainbow grants god mode (immune to walls and trails while your own trail
keeps killing others).

State and action are JSON-serializable dicts. The `step` function is pure.
"""

from __future__ import annotations

import math
import random
from typing import Final

from .._core.base import Game, GameMeta, StepResult
from .._core.registry import register

ARENA_W: Final = 1000.0
ARENA_H: Final = 1000.0
SPEED: Final = 4.8
TURN_RATE_DEG: Final = 6.0
SELF_CLIP_IMMUNE_SEGMENTS: Final = 3  # skip the last N own trail points for self-collision

# Visual palette mirrored by the frontend renderer.
PLAYER_COLORS: Final = ("#a3e635", "#f43f5e", "#38bdf8", "#fbbf24")

VALID_TURNS: Final = ("LEFT", "STRAIGHT", "RIGHT")

# ── powerups ───────────────────────────────────────────────────────────────
POWERUP_KINDS: Final = ("speed", "slow", "god")
POWERUP_DURATION: Final = {"speed": 80, "slow": 80, "god": 50}
POWERUP_SPAWN_INTERVAL: Final = 100  # ticks between spawn attempts
POWERUP_MAX_ALIVE: Final = 3
POWERUP_PICKUP_RADIUS: Final = 18.0
POWERUP_SPAWN_MARGIN: Final = 80.0
POWERUP_MIN_TRAIL_DIST: Final = 40.0
SPEED_BOOST_FACTOR: Final = 1.6
SLOW_FACTOR: Final = 0.55


def _segments_intersect(
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    p4: tuple[float, float],
) -> bool:
    """Standard 2D segment intersection including collinear-overlap.

    Returns True if segment (p1,p2) crosses or overlaps segment (p3,p4).
    """

    def ccw(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def on_segment(
        a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]
    ) -> bool:
        return (
            min(a[0], b[0]) <= c[0] <= max(a[0], b[0])
            and min(a[1], b[1]) <= c[1] <= max(a[1], b[1])
        )

    d1 = ccw(p3, p4, p1)
    d2 = ccw(p3, p4, p2)
    d3 = ccw(p1, p2, p3)
    d4 = ccw(p1, p2, p4)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return True
    # Collinear endpoints lying on the other segment.
    if d1 == 0 and on_segment(p3, p4, p1):
        return True
    if d2 == 0 and on_segment(p3, p4, p2):
        return True
    if d3 == 0 and on_segment(p1, p2, p3):
        return True
    return bool(d4 == 0 and on_segment(p1, p2, p4))


def _spawn_rng(seed: int, tick: int) -> random.Random:
    """Per-tick deterministic RNG for powerup spawn placement."""
    return random.Random(seed * 1_000_003 + tick)


@register
class Curve(Game):
    meta = GameMeta(
        id="curve",
        display_name="Curve",
        min_players=4,
        max_players=4,
        tick_deadline_ms=50,
        tick_interval_ms=50,
        max_ticks=1500,
        description=(
            "4-player free-for-all. Each head moves at constant speed and leaves "
            "a trail. Crash into any trail or the arena wall — you're out. "
            "Last alive wins."
        ),
    )

    # ── lifecycle ──────────────────────────────────────────────────────────

    def initial_state(self, seed: int, num_players: int) -> dict:
        if not (self.meta.min_players <= num_players <= self.meta.max_players):
            raise ValueError(
                f"Curve requires {self.meta.min_players}-{self.meta.max_players} players, "
                f"got {num_players}"
            )

        rng = random.Random(seed)
        margin = 150.0
        players = []
        for seat in range(num_players):
            x = rng.uniform(margin, ARENA_W - margin)
            y = rng.uniform(margin, ARENA_H - margin)
            heading = rng.uniform(0.0, 360.0)
            players.append(
                {
                    "seat": seat,
                    "x": x,
                    "y": y,
                    "heading_deg": heading,
                    "alive": True,
                    "color": PLAYER_COLORS[seat % len(PLAYER_COLORS)],
                    "effects": {},  # kind -> ticks_remaining
                }
            )

        return {
            "tick": 0,
            "seed": seed,
            "arena": {"w": ARENA_W, "h": ARENA_H},
            "speed": SPEED,
            "turn_rate_deg": TURN_RATE_DEG,
            "max_ticks": self.meta.max_ticks,
            "self_clip_immune_segments": SELF_CLIP_IMMUNE_SEGMENTS,
            "players": players,
            "trails": [[(p["x"], p["y"])] for p in players],
            "trail_delta": [[(p["x"], p["y"])] for p in players],
            "placement": [],  # filled in death-order from last to first as players die
            "powerups": [],
            "next_powerup_id": 0,
        }

    def alive_seats(self, state: dict) -> list[int]:
        return [p["seat"] for p in state["players"] if p["alive"]]

    def legal_actions(self, state: dict, seat: int) -> list[dict]:
        return [{"turn": t} for t in VALID_TURNS]

    def is_legal(self, state: dict, seat: int, action: dict) -> bool:
        return isinstance(action, dict) and action.get("turn") in VALID_TURNS

    def default_action(self, state: dict, seat: int) -> dict:
        return {"turn": "STRAIGHT"}

    # ── tick ────────────────────────────────────────────────────────────────

    def step(self, state: dict, actions: dict[int, dict]) -> StepResult:
        new_players = [dict(p) for p in state["players"]]
        # Copy each player's effects dict so we don't mutate the input state.
        for p in new_players:
            p["effects"] = dict(p.get("effects") or {})
        new_trails = [list(t) for t in state["trails"]]
        new_delta: list[list[tuple[float, float]]] = [[] for _ in new_players]
        eliminated: list[int] = []

        # 1) Decay effects: tick down every active effect; drop expired ones.
        for p in new_players:
            if not p["effects"]:
                continue
            decayed: dict[str, int] = {}
            for kind, remaining in p["effects"].items():
                nxt = remaining - 1
                if nxt > 0:
                    decayed[kind] = nxt
            p["effects"] = decayed

        # 2) Per-seat effective speed = base × own boost × any-other-slow.
        slow_active_from_others = any(
            p["alive"] and "slow" in p["effects"] for p in new_players
        )

        def _speed_for(p: dict) -> float:
            s = SPEED
            if "speed" in p["effects"]:
                s *= SPEED_BOOST_FACTOR
            if slow_active_from_others and "slow" not in p["effects"]:
                s *= SLOW_FACTOR
            return s

        # 3) Build proposed new heads using per-seat speed.
        proposals: dict[int, tuple[tuple[float, float], tuple[float, float], float]] = {}
        for p in new_players:
            seat = p["seat"]
            if not p["alive"]:
                continue
            action = actions.get(seat) or self.default_action(state, seat)
            turn = action.get("turn", "STRAIGHT")
            new_heading = p["heading_deg"]
            if turn == "LEFT":
                new_heading -= TURN_RATE_DEG
            elif turn == "RIGHT":
                new_heading += TURN_RATE_DEG
            new_heading %= 360.0
            rad = math.radians(new_heading)
            speed = _speed_for(p)
            new_x = p["x"] + speed * math.cos(rad)
            new_y = p["y"] + speed * math.sin(rad)
            proposals[seat] = ((p["x"], p["y"]), (new_x, new_y), new_heading)

        # 4) Collision detection. God-mode players skip every death check, but
        #    their own trail still kills others (handled later in the trail loop
        #    against the original `state["trails"]`).
        god_seats = {p["seat"] for p in new_players if "god" in p["effects"]}
        dead_this_tick: set[int] = set()
        for seat, (p0, p1, _heading) in proposals.items():
            if seat in god_seats:
                continue
            x, y = p1
            if x < 0.0 or x > ARENA_W or y < 0.0 or y > ARENA_H:
                dead_this_tick.add(seat)
                continue

            for other_seat, trail in enumerate(state["trails"]):
                if not trail:
                    continue
                relevant = trail[:-SELF_CLIP_IMMUNE_SEGMENTS] if other_seat == seat else trail
                for i in range(len(relevant) - 1):
                    if _segments_intersect(p0, p1, relevant[i], relevant[i + 1]):
                        dead_this_tick.add(seat)
                        break
                if seat in dead_this_tick:
                    break

        # Head-on: a god seat doesn't die, but a non-god opponent still does.
        seats = list(proposals.keys())
        head_on_threshold = SPEED  # closer than one tick of base travel = collided
        for i, a in enumerate(seats):
            for b in seats[i + 1 :]:
                _, end_a, _ = proposals[a]
                _, end_b, _ = proposals[b]
                crossed = _segments_intersect(*proposals[a][:2], *proposals[b][:2])
                close = (
                    (end_a[0] - end_b[0]) ** 2 + (end_a[1] - end_b[1]) ** 2
                ) < head_on_threshold**2
                if crossed or close:
                    if a not in god_seats:
                        dead_this_tick.add(a)
                    if b not in god_seats:
                        dead_this_tick.add(b)

        # 5) Apply: living players advance; dead are marked.
        for p in new_players:
            seat = p["seat"]
            if seat not in proposals:
                continue
            _p0, (nx, ny), new_heading = proposals[seat]
            if seat in dead_this_tick:
                p["alive"] = False
                eliminated.append(seat)
            else:
                p["x"] = nx
                p["y"] = ny
                p["heading_deg"] = new_heading
                new_trails[seat].append((nx, ny))
                new_delta[seat].append((nx, ny))

        # 6) Pickup pass: each surviving player picks up the nearest powerup
        #    in radius. Seat order resolves ties on the same pickup.
        powerups = [dict(pu) for pu in (state.get("powerups") or [])]
        pickup_r2 = POWERUP_PICKUP_RADIUS**2
        for p in new_players:
            if not p["alive"] or not powerups:
                continue
            px, py = p["x"], p["y"]
            best_idx = -1
            best_d2 = pickup_r2
            for idx, pu in enumerate(powerups):
                d2 = (pu["x"] - px) ** 2 + (pu["y"] - py) ** 2
                if d2 < best_d2:
                    best_d2 = d2
                    best_idx = idx
            if best_idx >= 0:
                kind = powerups[best_idx]["kind"]
                # Same-kind pickup resets to fresh duration (per plan).
                p["effects"][kind] = POWERUP_DURATION[kind]
                powerups.pop(best_idx)

        # 7) Spawn pass: deterministic per-tick RNG, capped at MAX_ALIVE.
        new_tick = state["tick"] + 1
        next_id = int(state.get("next_powerup_id") or 0)
        if (
            new_tick % POWERUP_SPAWN_INTERVAL == 0
            and len(powerups) < POWERUP_MAX_ALIVE
        ):
            rng = _spawn_rng(int(state.get("seed", 0)), new_tick)
            for _ in range(10):
                x = rng.uniform(POWERUP_SPAWN_MARGIN, ARENA_W - POWERUP_SPAWN_MARGIN)
                y = rng.uniform(POWERUP_SPAWN_MARGIN, ARENA_H - POWERUP_SPAWN_MARGIN)
                if any(
                    (pu["x"] - x) ** 2 + (pu["y"] - y) ** 2 < POWERUP_MIN_TRAIL_DIST**2
                    for pu in powerups
                ):
                    continue
                hit_trail = False
                for trail in new_trails:
                    for tx, ty in trail:
                        if (tx - x) ** 2 + (ty - y) ** 2 < POWERUP_MIN_TRAIL_DIST**2:
                            hit_trail = True
                            break
                    if hit_trail:
                        break
                if hit_trail:
                    continue
                kind = POWERUP_KINDS[rng.randrange(len(POWERUP_KINDS))]
                powerups.append({"id": f"p{next_id}", "kind": kind, "x": x, "y": y})
                next_id += 1
                break

        new_placement = list(state.get("placement") or [])
        for seat in eliminated:
            if seat not in new_placement:
                new_placement.append(seat)

        new_state = {
            **state,
            "tick": new_tick,
            "players": new_players,
            "trails": new_trails,
            "trail_delta": new_delta,
            "placement": new_placement,
            "powerups": powerups,
            "next_powerup_id": next_id,
        }

        alive_after = [p["seat"] for p in new_players if p["alive"]]
        done = len(alive_after) <= 1 or new_state["tick"] >= self.meta.max_ticks
        placement: list[int] | None = None
        reason: str | None = None
        if done:
            survivors = sorted(alive_after)
            deaths_reversed = list(reversed(new_placement))
            placement = survivors + deaths_reversed
            if state["tick"] + 1 >= self.meta.max_ticks and len(alive_after) > 1:
                reason = "timeout"
            else:
                reason = "elimination"

        return StepResult(
            state=new_state,
            done=done,
            placement=placement,
            reason=reason,
            eliminated_this_tick=tuple(eliminated),
        )

    def render_ascii(self, state: dict) -> str:
        cols, rows = 60, 30
        grid = [[" "] * cols for _ in range(rows)]
        for seat, trail in enumerate(state["trails"]):
            ch = str(seat)
            for x, y in trail:
                c = int(x / ARENA_W * cols)
                r = int(y / ARENA_H * rows)
                if 0 <= r < rows and 0 <= c < cols:
                    grid[r][c] = ch
        return "\n".join("".join(row) for row in grid)
