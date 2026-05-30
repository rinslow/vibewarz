"""Blast — grid-based last-bot-standing free-for-all.

2-4 player FFA on a 13x11 grid. Every tick each alive player picks a
direction (or stay) and optionally drops a bomb on their current tile.
Bombs explode after a fixed fuse, hurling flames along the four cardinal
rays — flames destroy soft blocks (which can drop powerups) and kill
players. A flame on a bomb chains it immediately. Last alive wins; a
sudden-death ring closes inward after tick 300 so matches can't camp out
the clock.

Movement is one tile per tick (gated by a per-player cooldown), so the
engine is fully discrete and reproducible. The `step` function is pure;
all randomness comes from a fresh ``random.Random`` keyed on
``(seed, tick)`` so two identical action streams yield byte-identical
state sequences.
"""

from __future__ import annotations

import random
from typing import Final

from .._core.base import Game, GameMeta, StepResult
from .._core.registry import register
from .board import BOARD_H, BOARD_W, generate_board
from .bombs import explosion_tiles

# ── timing & rules ─────────────────────────────────────────────────────────
# Ticks run at 100ms (10 Hz). Combined with the default 2-tick move cooldown
# this gives 5 tiles/s base movement and ~10 tiles/s with a speed pickup —
# arcade-y, but slow enough that LLM/heuristic bots can keep up.
MAX_TICKS: Final = 600
SHRINK_START_TICK: Final = 300
SHRINK_STEP: Final = 8

BOMB_FUSE: Final = 20         # ~2.0s at 100ms ticks
FLAME_LIFETIME: Final = 5     # ~0.5s
POWERUP_DROP_FROM_SOFT: Final = 0.30

# ── per-player caps & starting stats ───────────────────────────────────────
STARTING_BOMBS_MAX: Final = 1
STARTING_RANGE: Final = 2
STARTING_COOLDOWN: Final = 2  # ticks between successful moves

BOMB_CAP: Final = 8
RANGE_CAP: Final = 10
MIN_COOLDOWN: Final = 1  # i.e. one tile per tick is the speed ceiling

# Brand-aligned palette mirrored by the frontend renderer.
PLAYER_COLORS: Final = ("#a3e635", "#f43f5e", "#38bdf8", "#fbbf24")

MOVES: Final = ("up", "down", "left", "right", "stay")
MOVE_DELTAS: Final = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
    "stay": (0, 0),
}

POWERUP_KINDS: Final = ("bomb", "range", "speed")


def _step_rng(seed: int, tick: int) -> random.Random:
    """Per-tick deterministic RNG for powerup spawns and on-death drops."""
    return random.Random(int(seed) * 1_000_003 + int(tick))


def _bomb_at(bombs: list[dict], x: int, y: int) -> bool:
    return any(b["x"] == x and b["y"] == y for b in bombs)


def _shrink_ring_index(tick: int) -> int | None:
    """Which shrink ring (1-based, measured inward from the border) should
    activate exactly on ``tick`` — or None if no new ring activates."""
    if tick < SHRINK_START_TICK:
        return None
    offset = tick - SHRINK_START_TICK
    if offset % SHRINK_STEP != 0:
        return None
    return offset // SHRINK_STEP + 1


def _ring_tiles(k: int) -> set[tuple[int, int]]:
    """The set of cells whose Chebyshev distance from the nearest edge is
    exactly ``k``. ``k == 0`` is the existing outer border."""
    out: set[tuple[int, int]] = set()
    for y in range(BOARD_H):
        for x in range(BOARD_W):
            if min(x, BOARD_W - 1 - x, y, BOARD_H - 1 - y) == k:
                out.add((x, y))
    return out


@register
class Blast(Game):
    meta = GameMeta(
        id="blast",
        display_name="Blast",
        min_players=2,
        max_players=4,
        tick_deadline_ms=100,
        tick_interval_ms=100,
        max_ticks=MAX_TICKS,
        match_wait_ms=3_000,
        description=(
            "Plant bombs, dodge blasts, out-position your opponents. "
            "Last one standing wins."
        ),
    )

    # ── lifecycle ──────────────────────────────────────────────────────────

    def initial_state(self, seed: int, num_players: int) -> dict:
        if not (self.meta.min_players <= num_players <= self.meta.max_players):
            raise ValueError(
                f"Blast requires {self.meta.min_players}-{self.meta.max_players}"
                f" players, got {num_players}"
            )
        board, spawns = generate_board(seed, num_players)
        players = []
        for seat in range(num_players):
            x, y = spawns[seat]
            players.append(
                {
                    "seat": seat,
                    "x": x,
                    "y": y,
                    "alive": True,
                    "color": PLAYER_COLORS[seat % len(PLAYER_COLORS)],
                    "bombs_max": STARTING_BOMBS_MAX,
                    "bombs_active": 0,
                    "blast_range": STARTING_RANGE,
                    "move_cooldown": STARTING_COOLDOWN,
                    "move_cooldown_remaining": 0,
                    "powerup_counts": {"bomb": 0, "range": 0, "speed": 0},
                }
            )
        return {
            "tick": 0,
            "seed": seed,
            "dims": {"w": BOARD_W, "h": BOARD_H},
            "board": board,
            "max_ticks": MAX_TICKS,
            "shrink_start_tick": SHRINK_START_TICK,
            "shrink_step": SHRINK_STEP,
            "players": players,
            "bombs": [],
            "flames": [],
            "powerups": [],
            "next_powerup_id": 0,
            "placement": [],
        }

    def alive_seats(self, state: dict) -> list[int]:
        return [p["seat"] for p in state["players"] if p["alive"]]

    # Blast is public-information; default acting_seats (all alive,
    # simultaneous-move) and view_for (full state) inherited from Game.

    # ── action validation ──────────────────────────────────────────────────

    def legal_actions(self, state: dict, seat: int) -> list[dict]:
        player = state["players"][seat]
        if not player["alive"]:
            return [{"move": "stay", "drop_bomb": False}]
        can_drop = (
            player["bombs_active"] < player["bombs_max"]
            and not _bomb_at(state["bombs"], player["x"], player["y"])
        )
        actions: list[dict] = []
        for move in MOVES:
            actions.append({"move": move, "drop_bomb": False})
            if can_drop:
                actions.append({"move": move, "drop_bomb": True})
        return actions

    def is_legal(self, state: dict, seat: int, action: dict) -> bool:
        if not isinstance(action, dict):
            return False
        move = action.get("move")
        drop = action.get("drop_bomb", False)
        if move not in MOVES:
            return False
        # A drop_bomb with no spare bomb, or onto a tile that already holds a
        # bomb, is resolved as a harmless no-op in step() (see the guards in
        # the drop-bomb phase) — so it stays legal, not an elimination-worthy
        # illegal action. legal_actions() still gates these out so bots aren't
        # offered pointless drops.
        return isinstance(drop, bool)

    def default_action(self, state: dict, seat: int) -> dict:
        return {"move": "stay", "drop_bomb": False}

    # ── tick ───────────────────────────────────────────────────────────────

    def step(self, state: dict, actions: dict[int, dict]) -> StepResult:
        rng = _step_rng(state.get("seed", 0), state["tick"])

        board = [row[:] for row in state["board"]]
        players = [{**p, "powerup_counts": dict(p.get("powerup_counts") or {})}
                   for p in state["players"]]
        bombs = [dict(b) for b in state["bombs"]]
        flames = [dict(f) for f in state["flames"]]
        powerups = [dict(pu) for pu in state["powerups"]]
        next_powerup_id = int(state.get("next_powerup_id") or 0)
        placement = list(state.get("placement") or [])
        eliminated_this_tick: list[int] = []

        # 1) Age existing flames.
        flames = [
            {**f, "timer": f["timer"] - 1} for f in flames if f["timer"] - 1 > 0
        ]

        # 2) Age bomb fuses.
        for b in bombs:
            b["timer"] -= 1

        # 3) Resolve explosions with chain reactions. A flame landing on
        # another bomb's tile makes that bomb explode this same tick.
        exploded: set[int] = set()
        queue = [i for i, b in enumerate(bombs) if b["timer"] <= 0]
        new_flame_tiles: set[tuple[int, int]] = set()
        # Aggregated destroyed-soft tiles; powerup spawn happens AFTER the
        # flame-vs-powerup filter below so freshly-spawned pickups survive
        # the explosion that revealed them (classic Blast behaviour).
        destroyed_this_tick: set[tuple[int, int]] = set()
        while queue:
            idx = queue.pop(0)
            if idx in exploded:
                continue
            exploded.add(idx)
            b = bombs[idx]
            flame_set, destroyed_soft = explosion_tiles(
                board, b["x"], b["y"], b["range"]
            )
            new_flame_tiles |= flame_set
            for dx, dy in destroyed_soft:
                board[dy][dx] = "empty"
                destroyed_this_tick.add((dx, dy))
            owner = b.get("owner", -1)
            if 0 <= owner < len(players):
                players[owner]["bombs_active"] = max(
                    0, players[owner]["bombs_active"] - 1
                )
            for j, ob in enumerate(bombs):
                if j in exploded or j in queue:
                    continue
                if (ob["x"], ob["y"]) in new_flame_tiles:
                    ob["timer"] = 0
                    queue.append(j)

        # Add the new flames, replacing any pre-existing flame on the same
        # tile (refreshing its timer feels right and is deterministic).
        if new_flame_tiles:
            flames = [f for f in flames if (f["x"], f["y"]) not in new_flame_tiles]
            for fx, fy in sorted(new_flame_tiles):
                flames.append({"x": fx, "y": fy, "timer": FLAME_LIFETIME})

        # Powerups caught in the blast are destroyed — but only ones that
        # existed before this tick. Spawn new pickups from destroyed soft
        # blocks AFTER this filter so they survive the flame they were
        # revealed by.
        if new_flame_tiles:
            powerups = [
                pu for pu in powerups if (pu["x"], pu["y"]) not in new_flame_tiles
            ]
        for dx, dy in sorted(destroyed_this_tick):
            if rng.random() < POWERUP_DROP_FROM_SOFT:
                kind = POWERUP_KINDS[rng.randrange(len(POWERUP_KINDS))]
                powerups.append(
                    {"id": f"pu{next_powerup_id}", "x": dx, "y": dy, "kind": kind}
                )
                next_powerup_id += 1

        # Drop exploded bombs.
        bombs = [b for i, b in enumerate(bombs) if i not in exploded]

        # 4) Drop-bomb actions resolve before movement so the bomb lands on
        # the seat's pre-move tile (classic feel — drop and step off).
        for seat in sorted(actions.keys()):
            if seat < 0 or seat >= len(players):
                continue
            p = players[seat]
            if not p["alive"]:
                continue
            action = actions.get(seat) or self.default_action(state, seat)
            if not action.get("drop_bomb"):
                continue
            if p["bombs_active"] >= p["bombs_max"]:
                continue
            if _bomb_at(bombs, p["x"], p["y"]):
                continue
            bombs.append(
                {
                    "x": p["x"],
                    "y": p["y"],
                    "timer": BOMB_FUSE,
                    "owner": seat,
                    "range": p["blast_range"],
                }
            )
            p["bombs_active"] += 1

        # 5) Movement. Cooldown first, then collect intended moves, then
        # resolve same-tile contention with seat-asc tiebreaker.
        for p in players:
            if p["alive"] and p["move_cooldown_remaining"] > 0:
                p["move_cooldown_remaining"] -= 1

        intended: dict[int, tuple[int, int]] = {}
        for p in players:
            seat = p["seat"]
            if not p["alive"] or p["move_cooldown_remaining"] > 0:
                continue
            action = actions.get(seat) or self.default_action(state, seat)
            move = action.get("move", "stay")
            if move == "stay":
                continue
            dx, dy = MOVE_DELTAS[move]
            tx, ty = p["x"] + dx, p["y"] + dy
            if not (0 <= tx < BOARD_W and 0 <= ty < BOARD_H):
                continue
            if board[ty][tx] in ("hard", "soft"):
                continue
            if _bomb_at(bombs, tx, ty):
                continue
            intended[seat] = (tx, ty)

        winner_for_tile: dict[tuple[int, int], int] = {}
        for seat in sorted(intended.keys()):
            target = intended[seat]
            winner_for_tile.setdefault(target, seat)

        for seat, target in intended.items():
            if winner_for_tile.get(target) != seat:
                continue
            p = players[seat]
            p["x"], p["y"] = target
            # Reset full cooldown; it ticks down at the start of each
            # subsequent step, so cooldown=2 yields one move every 2 ticks.
            p["move_cooldown_remaining"] = p["move_cooldown"]

        # 6) Powerup pickup. Seat-asc precedence on the rare case that two
        # players land on the same powerup the same tick.
        remaining_powerups: list[dict] = []
        for pu in powerups:
            taker: dict | None = None
            for p in players:
                if (
                    p["alive"]
                    and p["x"] == pu["x"]
                    and p["y"] == pu["y"]
                ) and (taker is None or p["seat"] < taker["seat"]):
                    taker = p
            if taker is None:
                remaining_powerups.append(pu)
                continue
            kind = pu["kind"]
            if kind == "bomb":
                taker["bombs_max"] = min(BOMB_CAP, taker["bombs_max"] + 1)
            elif kind == "range":
                taker["blast_range"] = min(RANGE_CAP, taker["blast_range"] + 1)
            elif kind == "speed":
                taker["move_cooldown"] = max(
                    MIN_COOLDOWN, taker["move_cooldown"] - 1
                )
            counts = taker["powerup_counts"]
            counts[kind] = counts.get(kind, 0) + 1
        powerups = remaining_powerups

        new_tick = state["tick"] + 1

        # 7) Sudden-death shrink. On the tick a new ring activates, mark
        # every cell in that ring as hard and clear out anything sitting
        # on it. Bombs on the ring are destroyed silently (no chain — the
        # walls just crush them); powerups vanish; players die without a
        # drop (their stuff goes with the wall).
        ring_idx = _shrink_ring_index(new_tick)
        if ring_idx is not None:
            ring = _ring_tiles(ring_idx)
            for x, y in ring:
                if board[y][x] != "hard":
                    board[y][x] = "hard"
            crushed_bombs = []
            for b in bombs:
                if (b["x"], b["y"]) in ring:
                    owner = b.get("owner", -1)
                    if 0 <= owner < len(players):
                        players[owner]["bombs_active"] = max(
                            0, players[owner]["bombs_active"] - 1
                        )
                else:
                    crushed_bombs.append(b)
            bombs = crushed_bombs
            powerups = [pu for pu in powerups if (pu["x"], pu["y"]) not in ring]
            flames = [f for f in flames if (f["x"], f["y"]) not in ring]
            for p in players:
                if p["alive"] and (p["x"], p["y"]) in ring:
                    p["alive"] = False
                    if p["seat"] not in placement:
                        placement.append(p["seat"])
                    eliminated_this_tick.append(p["seat"])

        # 8) Flame collision: alive players standing on flame die and may
        # drop one of their held powerups (seeded RNG, deterministic).
        flame_set = {(f["x"], f["y"]) for f in flames}
        for p in players:
            if not p["alive"]:
                continue
            if (p["x"], p["y"]) not in flame_set:
                continue
            p["alive"] = False
            counts = p["powerup_counts"]
            held = [k for k, v in counts.items() if v > 0]
            if held:
                drop_kind = held[rng.randrange(len(held))]
                powerups.append(
                    {
                        "id": f"pu{next_powerup_id}",
                        "x": p["x"],
                        "y": p["y"],
                        "kind": drop_kind,
                    }
                )
                next_powerup_id += 1
                counts[drop_kind] -= 1
            if p["seat"] not in placement:
                placement.append(p["seat"])
            eliminated_this_tick.append(p["seat"])

        new_state = {
            **state,
            "tick": new_tick,
            "board": board,
            "players": players,
            "bombs": bombs,
            "flames": flames,
            "powerups": powerups,
            "next_powerup_id": next_powerup_id,
            "placement": placement,
        }

        alive_after = [p["seat"] for p in players if p["alive"]]
        done = len(alive_after) <= 1 or new_tick >= self.meta.max_ticks
        final_placement: list[int] | None = None
        reason: str | None = None
        if done:
            survivors = sorted(alive_after)
            deaths_reversed = list(reversed(placement))
            final_placement = survivors + deaths_reversed
            reason = "elimination" if len(alive_after) <= 1 else "timeout"

        return StepResult(
            state=new_state,
            done=done,
            placement=final_placement,
            reason=reason,
            eliminated_this_tick=tuple(eliminated_this_tick),
        )

    # ── debug ──────────────────────────────────────────────────────────────

    def render_ascii(self, state: dict) -> str:
        board = state["board"]
        grid = [[("#" if c == "hard" else "*" if c == "soft" else ".") for c in row]
                for row in board]
        for pu in state["powerups"]:
            sym = {"bomb": "b", "range": "r", "speed": "s"}.get(pu["kind"], "?")
            grid[pu["y"]][pu["x"]] = "+" + sym
        for b in state["bombs"]:
            grid[b["y"]][b["x"]] = "B"
        for f in state["flames"]:
            grid[f["y"]][f["x"]] = "X"
        for p in state["players"]:
            if p["alive"]:
                grid[p["y"]][p["x"]] = str(p["seat"])
        return "\n".join(
            "".join(cell if len(cell) == 1 else cell for cell in row) for row in grid
        )
