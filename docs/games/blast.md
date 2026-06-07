# Blast

Bomberman-style grid combat. Drop bombs, blow up soft blocks for
powerups, out-position your opponents. Last bot standing wins. The
arena starts closing in at tick 300, so no camping.

- **Players:** 2–4
- **Tick budget:** 100 ms — miss it and the engine substitutes
  `{"move": "stay", "drop_bomb": false}`
- **Grid:** 13×11 cells, origin `(0, 0)` top-left, `+x` right, `+y` down
- **Match length:** capped at `max_ticks = 600`

## Actions

Use `BlastBot` with a `BlastState` callback. Each tick `act(state)`
returns one combined action — a direction (or stand still) plus an
optional bomb drop on your current tile:

```python
from vibewarz import BlastAction

BlastAction(move="up", drop_bomb=False)
BlastAction(move="stay", drop_bomb=True)
```

Plain dicts like `{"move": "up", "drop_bomb": False}` are still accepted.

Dropping a bomb leaves it on your current tile; you can step off it the
same tick. A bomb only actually drops when
`bombs_active < bombs_max` *and* there isn't already a bomb on your
tile.

## State shape

`state` is a `BlastState` pydantic model with attribute access
(`state.board`, `state.bombs`, `state.player(self.seat)`). Legacy `Bot`
subclasses still receive the same data as a plain dict.

| Key | Meaning |
|---|---|
| `tick`, `max_ticks` | current tick / 600 |
| `dims` | `{"w": 13, "h": 11}` |
| `board[y][x]` | `"empty"` \| `"hard"` \| `"soft"` (hard walls indestructible; soft blocks blow up) |
| `shrink_start_tick` | 300 — see *Sudden death* below |
| `shrink_step` | 8 — ticks between ring contractions |
| `bombs` | list of `{x, y, timer, owner, range}`. `timer` counts down; explodes at 0. A flame landing on a bomb sets its timer to 0 (chain detonation). |
| `flames` | list of `{x, y, timer}`. Stepping on a flame tile kills. |
| `powerups` | list of `{id, x, y, kind}` where `kind` ∈ `"bomb" \| "range" \| "speed"` |
| `placement` | death order, last-out first |

Per-seat in `state.players[i]`:

| Key | Meaning |
|---|---|
| `seat`, `x`, `y`, `alive`, `color` | identity + position |
| `bombs_max` | concurrent-bomb cap (max 8) |
| `bombs_active` | currently ticking bombs you own |
| `blast_range` | tiles per ray (max 10) |
| `move_cooldown` | ticks between successful moves (floor 1 = one tile per tick) |
| `move_cooldown_remaining` | wait this many ticks before your next move applies |
| `powerup_counts` | `{"bomb": n, "range": n, "speed": n}` you've absorbed |

## Bombs and flames

Bombs fuse for **20 ticks (~2.0 s)** then explode along the four cardinal
rays. Each ray:

- Travels `blast_range` tiles or until it hits a `hard` wall.
- Stops *after* destroying one `soft` block.
- Triggers any bomb it touches → instant chain detonation.

Flames linger for **5 ticks**. Step on a flame tile any of those ticks
and you're out — and you drop one of your held powerups on the tile as
you go.

## Powerups

Each destroyed soft block has a **30%** chance to drop a powerup. Walk
over one to absorb it:

| Kind | Effect |
|---|---|
| `bomb` | `+1 bombs_max` (cap 8) |
| `range` | `+1 blast_range` (cap 10) |
| `speed` | `−1 move_cooldown` (floor 1 — one tile per tick) |

## Sudden death

Starting on `shrink_start_tick = 300`, a ring of indestructible walls
contracts inward every `shrink_step = 8` ticks. Anything caught on the
new ring — players, bombs, powerups — is crushed.

## Default action / illegal action

- Missing the 100 ms deadline → `{"move": "stay", "drop_bomb": false}`.
- Returning an illegal action on the live server eliminates you;
  locally we substitute-and-warn.
- A `drop_bomb: true` you can't act on — you're at `bombs_max`, or a bomb
  already sits on your tile — is **not** illegal. It's a harmless no-op, so
  mashing the bomb key never eliminates you.
- That no-op gets no explicit feedback: it isn't an `error`, and it isn't a
  `null`-substituted action in `tick_result`. Infer it from the next state
  (no new bomb on your tile, `bombs_active` unchanged), just like a move
  blocked by a wall.

Use `self.legal_actions(state)` to get the currently useful action dicts
for your seat. If you need raw JSON for existing helper code, use
`state.model_dump(mode="json")`.

## Tips for a first bot

1. Encode the board as a 2-D grid and BFS for safe tiles (no
   incoming-flame projection).
2. Bombs project their range *now* — track each bomb's footprint and
   treat the union of those tiles as walls 1–20 ticks ahead.
3. Don't forget chains — your "safe" route can light up if the bomb
   next to it ignites first.
