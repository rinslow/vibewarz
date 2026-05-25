# Quickstart

A 5-minute path from "fresh venv" to "two bots playing each other locally."

## Install

```bash
pip install vibewarz vibewarz-games
```

## Run the demo

Clone this repo (or download just the `sample-bots/` directory) and run:

```bash
vibewarz play-local --game curve \
  --bot sample-bots/curve_wall_avoid.py \
  --bot sample-bots/curve_wall_avoid.py \
  --bot sample-bots/curve_wall_avoid.py \
  --bot sample-bots/curve_wall_avoid.py
```

You should see output like:

```
local_a1b2c3d4: placement=[3, 0, 1, 2] reason=elimination ticks=210
```

`placement` is winner → loser by seat index. Curve needs 4–8 players;
poker and blast go 2+.

## Write your own bot

Save this as `my_bot.py`:

```python
from vibewarz import Bot

class MyCurveBot(Bot):
    game = "curve"

    def act(self, state):
        # state is a dict — full schema in docs/PROTOCOL.md
        me = next(p for p in state["players"] if p["seat"] == self.seat)
        if not me["alive"]:
            return {"turn": "STRAIGHT"}
        # always turn right
        return {"turn": "RIGHT"}
```

Pit it against `wall_avoid`:

```bash
vibewarz play-local --game curve \
  --bot my_bot.py \
  --bot sample-bots/curve_wall_avoid.py \
  --bot sample-bots/curve_wall_avoid.py \
  --bot sample-bots/curve_wall_avoid.py
```

## act() return values

- A dict: `{"turn": "LEFT"}` — your action this tick
- A tuple `(action, reasoning)`: same, plus a free-form string shown in replays
- Anything else, or an illegal action: the engine substitutes `default_action(state, seat)` (for Curve, `{"turn": "STRAIGHT"}`). Substitution does NOT eliminate you; only illegal moves on the live server do (locally we substitute and warn with `--verbose`).

## State shape per game

The full wire format lives in [PROTOCOL.md](PROTOCOL.md). For local play the `state` your bot receives is the same dict the server's `Game.view_for(state, seat)` returns. For poker it's redacted (you see only your hole cards); for Curve and Blast it's the full public state.

## Submit to the live arena

When your bot beats the samples locally, take it online:

1. Sign in at https://vibewarz.com (Google).
2. Open https://vibewarz.com/account, click **Create bot**, copy the key (it's only shown once — keys start with `vw_live_`).
3. Run against the live arena:

   ```bash
   export VIBEWARZ_API_KEY=vw_live_...

   # Play 50 ranked matches and print the placement summary
   vibewarz play my_bot.py --mode ranked --loop 50
   ```

The SDK targets `wss://api.vibewarz.com/ws` by default — no extra config needed. Set `VIBEWARZ_API_URL` only if you're pointing at a local or staging server.

ELO changes appear on your profile at https://vibewarz.com/u/&lt;your-handle&gt;.

## Next

- [PROTOCOL.md](PROTOCOL.md) — every message shape on the wire
- [WRITING_A_GAME.md](WRITING_A_GAME.md) — add a new game to vibewarz
- [vibewarz.com/leaderboards](https://vibewarz.com/leaderboards) — what to beat
