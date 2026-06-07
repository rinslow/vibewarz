# vibewarz

Open-source bot-vs-bot arena. Write a Python bot, climb the ELO leaderboard at [vibewarz.com](https://vibewarz.com).

This repo contains the public surface:

| Package | What |
|---|---|
| [`sdk-python/`](sdk-python/) | `vibewarz` — Bot base class, WebSocket client, protocol models, `play-local` harness |
| [`games/`](games/) | `vibewarz-games` — pure Python game engines (Curve, Poker, Blast) |
| [`sample-bots/`](sample-bots/) | Reference bots you can fork |
| [`docs/`](docs/) | Protocol spec + quickstart + game-authoring guide |

The closed-source platform (server, web UI, infra) lives at [OmriGanor/vibe-warz-platform](https://github.com/OmriGanor/vibe-warz-platform).

## Quickstart

```bash
pip install vibewarz vibewarz-games

# Run a 4-bot Curve match locally — no server, no auth:
vibewarz play-local --game curve \
  --bot sample-bots/curve_wall_avoid.py \
  --bot sample-bots/curve_wall_avoid.py \
  --bot sample-bots/curve_wall_avoid.py \
  --bot sample-bots/curve_wall_avoid.py

# Or 2-bot heads-up poker:
vibewarz play-local --game poker \
  --bot sample-bots/poker_random.py \
  --bot sample-bots/poker_random.py
```

Write your own:

```python
# my_bot.py
from vibewarz import CurveAction, CurveBot, CurveState

class MyBot(CurveBot):
    def act(self, state: CurveState):
        return CurveAction(turn="STRAIGHT")
```

```bash
# 4 players minimum for curve; mix yours with samples:
vibewarz play-local --game curve \
  --bot my_bot.py \
  --bot sample-bots/curve_wall_avoid.py \
  --bot sample-bots/curve_wall_avoid.py \
  --bot sample-bots/curve_wall_avoid.py
```

Ready to climb the ladder?

1. Sign in at [vibewarz.com](https://vibewarz.com) with Google.
2. Open [vibewarz.com/account](https://vibewarz.com/account) and create a bot — copy the key (shown once).
3. Run your bot against the live arena:

   ```bash
   export VIBEWARZ_API_KEY=vw_live_...
   vibewarz play my_bot.py --mode ranked --loop 50
   ```

The SDK defaults to the production arena (`wss://api.vibewarz.com/ws`). Override with `VIBEWARZ_API_URL` only when pointing at a local or staging server.

See [`docs/QUICKSTART.md`](docs/QUICKSTART.md) for the full walkthrough, [`docs/WRITING_A_BOT.md`](docs/WRITING_A_BOT.md) for the bot API, and [`docs/PROTOCOL.md`](docs/PROTOCOL.md) for the wire spec.

## Develop on this repo

```bash
uv sync --all-extras
make test     # pytest games + sdk
make lint     # ruff
```

## License

MIT — see [LICENSE](LICENSE).
