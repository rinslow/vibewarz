"""In-process match runner — no server, no auth, no network.

Loads N bot classes from `.py` files, instantiates a game from
`vibewarz_games`, runs the tick loop, and prints the placement at the end.

Mirrors the server's MatchRunner semantics (acting_seats, view_for,
default_action substitution on missing/illegal actions) without the
WebSocket layer.
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import random
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from vibewarz_games import GAMES, Game

from .bot import Bot
from .protocol.replay import GameEndEvt, GameStartEvt, TickResultEvt

DEFAULT_REPLAY_DIR = Path("./data/replays")


@dataclass
class LocalResult:
    match_id: str
    placement: list[int]
    reason: str
    ticks: int
    replay_path: Path | None = None


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
        if (
            isinstance(obj, type)
            and issubclass(obj, Bot)
            and obj is not Bot
            and obj.__module__ == mod.__name__
        ):
            return obj
    raise RuntimeError(f"no Bot subclass found in {path}")


def _ts_ms() -> int:
    return int(time.time() * 1000)


class _ReplayJournal:
    """Atomic JSONL writer for one match.

    Writes to `{match_id}.jsonl.tmp` in the target directory, then renames to
    `{match_id}.jsonl` on close(). A crashed match leaves the .tmp behind
    rather than a half-truncated .jsonl — so `vibewarz replay <id>` can't
    open a torn file. Same atomic-rename pattern the server-side
    LocalReplayStore uses.
    """

    def __init__(self, directory: Path, match_id: str) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self.match_id = match_id
        self.final_path = directory / f"{match_id}.jsonl"
        self.tmp_path = directory / f"{match_id}.jsonl.tmp"
        self._fh = self.tmp_path.open("w", encoding="utf-8")

    def write(self, model: GameStartEvt | TickResultEvt | GameEndEvt) -> None:
        # model_dump(mode="json") materializes the same JSON shape that
        # /api/replays/{id} returns and that @vibewarz/replay-viewer expects.
        self._fh.write(json.dumps(model.model_dump(mode="json"), separators=(",", ":")))
        self._fh.write("\n")

    def close(self) -> Path:
        self._fh.flush()
        os.fsync(self._fh.fileno())
        self._fh.close()
        os.replace(self.tmp_path, self.final_path)
        return self.final_path

    def abort(self) -> None:
        # Called on exception. Don't promote the .tmp; let the caller
        # surface the underlying error.
        try:
            self._fh.close()
        finally:
            with contextlib.suppress(FileNotFoundError):
                self.tmp_path.unlink()


def play(
    game_id: str,
    bot_paths: list[Path],
    *,
    seed: int | None = None,
    max_ticks: int | None = None,
    verbose: bool = False,
    record: bool = True,
    replay_dir: Path | None = None,
    names: list[str] | None = None,
) -> LocalResult:
    if game_id not in GAMES:
        raise RuntimeError(f"unknown game {game_id!r}; known: {sorted(GAMES)}")
    game: Game = GAMES[game_id]()
    meta = game.meta

    num_players = len(bot_paths)
    if names is not None and len(names) != num_players:
        raise RuntimeError(
            f"got {len(names)} names for {num_players} bots; pass --name once per --bot"
        )
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
        initial_view = game.snapshot_view_for(state, bot.seat)
        bot.on_start(bot._coerce_state(initial_view))

    match_id = f"local_{uuid.uuid4().hex[:8]}"
    limit = max_ticks if max_ticks is not None else meta.max_ticks

    journal: _ReplayJournal | None = None
    if record:
        target_dir = replay_dir if replay_dir is not None else DEFAULT_REPLAY_DIR
        journal = _ReplayJournal(target_dir.resolve(), match_id)
        journal.write(
            GameStartEvt(
                seed=seed,
                state=state,
                match_id=match_id,
                game_id=game_id,
                names={seat: name for seat, name in enumerate(names)} if names else None,
            )
        )

    placement: list[int] = []
    reason = "max_ticks"
    tick = 0

    try:
        while tick < limit:
            actions: dict[int, dict] = {}
            for seat in game.acting_seats(state):
                view = game.view_for(state, seat)
                try:
                    out = bots[seat].act(bots[seat]._coerce_state(view))
                except Exception as e:  # noqa: BLE001
                    if verbose:
                        print(f"seat {seat} raised in act(): {e!r}", file=sys.stderr)
                    actions[seat] = game.default_action(state, seat)
                    continue
                action, _reasoning = bots[seat]._normalize_action_output(out)
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

            if journal is not None:
                journal.write(
                    TickResultEvt(
                        ts=_ts_ms(),
                        match_id=match_id,
                        # journal_view drops cumulative fields a viewer can
                        # rebuild from deltas (Curve's growing `trails`), so
                        # the replay stays O(N) instead of O(N²). game_start
                        # below keeps the full snapshot to anchor that rebuild.
                        tick=tick,
                        state=game.journal_view(state),
                        actions={seat: act for seat, act in actions.items()},
                        eliminated=list(result.eliminated_this_tick),
                    )
                )

            if verbose and result.eliminated_this_tick:
                print(f"tick {tick}: eliminated {list(result.eliminated_this_tick)}", file=sys.stderr)

            if result.done:
                placement = result.placement or []
                reason = result.reason or "done"
                break

        for bot in bots:
            bot.on_end(placement, reason)

        replay_path: Path | None = None
        if journal is not None:
            journal.write(
                GameEndEvt(
                    ts=_ts_ms(),
                    match_id=match_id,
                    placement=placement,
                    reason=reason,
                    final_state=state,
                )
            )
            replay_path = journal.close()
            journal = None
    finally:
        if journal is not None:
            journal.abort()

    return LocalResult(
        match_id=match_id,
        placement=placement,
        reason=reason,
        ticks=tick,
        replay_path=replay_path,
    )
