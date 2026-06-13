# Vibelords

Two lords, one lane, four ages. March your army, out-read your
opponent, and raze their keep before they raze yours. *A call to
vibes.*

Vibelords is a heads-up lane RTS with **hidden, simultaneous
commitment**. Each tick both bots spend in secret, units counter each
other rock-paper-scissors, and what you're building stays off the lane
until it deploys — so there is no fixed optimal build order. You're
reacting to a concealed opponent, which makes it unsolvable in the same
way poker is.

- **Players:** 2 (heads-up only)
- **Tick budget:** 100 ms — miss it and the engine substitutes
  `{"type": "noop"}`
- **Cadence:** `tick_interval_ms = 100` → 10 ticks/second
- **Lane:** 1D, length `1000.0`. Your base sits at `x = 0` (seat 0) or
  `x = 1000` (seat 1); units march toward the enemy end.
- **Match length:** capped at `max_ticks = 3600` (~6 min). Raze the
  enemy base to win sooner. (Read the cap from `state["max_ticks"]`
  rather than hardcoding it.)

## The counter cycle

```
pike  >  cavalry  >  archer  >  pike
```

A unit deals **2.2×** damage to the class it counters. The cycle is
reinforced by mechanics, not just a multiplier:

- **Pike** — tanky, short range, slow. An anti-charge wall; shreds cavalry.
- **Cavalry** — medium HP, **fast** (closes on archers before they kite).
- **Archer** — fragile, **long range** (~5× melee reach); guns down pikes
  before they connect.

A higher-age unit also beats the lower-age version of the same class.

## The four ages

You start in the **Stone** age and spend XP to advance. Positioning
stats (range / speed / attack cooldown / build time) are constant across
ages — only HP, attack, and cost escalate, so matchup *timing* is
identical at every tier while raw power climbs.

| Age | Name | XP to enter | Pike · Cavalry · Archer |
|---|---|---|---|
| 0 | Stone | — (start) | Clubman · Wolf Rider · Slinger |
| 1 | Castle | 120 | Pikeman · Knight · Longbowman |
| 2 | Industrial | 320 | Trench Guard · Dragoon · Rifleman |
| 3 | Future | 700 | Juggernaut · Hover Striker · Railgunner |

Per-age scaling: HP & attack ×`1.55^age`, gold cost & kill-gold
×`1.6^age`. Rising age-up cost makes teching a real tempo sacrifice.

## Resources

| Resource | Earns | Spends on |
|---|---|---|
| **Gold** | +2/tick passive, plus `kill_gold` for each enemy unit you kill | building units, (airstrike is free) |
| **XP** | +1/tick passive, plus `kill_xp` per enemy kill | advancing ages |

You start with **50 gold** (enough for one Stone unit immediately) and
**0 XP**. Killing an enemy unit pays *you* its bounty.

## Unit roster (age-0 base stats)

`range`/`speed`/`atk_cd`/`build_ticks` are constant across ages; `hp`,
`atk`, `gold_cost`, and the kill rewards scale up per age (see above).

| Class | HP | Atk | Range | Speed | Atk CD | Gold | Build | Kill→gold/xp |
|---|---|---|---|---|---|---|---|---|
| pike | 140 | 18 | 16 | 7 | 6 | 40 | 8 | 22 / 14 |
| cavalry | 100 | 20 | 16 | 15 | 6 | 55 | 9 | 30 / 16 |
| archer | 70 | 22 | 85 | 9 | 6 | 50 | 10 | 28 / 16 |

## Actions

Use `VibelordsBot` with a `VibelordsState` callback. `act(state)`
returns **one** command per tick:

```python
from vibewarz import (
    VibelordsAdvanceAgeAction,
    VibelordsBuildAction,
    VibelordsNoopAction,
    VibelordsSpecialAction,
)

VibelordsBuildAction(unit="pike")  # queue a current-age unit
VibelordsAdvanceAgeAction()        # if xp >= cost and age < 3
VibelordsSpecialAction()           # airstrike, if off cooldown
VibelordsNoopAction()              # bank resources
```

Plain dicts like `{"type": "build", "unit": "pike"}` are still accepted.

- **build** deducts the unit's gold cost and appends it to your **hidden
  build queue** with `ready_tick = tick + build_ticks`. It deploys from
  your base edge when that tick arrives, then auto-marches. An
  unaffordable build is treated as a legal no-op (it won't error).
- **advance_age** deducts the XP cost and bumps your age.
- **special** — see *Airstrike* below.
- `legal_actions(state, seat)` returns only the currently affordable /
  available subset (plus `noop`); `default_action` is `noop`.

## Hidden information

Your `VibelordsState` is already redacted for your seat:

- your **own** `queue` is visible; the **opponent's `queue` is redacted
  to `[]`**.
- the RNG `seed` is dropped (there's no randomness anyway — `step` is
  fully deterministic — but the seat never sees it).

Everything else is **public**: gold, XP, age, every unit on the lane
(position + HP), and both base HPs. The read is *"what are they
deploying before it appears?"*

## Airstrike (the special)

`{"type": "special"}` fires a **defensive** airstrike: it damages every
**enemy unit in your own half** of the lane (seat 0: `x ≤ 500`).

- Damage: `90 + 40 × your_age`.
- Cooldown: `250` ticks (~25 s); `special_cd` counts down to 0 = ready.
- It's free (no gold). Use it to break a stack that's pushing your keep.

## Win conditions

- Drop the enemy base to **0 HP** → you win (`reason = "base_destroyed"`).
  Bases start at **1500 HP**; units chip the base once they break through.
- At `max_ticks` the match resolves on **base HP** (`reason =
  "timeout"`). Ties break by total **damage dealt**, then by seat.

## State shape

`state` is a `VibelordsState` pydantic model with attribute access
(`state.units`, `state.player(self.seat)`, `state.base(self.seat)`).
Legacy `Bot` subclasses still receive the same data as a plain dict.

| Key | Meaning |
|---|---|
| `tick`, `max_ticks` | current tick / the match cap (3600) |
| `lane` | `{"length": 1000.0}` |
| `bases` | `[{seat, x, hp, max_hp}]` — one per player |
| `players` | `[{seat, color, gold, xp, age, special_cd, dmg_dealt, queue}]` — `queue` is yours only; the opponent's is `[]` |
| `units` | `[{id, owner, unit, age, x, hp, max_hp, atk_cd}]` — every unit on the lane (public) |
| `fx` | transient per-tick render events (`hit`/`arrow`/`death`/`airstrike`); ignore in bots |
| `placement` | finishing order as seats are eliminated |

Use `self.legal_actions(state)` to get the currently affordable /
available action dicts for your seat. If you need raw JSON for existing
helper code, use `state.model_dump(mode="json")`.

## Reference bots

- `sample-bots/vibelords_random.py` — uniform-random legal action (the
  leaderboard floor).
- `sample-bots/vibelords_counter.py` — reads the visible enemy units and
  builds the counter class; banks XP to tech when ahead, and uses the
  airstrike defensively. Demonstrates the intended read-and-react loop.
