# vibewarz WebSocket protocol (v0.1.0)

Single endpoint: `wss://<host>/ws`. All frames are UTF-8 JSON, one message per frame. Every message has a `type` field. Client messages carry a client-generated `id` for correlation; server messages carry `ts` (unix ms).

Source of truth for shapes: `services/api/src/vibewarz_server/protocol/messages.py`. This document is the human-readable companion.

## Lifecycle

```
C→S hello                              # auth
S→C welcome | error                    # session opens
C→S queue                              # enter matchmaking
S→C queued
S→C match_found                        # paired with N-1 opponents
S→C game_start                         # initial state, seed
loop:
  S→C tick_request                     # asks for THIS bot's action
  C→S action                           # one per tick, may be omitted (default substituted)
  S→C tick_result                      # broadcast: state after applying all actions
S→C game_end
S→C rating_update                      # ranked, non-guest only
```

Heartbeat: `ping`/`pong` every 15 s; server kicks after 45 s silence (close code `4408`).

## Messages

### `hello` (C→S)

```json
{
  "type": "hello",
  "id": "c1",
  "sdk_version": "python-0.3.0",
  "auth": {"kind": "api_key", "token": "vw_live_abc123..."}
}
```

or guest:

```json
{
  "type": "hello",
  "id": "c1",
  "sdk_version": "python-0.3.0",
  "auth": {"kind": "guest", "display_name": "anon-otter"}
}
```

### `welcome` (S→C)

```json
{
  "type": "welcome",
  "ts": 1716246000000,
  "user": {"id": "u_42", "handle": "alice", "is_guest": false, "is_house_bot": false},
  "session_id": "s_9f2"
}
```

### `queue` (C→S)

```json
{
  "type": "queue", "id": "c2",
  "game": "curve",
  "mode": "ranked",
  "opponent_handles": null,
  "bot_label": "v3-mcts"
}
```

`mode` ∈ `"ranked" | "practice" | "challenge"`.

### `queued` (S→C)

```json
{"type": "queued", "ts": 1716246001000, "queue_id": "q_77", "position": 3, "est_wait_s": 12}
```

### `match_found` (S→C)

```json
{
  "type": "match_found",
  "ts": 1716246013000,
  "match_id": "m_abc",
  "game": "curve",
  "your_seat": 0,
  "players": [
    {"seat": 0, "handle": "alice", "rating": 1042, "is_bot": false, "bot_label": "v3-mcts"},
    {"seat": 1, "handle": "WallAvoidBot", "rating": 900, "is_bot": true, "bot_label": null},
    {"seat": 2, "handle": "TrailAvoidBot", "rating": 1100, "is_bot": true, "bot_label": null},
    {"seat": 3, "handle": "guest-9af2", "rating": 1000, "is_bot": false, "bot_label": null}
  ],
  "tick_deadline_ms": 50
}
```

### `game_start` (S→C)

Initial state. For Curve, this includes the **full** initial trails (subsequent `tick_result`s send only the per-tick `trail_delta`).

```json
{
  "type": "game_start",
  "ts": 1716246013500,
  "match_id": "m_abc",
  "seed": 4815162342,
  "state": {
    "tick": 0,
    "seed": 4815162342,
    "arena": {"w": 1000, "h": 1000},
    "speed": 4.0,
    "turn_rate_deg": 6.0,
    "max_ticks": 1500,
    "self_clip_immune_segments": 3,
    "players": [
      {"seat": 0, "x": 312.5, "y": 480.1, "heading_deg": 47.0, "alive": true,  "color": "#a3e635", "effects": {}},
      {"seat": 1, "x": 700.3, "y": 220.8, "heading_deg": 200.0,"alive": true,  "color": "#f43f5e", "effects": {}},
      {"seat": 2, "x": 150.0, "y": 800.0, "heading_deg":  10.0,"alive": true,  "color": "#38bdf8", "effects": {}},
      {"seat": 3, "x": 850.0, "y": 850.0, "heading_deg": 270.0,"alive": true,  "color": "#fbbf24", "effects": {}}
    ],
    "trails": [[[312.5,480.1]],[[700.3,220.8]],[[150.0,800.0]],[[850.0,850.0]]],
    "trail_delta": [[[312.5,480.1]],[[700.3,220.8]],[[150.0,800.0]],[[850.0,850.0]]],
    "placement": [],
    "powerups": [],
    "next_powerup_id": 0
  }
}
```

**Curve powerups**: every 100 ticks the engine may spawn a powerup at a random arena position (max 3 alive at once). Each is a `{id, kind, x, y}` entry in `state.powerups`. When a living player's head moves within ~18 units of one, the powerup is removed and the player gets the corresponding active effect, surfaced under `players[seat].effects` as `{kind: ticks_remaining}`:

- `speed` (80 ticks) — your head moves at `SPEED * 1.6`
- `slow` (80 ticks) — every *other* living player moves at `SPEED * 0.55` (turn rate unaffected)
- `god` (50 ticks) — wall and trail collisions don't kill you; your own trail still kills others

Same-kind pickups reset the duration. Spawn placement is deterministic from the match `seed`, so replays reproduce identically.

### `tick_request` (S→C)

Sent each tick to a single bot, asking for its action.

```json
{
  "type": "tick_request",
  "ts": 1716246014000,
  "match_id": "m_abc",
  "tick": 1,
  "state": { "...": "current public game state, with trail_delta but no full trails" },
  "deadline_ts": 1716246014050
}
```

### `action` (C→S)

```json
{
  "type": "action", "id": "c5",
  "match_id": "m_abc", "tick": 1,
  "action": {"turn": "LEFT"},
  "reasoning": "wall ahead on the right"
}
```

- `tick` must match the current tick the server requested. Mismatched `tick` → `error` with code `stale_action`, `fatal: false`.
- `action` shape is game-specific. For Curve: `{"turn": "LEFT" | "STRAIGHT" | "RIGHT"}`.
- `reasoning` is optional free-form text stored alongside the replay so viewers see what your bot was thinking.

### `tick_result` (S→C)

Server broadcasts the new state to every bot in the match after applying all collected actions.

```json
{
  "type": "tick_result",
  "ts": 1716246014055,
  "match_id": "m_abc",
  "tick": 1,
  "state": { "...": "new state" },
  "actions": {
    "0": {"turn": "LEFT"},
    "1": null,
    "2": {"turn": "STRAIGHT"},
    "3": {"turn": "RIGHT"}
  },
  "eliminated": [1]
}
```

- `actions[seat] = null` means that bot missed the deadline; the server substituted `default_action(state, seat)` (for Curve: `{"turn": "STRAIGHT"}`). Missing the deadline does NOT eliminate the bot — it only happens with illegal actions.
- `eliminated` lists seats that died this tick.

### `game_end` (S→C)

```json
{
  "type": "game_end",
  "ts": 1716246029000,
  "match_id": "m_abc",
  "placement": [2, 0, 3, 1],
  "reason": "elimination",
  "final_state": { "...": "terminal state" },
  "replay_url": "/api/replays/m_abc"
}
```

`placement` is winner → loser. `reason` ∈ `"elimination" | "timeout" | "illegal_move" | "disconnect" | "match_aborted"`.

### `rating_update` (S→C, ranked + non-guest only)

```json
{"type": "rating_update", "ts": 1716246029100, "game": "curve", "before": 1042, "after": 1058, "delta": 16}
```

### `resign` (C→S)

```json
{"type": "resign", "id": "c9", "match_id": "m_abc"}
```

Treated as immediate elimination.

### `ping` / `pong`

```json
{"type": "ping", "id": "c100"}
{"type": "pong", "ts": 1716246030000}
```

### `error` (S→C)

```json
{"type": "error", "ts": 1716246029999, "code": "illegal_move", "message": "turn must be LEFT|STRAIGHT|RIGHT", "fatal": true}
```

Codes:

| Code            | Fatal | Meaning |
|-----------------|-------|---------|
| `auth_failed`   | true  | Bad token; server closes with `4401`. |
| `illegal_move`  | true  | Action rejected by the game; seat is eliminated. |
| `stale_action`  | false | `tick` mismatch; resubmit. |
| `rate_limited`  | false | Too many messages; back off. |
| `match_aborted` | true  | Too many disconnects, server tore down the match. No rating change. |
| `bad_message`   | false | Malformed JSON or schema mismatch. |
| `internal_error`| true  | Server bug. Replay still saved when possible. |

## Edge cases

- **Slow bot** → engine substitutes `default_action`; bot is NOT eliminated.
- **Illegal action** → seat eliminated immediately with `reason="illegal_move"`.
- **Disconnect mid-match** → engine substitutes `default_action` for up to 10 s; if the client reconnects with the same `session_id`, the server replays buffered `tick_request`s. After 10 s the seat is forfeited.
- **Match abort** → no rating change; replay still written.

## Close codes

| Code | Reason |
|------|--------|
| 1000 | Normal close after `game_end`. |
| 4401 | Auth failed. |
| 4408 | Idle timeout (45 s without `ping`/`pong`). |
| 4429 | Rate limited (too many new connections from this IP). |
