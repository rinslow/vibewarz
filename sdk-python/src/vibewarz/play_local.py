"""In-process match runner — no server, no auth, no network.

Loads N bot classes from `.py` files, instantiates a game from
`vibewarz_games`, runs the tick loop, and prints the placement at the end.

Mirrors the server's MatchRunner semantics (acting_seats, view_for,
default_action substitution on missing/illegal actions) without the
WebSocket layer.
"""

from __future__ import annotations

import importlib.util
import random
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

from vibewarz_games import GAMES, Game

from .bot import Bot


@dataclass
class LocalResult:
    match_id: str
    placement: list[int]
    reason: str
    ticks: int


def _load_bot_class(path: Path) -> type[Bot]:
    spec = importlib.util.spec_from_file_location(f"_user_bot_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load bot module {path}")
    mod = importlib.util.module_from_spec(spec)
    # Use a unique key so two `--bot` paths to the same file work.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    for name in dir(mod):
        obj = getattr(mod, name)
        if isinstance(obj, type) and issubclass(obj, Bot) and obj is not Bot:
            return obj
    raise RuntimeError(f"no Bot subclass found in {path}")


def play(
    game_id: str,
    bot_paths: list[Path],
    *,
    seed: int | None = None,
    max_ticks: int | None = None,
    verbose: bool = False,
) -> LocalResult:
    if game_id not in GAMES:
        raise RuntimeError(f"unknown game {game_id!r}; known: {sorted(GAMES)}")
    game: Game = GAMES[game_id]()
    meta = game.meta

    num_players = len(bot_paths)
    if num_players < meta.min_players:
        raise RuntimeError(
            f"{game_id} needs >= {meta.min_players} players, got {num_players}"
        )
    if num_players > meta.max_players:
        raise RuntimeError(
            f"{game_id} allows <= {meta.max_players} players, got {num_players}"
        )

    bots: list[Bot] = []
    for seat, path in enumerate(bot_paths):
        cls = _load_bot_class(path)
        bot = cls()
        bot.seat = seat
        bot.match_id = "local"
        bot.players = None
        # Allow bots that don't set `game` to play here; warn on mismatch.
        if getattr(bot, "game", "") and bot.game != game_id:
            print(
                f"warning: {path.name} declares game={bot.game!r}, "
                f"running it under {game_id!r} anyway",
                file=sys.stderr,
            )
        bots.append(bot)

    seed = seed if seed is not None else random.randrange(2**31)
    state = game.initial_state(seed=seed, num_players=num_players)

    for bot in bots:
        bot.on_start(state)

    match_id = f"local_{uuid.uuid4().hex[:8]}"
    limit = max_ticks if max_ticks is not None else meta.max_ticks

    placement: list[int] = []
    reason = "max_ticks"
    tick = 0

    while tick < limit:
        actions: dict[int, dict] = {}
        for seat in game.acting_seats(state):
            view = game.view_for(state, seat)
            try:
                out = bots[seat].act(view)
            except Exception as e:  # noqa: BLE001
                if verbose:
                    print(f"seat {seat} raised in act(): {e!r}", file=sys.stderr)
                actions[seat] = game.default_action(state, seat)
                continue
            action = out[0] if isinstance(out, tuple) else out
            if not isinstance(action, dict) or not game.is_legal(state, seat, action):
                if verbose:
                    print(
                        f"seat {seat} returned illegal action {action!r}; substituting default",
                        file=sys.stderr,
                    )
                actions[seat] = game.default_action(state, seat)
            else:
                actions[seat] = action

        result = game.step(state, actions)
        state = result.state
        tick += 1

        if verbose and result.eliminated_this_tick:
            print(f"tick {tick}: eliminated {list(result.eliminated_this_tick)}", file=sys.stderr)

        if result.done:
            placement = result.placement or []
            reason = result.reason or "done"
            break

    for bot in bots:
        bot.on_end(placement, reason)

    return LocalResult(match_id=match_id, placement=placement, reason=reason, ticks=tick)
