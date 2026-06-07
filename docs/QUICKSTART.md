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

`placement` is winner → loser by seat index. Curve needs exactly 4
players; poker and blast go 2+; Vibelords is heads-up.

## Write your own bot

Save this as `my_bot.py`:

```python
from vibewarz import CurveAction, CurveBot, CurveState

class MyCurveBot(CurveBot):
    def act(self, state: CurveState):
        me = state.player(self.seat)
        if not me.alive:
            return CurveAction(turn="STRAIGHT")

        # always turn right
        return CurveAction(turn="RIGHT")
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

- A pydantic action model: `CurveAction(turn="LEFT")`
- A dict: `{"turn": "LEFT"}` — still supported for compatibility
- A tuple `(action, reasoning)`: same action, plus a free-form string shown in replays
- Anything else, or an illegal action: the engine substitutes `default_action(state, seat)` (for Curve, `{"turn": "STRAIGHT"}`). Substitution does NOT eliminate you; only illegal moves on the live server do (locally we substitute and warn with `--verbose`).

## State shape per game

Each game has its own typed pydantic state model and action format. Full
reference per game:

- [Curve](games/curve.md) — turn LEFT/STRAIGHT/RIGHT, avoid walls and trails
- [Blast](games/blast.md) — grid movement + bomb drops, dodge flames
- [Poker](games/poker.md) — fold/check/call/bet/raise with hidden hole cards
- [Vibelords](games/vibelords.md) — hidden queue lane RTS

For typed bots, `state` is a pydantic model such as `CurveState` with
attribute access (`state.players`, `state.player(self.seat)`). For legacy
`Bot` subclasses, `state` remains the raw dict. Hidden-information games
are redacted before your bot sees them: Poker shows only your hole cards,
and Vibelords hides the opponent build queue. The wire-format envelope
around the JSON state lives in [PROTOCOL.md](PROTOCOL.md).

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

- [games/curve.md](games/curve.md), [games/blast.md](games/blast.md), [games/poker.md](games/poker.md), [games/vibelords.md](games/vibelords.md) — per-game reference
- [WRITING_A_BOT.md](WRITING_A_BOT.md) — typed bot lifecycle and API
- [PROTOCOL.md](PROTOCOL.md) — every message shape on the wire
- [WRITING_A_GAME.md](WRITING_A_GAME.md) — add a new game to vibewarz
- [vibewarz.com/leaderboards](https://vibewarz.com/leaderboards) — what to beat
