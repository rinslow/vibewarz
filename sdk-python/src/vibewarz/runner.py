"""High-level `run()` — wires a `Bot` to the protocol and prints results.

Usage:
    from vibewarz import CurveAction, CurveBot, CurveState, run
    class MyBot(CurveBot):
        def act(self, state: CurveState): return CurveAction(turn="STRAIGHT")
    run(MyBot(), mode="practice", loop=10)
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

import websockets.exceptions

from .bot import Bot
from .client import Client, default_api_url
from .protocol import (
    ActionC2S,
    ErrorS2C,
    GameEndS2C,
    GameStartS2C,
    MatchFoundS2C,
    QueuedS2C,
    RatingUpdateS2C,
    TickRequestS2C,
    TickResultS2C,
)
from .state_accumulator import StateAccumulator

log = logging.getLogger(__name__)


async def _play_one_match(client: Client, bot: Bot, mode: str, bot_label: str | None) -> GameEndS2C:
    await client.queue(bot.game, mode=mode, bot_label=bot_label)

    bot.seat = -1
    bot.match_id = None
    bot.players = None
    # Server sends a full snapshot in GameStartS2C and per-tick deltas in
    # TickRequest/Result (see vibewarz_games._core.base.Game.delta_view_for).
    # The accumulator reconstructs the live state so bot.act() keeps
    # receiving a full state — no per-bot delta handling required.
    accumulator = StateAccumulator()

    async for msg in client.messages():
        if isinstance(msg, QueuedS2C):
            continue
        if isinstance(msg, MatchFoundS2C):
            bot.seat = msg.your_seat
            bot.match_id = msg.match_id
            bot.players = msg.players
            continue
        if isinstance(msg, GameStartS2C):
            state = accumulator.on_snapshot(msg.state)
            bot.on_start(bot._coerce_state(state))
            continue
        if isinstance(msg, TickRequestS2C):
            state = accumulator.on_delta(msg.state)
            action, reasoning = bot._normalize_action_output(
                bot.act(bot._coerce_state(state))
            )
            await client.send(
                ActionC2S(
                    id="a",
                    match_id=msg.match_id,
                    tick=msg.tick,
                    action=action,
                    reasoning=reasoning,
                )
            )
            continue
        if isinstance(msg, TickResultS2C):
            # Keep the accumulator in sync; bot doesn't observe tick_result
            # directly — its next act() will see the post-step state.
            accumulator.on_delta(msg.state)
            continue
        if isinstance(msg, RatingUpdateS2C):
            continue
        if isinstance(msg, GameEndS2C):
            # final_state is a full snapshot (per delta_view_for contract);
            # treat it as such so a hypothetical post-end consumer reads a
            # clean cumulative state.
            accumulator.on_snapshot(msg.final_state)
            bot.on_end(msg.placement, msg.reason)
            return msg
        if isinstance(msg, ErrorS2C):
            if msg.fatal:
                raise RuntimeError(f"server error: {msg.code}: {msg.message}")
            # Non-fatal errors are surfaced as WARNING so silent server-side
            # drops (e.g. a rate_limited QueueC2S) don't leave the bot
            # hanging in client.messages() with no diagnostic — see
            # vibe-warz-platform issue #69.
            log.warning("non-fatal server error: %s %s", msg.code, msg.message)
            continue

    raise RuntimeError("ws closed before game_end")


def run(
    bot: Bot,
    *,
    mode: str = "ranked",
    loop: int = 1,
    api_url: str | None = None,
    api_key_env: str = "VIBEWARZ_API_KEY",
    guest_name: str | None = None,
    bot_label: str | None = None,
) -> None:
    """Connect, play `loop` matches, print one-line summaries, exit."""

    api_key = os.environ.get(api_key_env)
    url = api_url or default_api_url()

    async def _go() -> None:
        async with Client(url=url, api_key=api_key, guest_name=guest_name) as client:
            handle = client.user.handle if client.user else "?"
            for i in range(loop):
                end = await _play_one_match(client, bot, mode, bot_label)
                place = end.placement.index(bot.seat) + 1 if bot.seat in end.placement else "?"
                print(
                    f"[{handle}] match {i + 1}/{loop} {end.match_id}: "
                    f"placed {place}/{len(end.placement)} "
                    f"({end.reason})",
                    file=sys.stderr,
                )

    try:
        asyncio.run(_go())
    except (
        ConnectionRefusedError,
        OSError,
        websockets.exceptions.InvalidHandshake,
        websockets.exceptions.InvalidURI,
    ) as e:
        # Wrap raw network errors with the env-var hint. The default URL
        # is prod, so the most likely cause of failure here is a typo'd
        # override or someone running an old client against a stopped
        # dev server.
        raise SystemExit(
            f"Couldn't reach vibewarz at {url}: {e}\n"
            "Set VIBEWARZ_API_URL to override (default is the prod arena)."
        ) from e
