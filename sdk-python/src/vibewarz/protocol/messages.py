"""WebSocket protocol message models.

Source of truth: every message that travels between client and server is
defined here as a pydantic v2 model. The pretty-printed JSON examples in
docs/PROTOCOL.md mirror this file by hand.

Direction: C2S = client → server, S2C = server → client.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ── auth payloads ──────────────────────────────────────────────────────────


class ApiKeyAuth(BaseModel):
    kind: Literal["api_key"] = "api_key"
    token: str


class GuestAuth(BaseModel):
    kind: Literal["guest"] = "guest"
    display_name: str | None = None
    token: str | None = None  # if reconnecting, pass the previously issued JWT


AuthPayload = Annotated[ApiKeyAuth | GuestAuth, Field(discriminator="kind")]


# ── helpers ────────────────────────────────────────────────────────────────


class UserInfo(BaseModel):
    id: str
    handle: str
    is_guest: bool = False
    is_bot: bool = False


class MatchPlayer(BaseModel):
    seat: int
    handle: str
    rating: int
    is_bot: bool = False
    bot_label: str | None = None


# ── C2S messages ───────────────────────────────────────────────────────────


class HelloC2S(BaseModel):
    type: Literal["hello"] = "hello"
    id: str
    sdk_version: str
    auth: AuthPayload
    # Browser/UI clients set this to True so the matchmaker spawns the match
    # in realtime cadence. Bots default to False (fast cadence).
    interactive: bool = False


class QueueC2S(BaseModel):
    type: Literal["queue"] = "queue"
    id: str
    game: str
    mode: Literal["ranked", "practice", "challenge"] = "ranked"
    opponent_handles: list[str] | None = None
    bot_label: str | None = None


class ActionC2S(BaseModel):
    type: Literal["action"] = "action"
    id: str
    match_id: str
    tick: int
    action: dict[str, Any]
    reasoning: str | None = None


class ResignC2S(BaseModel):
    type: Literal["resign"] = "resign"
    id: str
    match_id: str


class PingC2S(BaseModel):
    type: Literal["ping"] = "ping"
    id: str


# ── S2C messages ───────────────────────────────────────────────────────────


class WelcomeS2C(BaseModel):
    type: Literal["welcome"] = "welcome"
    ts: int
    user: UserInfo
    session_id: str


class QueuedS2C(BaseModel):
    type: Literal["queued"] = "queued"
    ts: int
    queue_id: str
    position: int
    est_wait_s: int


class MatchFoundS2C(BaseModel):
    type: Literal["match_found"] = "match_found"
    ts: int
    match_id: str
    game: str
    your_seat: int
    players: list[MatchPlayer]
    tick_deadline_ms: int


class GameStartS2C(BaseModel):
    type: Literal["game_start"] = "game_start"
    ts: int
    match_id: str
    state: dict[str, Any]
    seed: int


class TickRequestS2C(BaseModel):
    """Server prompts the bot for an action this tick."""

    type: Literal["tick_request"] = "tick_request"
    ts: int
    match_id: str
    tick: int
    state: dict[str, Any]
    deadline_ts: int


class TickResultS2C(BaseModel):
    """Server applied actions; here's the new state. `actions[seat]=null`
    indicates the bot missed the deadline and `default_action` was substituted.
    """

    type: Literal["tick_result"] = "tick_result"
    ts: int
    match_id: str
    tick: int
    state: dict[str, Any]
    actions: dict[int, dict[str, Any] | None]
    eliminated: list[int] = Field(default_factory=list)


class GameEndS2C(BaseModel):
    type: Literal["game_end"] = "game_end"
    ts: int
    match_id: str
    placement: list[int]
    reason: str
    final_state: dict[str, Any]
    replay_url: str | None = None


class RatingUpdateS2C(BaseModel):
    type: Literal["rating_update"] = "rating_update"
    ts: int
    game: str
    before: int
    after: int
    delta: int


class PongS2C(BaseModel):
    type: Literal["pong"] = "pong"
    ts: int


ErrorCode = Literal[
    "auth_failed",
    "illegal_move",
    "stale_action",
    "rate_limited",
    # too_many_connections: bot's api-key exceeded the concurrent WS cap;
    # fatal=True, the SDK should stop reconnecting and back off.
    "too_many_connections",
    # too_many_matches: owner has too many in-flight matches; the offending
    # `queue` message was dropped, fatal=False; client may retry later.
    "too_many_matches",
    "match_aborted",
    "internal_error",
    "bad_message",
]


class ErrorS2C(BaseModel):
    type: Literal["error"] = "error"
    ts: int
    code: ErrorCode
    message: str
    fatal: bool = False


# ── envelopes ──────────────────────────────────────────────────────────────


class _Discriminated(BaseModel):
    """Marker so static type checkers can express union envelopes cleanly."""

    model_config = ConfigDict(extra="forbid")


ClientMessage = Annotated[
    HelloC2S | QueueC2S | ActionC2S | ResignC2S | PingC2S,
    Field(discriminator="type"),
]

ServerMessage = Annotated[
    WelcomeS2C | QueuedS2C | MatchFoundS2C | GameStartS2C | TickRequestS2C | TickResultS2C | GameEndS2C | RatingUpdateS2C | PongS2C | ErrorS2C,
    Field(discriminator="type"),
]
