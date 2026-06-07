# Sample bots

Reference bots that exercise the typed SDK + game APIs end-to-end. Fork
these to bootstrap your own.

| File | Game | Strategy |
|---|---|---|
| [`curve_wall_avoid.py`](curve_wall_avoid.py) | curve | Drives straight unless a wall is within ~80 units of the projected head, then turns toward arena center |
| [`blast_random.py`](blast_random.py) | blast | Uniform random over legal actions — a leaderboard floor |
| [`poker_random.py`](poker_random.py) | poker | Uniform random over legal actions (check/fold/call/min-raise) |
| [`vibelords_random.py`](vibelords_random.py) | vibelords | Uniform random over legal actions |
| [`vibelords_counter.py`](vibelords_counter.py) | vibelords | Builds counters to visible enemy units |

## Try them

```bash
pip install vibewarz vibewarz-games

# Two random poker bots head-to-head
vibewarz play-local --game poker \
  --bot sample-bots/poker_random.py \
  --bot sample-bots/poker_random.py

# Four-curve scrap, with verbose elimination log
vibewarz play-local --game curve --verbose \
  --bot sample-bots/curve_wall_avoid.py \
  --bot sample-bots/curve_wall_avoid.py \
  --bot sample-bots/curve_wall_avoid.py \
  --bot sample-bots/curve_wall_avoid.py
```

## Submit yours to the live arena

Once your bot beats these locally, sign in at [vibewarz.com](https://vibewarz.com), open [vibewarz.com/account](https://vibewarz.com/account) to create a bot + copy its key, and:

```bash
export VIBEWARZ_API_KEY=vw_live_...
vibewarz play my_bot.py --mode ranked --loop 50
```

## License

MIT — these are reference implementations, copy them freely.
