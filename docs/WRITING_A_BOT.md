# Writing a bot

The recommended SDK API is one typed base class per game:

```python
from vibewarz import CurveAction, CurveBot, CurveState

class MyBot(CurveBot):
    def on_start(self, initial_state: CurveState) -> None:
        self.start_tick = initial_state.tick

    def act(self, state: CurveState):
        me = state.player(self.seat)
        return CurveAction(turn="RIGHT" if me.alive else "STRAIGHT")

    def on_end(self, placement: list[int], reason: str) -> None:
        pass
```

## Lifecycle

- `seat`, `match_id`, and `players` are populated before the first callback.
- `on_start(initial_state)` runs once with the first bot-visible state.
- `act(state)` runs whenever your seat owes an action.
- `on_end(placement, reason)` runs once after the match ends.

Typed bots receive pydantic models in `on_start()` and `act()`. Legacy
subclasses of `Bot` still receive raw dicts.

## Games

Import the base class and state/action models for the game you are
playing:

```python
from vibewarz import BlastAction, BlastBot, BlastState
from vibewarz import PokerBot, PokerCallAction, PokerFoldAction, PokerState
from vibewarz import VibelordsBot, VibelordsBuildAction, VibelordsState
```

The same names are also available from `vibewarz.games`.

## Returning actions

You can return either a typed pydantic action model or a plain dict:

```python
return CurveAction(turn="LEFT")
return {"turn": "LEFT"}
```

To add replay-visible reasoning, return `(action, text)`:

```python
return CurveAction(turn="LEFT"), "wall ahead"
```

For games with larger action spaces, `self.legal_actions(state)` returns
the current legal action dicts for your game and seat. `self.default_action(state)`
returns the engine timeout fallback.

## Hidden information

State models describe what your bot can actually see, not the server's
omniscient replay state:

- Poker redacts the deck and other players' hole cards until showdown.
- Vibelords redacts the opponent's hidden build queue.
- Curve and Blast are public-information games, apart from the server-only RNG seed.

## Raw JSON

Use `state.model_dump(mode="json")` when you need the underlying JSON-like
dict, for example to pass state into custom helper code. Unknown future
server fields are allowed on state models, so older bots do not break when
the server adds non-breaking fields.

The wire envelope is still plain JSON; see [PROTOCOL.md](PROTOCOL.md) for
the WebSocket message shapes.
