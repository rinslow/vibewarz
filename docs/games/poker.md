# Poker (No-Limit Hold'em)

Single-table tournament. 1000-chip starting stacks, escalating blinds.
Last stack standing wins; placement is the bust-out order (last-out
first).

- **Players:** 2–6
- **Decision budget:** 15 s — miss it and the engine substitutes a free
  `check`, or a `fold` if there's a bet you haven't matched
- **Variant:** No-Limit Texas Hold'em

## Actions

Use `PokerBot` with a `PokerState` callback. When it's your seat's turn
(`state.action_on == self.seat`), return one of:

```python
from vibewarz import (
    PokerBetAction,
    PokerCallAction,
    PokerCheckAction,
    PokerFoldAction,
    PokerRaiseAction,
)

PokerFoldAction()          # give up this hand
PokerCheckAction()         # only legal when no bet to call
PokerCallAction()          # match the current bet
PokerBetAction(amount=N)   # open with N (only when no current bet yet)
PokerRaiseAction(to=N)     # raise so your committed_round becomes N
```

Plain dicts like `{"type": "fold"}` are still accepted.

- `bet.amount` is the **size of the opening bet**.
- `raise.to` is the **total chips you have in for this round** after the
  raise — *not* the delta over the current bet.

## State shape

`state` is a `PokerState` pydantic model with attribute access
(`state.phase`, `state.community_cards`, `state.player(self.seat)`).
Legacy `Bot` subclasses still receive the same data as a plain dict.

| Key | Meaning |
|---|---|
| `phase` | `"preflop" \| "flop" \| "turn" \| "river" \| "showdown" \| "between_hands"` |
| `action_on` | seat that owes a decision (`None` when nothing to do) |
| `pot` | chips already committed and moved to the pot (does **not** include the current round's in-flight chips) |
| `side_pots` | list of `{amount, eligible_seats}` after an all-in |
| `community_cards` | the board: 0–5 cards depending on phase |
| `current_bet` | highest `committed_round` at the table this round. To call, you owe `current_bet − your.committed_round`. |
| `min_raise` | smallest legal *increment* over `current_bet` for a raise |
| `last_aggressor` | seat that opened/raised last |
| `small_blind`, `big_blind` | current blind amounts |
| `blind_schedule`, `level_idx`, `hands_at_level` | tournament blind clock |
| `button` | dealer-button seat (always last to act post-flop) |
| `hand_number` | 1-indexed hand counter |
| `history` | every action so far as `{hand, phase, seat, action}` |
| `showdown_hands` | at showdown only: `{seat: hand_string}`. Otherwise `None`. |
| `pot_distribution` | filled when a hand resolves: list of `{seat, amount}` payouts |
| `placement` | tournament bust-out order, last-out first |

Per-seat in `state.players[i]`:

| Key | Meaning |
|---|---|
| `stack` | chips behind |
| `committed_round` | chips put in this betting round (your "to call" reads this) |
| `committed_hand` | chips put in this whole hand |
| `in_tournament`, `in_hand`, `folded`, `all_in` | seat status flags |
| `hole_cards` | your own at any time; others' only at showdown (otherwise `[]`) |
| `last_action` | most recent action this hand or `None` |

## Hidden information

Each seat sees its own hole cards in
`state.player(self.seat).hole_cards`. Other players' hole cards arrive
as an empty list until showdown reveal — the server is authoritative and
is the only thing that ever sees every seat's cards mid-hand.

The same applies to the replay viewer: a replay re-renders the engine's
unredacted journal, but the UI can toggle a "view as seat X" mode that
client-side hides other seats' cards.

## Timing / defaults

- Miss the 15 s decision window → engine substitutes a free `check`, or
  `fold` if there's a bet you haven't matched.
- Bots never auto-bet from a timeout — only check or fold.
- Returning an illegal action on the live server eliminates you;
  locally we substitute-and-warn.

## Tips for a first bot

1. Start tight: fold weak hands preflop, only call/raise with strong
   ones. Use `state.to_call(self.seat)` to size up cost.
2. Track `state.min_raise` — raising under it is illegal and gets you booted.
3. Use `state.history` to model opponents over multiple hands. Bust-out order
   is what matters; survival is more important than max EV on a single
   hand.

Use `self.legal_actions(state)` to get the current legal action dicts
for your seat. If you need raw JSON for existing helper code, use
`state.model_dump(mode="json")`.
