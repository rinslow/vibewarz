"""Typed SDK models for Curve bots."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import Field

from ..bot import ActionResult, Bot
from .base import ActionModel, StateModel

CurveTurn = Literal["LEFT", "STRAIGHT", "RIGHT"]
CurvePowerupKind = Literal["speed", "slow", "god"]
CurvePoint = tuple[float, float]


class CurveArena(StateModel):
    w: float
    h: float


class CurvePlayer(StateModel):
    seat: int
    x: float
    y: float
    heading_deg: float
    alive: bool
    color: str
    effects: dict[CurvePowerupKind, int] = Field(default_factory=dict)


class CurvePowerup(StateModel):
    id: str
    kind: CurvePowerupKind
    x: float
    y: float


class CurveState(StateModel):
    tick: int
    arena: CurveArena
    speed: float
    turn_rate_deg: float
    max_ticks: int
    self_clip_immune_segments: int
    players: list[CurvePlayer]
    trails: list[list[CurvePoint]] = Field(default_factory=list)
    trail_delta: list[list[CurvePoint]] = Field(default_factory=list)
    placement: list[int] = Field(default_factory=list)
    powerups: list[CurvePowerup] = Field(default_factory=list)
    next_powerup_id: int | None = None

    def player(self, seat: int) -> CurvePlayer:
        for player in self.players:
            if player.seat == seat:
                return player
        raise KeyError(f"seat {seat} not found")


class CurveAction(ActionModel):
    turn: CurveTurn


class CurveBot(Bot):
    """Base class for typed Curve bots."""

    game = "curve"
    state_model: ClassVar[type[CurveState]] = CurveState

    def on_start(self, initial_state: CurveState) -> None:
        """Called once at game_start."""

    def act(self, state: CurveState) -> ActionResult:
        raise NotImplementedError


__all__ = [
    "CurveAction",
    "CurveArena",
    "CurveBot",
    "CurvePlayer",
    "CurvePoint",
    "CurvePowerup",
    "CurvePowerupKind",
    "CurveState",
    "CurveTurn",
]
