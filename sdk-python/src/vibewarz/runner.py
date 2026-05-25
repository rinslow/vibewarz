"""High-level `run()` — wires a `Bot` to the protocol and prints results.

Usage:
    from vibewarz import Bot, run
    class MyBot(Bot):
        game = "curve"
        def act(self, state): return {"turn": "STRAIGHT"}
    run(MyBot(), mode="practice", loop=10)
"""

from __future__ import annotations

import asyncio
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


async def _play_one_match(client: Client, bot: Bot, mode: str, bot_label: str | None) -> GameEndS2C:
    await client.queue(bot.game, mode=mode, bot_label=bot_label)

    bot.seat = -1
    bot.match_id = None
    bot.players = None

    async for msg in client.messages():
        if isinstance(msg, QueuedS2C):
            continue
        if isinstance(msg, MatchFoundS2C):
            bot.seat = msg.your_seat
            bot.match_id = msg.match_id
            bot.players = msg.players
            continue
        if isinstance(msg, GameStartS2C):
            bot.on_start(msg.state)
            continue
        if isinstance(msg, TickRequestS2C):
            action_or_pair = bot.act(msg.state)
            if isinstance(action_or_pair, tuple):
                action, reasoning = action_or_pair
            else:
                action, reasoning = action_or_pair, None
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
        if isinstance(msg, TickResultS2C | RatingUpdateS2C):
            continue
        if isinstance(msg, GameEndS2C):
            bot.on_end(msg.placement, msg.reason)
            return msg
        if isinstance(msg, ErrorS2C) and msg.fatal:
            raise RuntimeError(f"server error: {msg.code}: {msg.message}")
        # non-fatal ErrorS2C: keep going

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
