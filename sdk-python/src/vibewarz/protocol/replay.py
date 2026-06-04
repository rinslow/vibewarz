"""Replay envelope and event models.

The vibewarz server journals each match as an ordered list of events
(`game_start`, `tick_result`, `game_end`) and persists them under the
`/api/replays/{match_id}` endpoint. The shape returned by that endpoint is
the `ReplayEnvelope` defined here.

Single source of truth for both sides:
  - the server's ReplayStore writes/serves objects shaped like this;
  - the SDK `Client.fetch_replay` parses responses into this type.

Hidden-information games (poker) journal the *unredacted* state — the
spectator/owner consuming the envelope can re-apply per-seat redaction
client-side if they want a POV view.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class GameStartEvt(BaseModel):
    type: Literal["game_start"] = "game_start"
    seed: int
    state: dict[str, Any]
    match_id: str
    # Optional only for back-compat with replays written before envelope
    # tagging shipped. New replays always carry this; viewers should prefer
    # ReplayEnvelope.game_id and use this as a fallback.
    game_id: str | None = None
    # Optional display names keyed by seat (e.g. {0: "Anthropic", 1: "OpenAI"}).
    # Absent on replays written before naming shipped; viewers fall back to
    # seat labels.
    names: dict[int, str] | None = None


class TickResultEvt(BaseModel):
    type: Literal["tick_result"] = "tick_result"
    ts: int
    match_id: str
    tick: int
    state: dict[str, Any]
    actions: dict[int, dict[str, Any] | None]
    eliminated: list[int] = Field(default_factory=list)


class GameEndEvt(BaseModel):
    type: Literal["game_end"] = "game_end"
    ts: int
    match_id: str
    placement: list[int]
    reason: str
    final_state: dict[str, Any]
    replay_url: str | None = None


ReplayEvent = Annotated[
    GameStartEvt | TickResultEvt | GameEndEvt,
    Field(discriminator="type"),
]


class ReplayEnvelope(BaseModel):
    """Top-level shape returned by GET /api/replays/{match_id}.

    `game_id` is the canonical game tag (e.g. "curve" / "blast" / "poker").
    Pre-tagging replays were written without it — consumers should fall back
    to GameStartEvt.game_id or to state-shape inference.
    """

    match_id: str
    game_id: str | None = None
    events: list[ReplayEvent]
