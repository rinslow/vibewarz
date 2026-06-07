# vibewarz — Python SDK

```bash
pip install vibewarz
```

Write a bot:

```python
from vibewarz import CurveAction, CurveBot, CurveState, run

class MyBot(CurveBot):
    def act(self, state: CurveState):
        return CurveAction(turn="STRAIGHT")

run(MyBot(), mode="practice")
```

Use `CurveBot`, `BlastBot`, `PokerBot`, or `VibelordsBot` for typed
pydantic state objects. Returning plain dict actions still works.

Or use the CLI:

```bash
vibewarz login
vibewarz play my_bot.py --mode ranked --loop 50
```
