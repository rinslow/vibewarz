# Curve

Light-cycle / *Achtung die Kurve*. Each player drives a head at constant
speed. The head leaves a trail behind it. Crash into any trail or the
arena wall — including your own — and you're out. Last alive wins.

- **Players:** 4
- **Tick budget:** 50 ms — miss it and the engine substitutes
  `{"turn": "STRAIGHT"}`
- **Arena:** 1000×1000 px, origin `(0, 0)` top-left
- **Match length:** capped at `max_ticks = 1500`; if anyone's still alive
  the longer survivor wins.

## Actions

Use `CurveBot` with a `CurveState` callback. Each tick `act(state)` must
return one of:

```python
from vibewarz import CurveAction

CurveAction(turn="LEFT")      # rotate heading -6 degrees
CurveAction(turn="STRAIGHT")  # keep heading
CurveAction(turn="RIGHT")     # rotate heading +6 degrees
```

Plain dicts like `{"turn": "LEFT"}` are still accepted.

## State shape

`state` is a `CurveState` pydantic model with attribute access
(`state.tick`, `state.players`, `state.player(self.seat)`). Legacy
`Bot` subclasses still receive the same data as a plain dict.

| Key | Meaning |
|---|---|
| `tick` | current tick, 0-indexed |
| `max_ticks` | 1500 — ties resolved by survival time |
| `arena` | `{"w": 1000, "h": 1000}` |
| `speed` | 4.8 px/tick base (`×1.6` with active `speed`, `×0.55` while `slow` is on you) |
| `turn_rate_deg` | 6.0 |
| `self_clip_immune_segments` | 3 — your last N trail points don't kill you. Materially changes your minimum turning radius. |
| `players[i]` | `CurvePlayer(seat, x, y, heading_deg, alive, color, effects)` where `effects` is `{"speed"\|"slow"\|"god": ticks_remaining}` |
| `trails[i]` | full point list for seat i, oldest first |
| `trail_delta[i]` | points added this tick (use this in your hot path) |
| `powerups` | list of `{id, kind, x, y}` — they don't expire on the ground |
| `placement` | death order, last-out first |

## Powerups

The engine spawns a powerup at a random arena position roughly every
100 ticks, capped at 3 alive on the ground. Walk over one (within ~18
units of your head) to absorb it:

| Kind | Effect | Duration |
|---|---|---|
| `speed` | you move 1.6× faster | 80 ticks |
| `slow` | every other player moves 0.55× | 80 ticks |
| `god`  | walls and trails don't kill you (your trail still kills others) | 50 ticks |

Active effects show up under `state.player(seat).effects` as a
`{kind: ticks_remaining}` dict. If you need raw JSON for existing helper
code, use `state.model_dump(mode="json")`.

## Default action / illegal action

- Missing the 50 ms deadline → engine substitutes `{"turn": "STRAIGHT"}`.
  You stay alive; you just go straight that tick.
- Returning an illegal action (anything that isn't one of the three turns)
  on the live server eliminates you. Locally (`vibewarz play-local`) the
  engine substitutes-and-warns instead.

## Tips for a first bot

1. Start with a wall-avoid heuristic: project a few ticks ahead and pick
   the turn that keeps you in-bounds longest.
2. Then add trail-avoidance using `state.trail_delta` rather than the full
   `state.trails` list — scanning every point every tick wastes your budget.
3. Powerup awareness comes last — picking up `speed` near a tight
   corridor is usually a death sentence.
