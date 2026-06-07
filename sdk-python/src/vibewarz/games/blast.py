"""Typed SDK models for Blast bots."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import Field

from ..bot import ActionResult, Bot
from .base import ActionModel, StateModel

BlastCell = Literal["empty", "hard", "soft"]
BlastMove = Literal["up", "down", "left", "right", "stay"]
BlastPowerupKind = Literal["bomb", "range", "speed"]


class BlastDims(StateModel):
    w: int
    h: int


class BlastPlayer(StateModel):
    seat: int
    x: int
    y: int
    alive: bool
    color: str
    bombs_max: int
    bombs_active: int
    blast_range: int
    move_cooldown: int
    move_cooldown_remaining: int
    powerup_counts: dict[BlastPowerupKind, int] = Field(default_factory=dict)


class BlastBomb(StateModel):
    x: int
    y: int
    timer: int
    owner: int
    range: int


class BlastFlame(StateModel):
    x: int
    y: int
    timer: int


class BlastPowerup(StateModel):
    id: str
    x: int
    y: int
    kind: BlastPowerupKind


class BlastState(StateModel):
    tick: int
    dims: BlastDims
    board: list[list[BlastCell]]
    max_ticks: int
    shrink_start_tick: int
    shrink_step: int
    players: list[BlastPlayer]
    bombs: list[BlastBomb] = Field(default_factory=list)
    flames: list[BlastFlame] = Field(default_factory=list)
    powerups: list[BlastPowerup] = Field(default_factory=list)
    next_powerup_id: int | None = None
    placement: list[int] = Field(default_factory=list)

    def player(self, seat: int) -> BlastPlayer:
        for player in self.players:
            if player.seat == seat:
                return player
        raise KeyError(f"seat {seat} not found")


class BlastAction(ActionModel):
    move: BlastMove
    drop_bomb: bool = False


class BlastBot(Bot):
    """Base class for typed Blast bots."""

    game = "blast"
    state_model: ClassVar[type[BlastState]] = BlastState

    def on_start(self, initial_state: BlastState) -> None:
        """Called once at game_start."""

    def act(self, state: BlastState) -> ActionResult:
        raise NotImplementedError


__all__ = [
    "BlastAction",
    "BlastBomb",
    "BlastBot",
    "BlastCell",
    "BlastDims",
    "BlastFlame",
    "BlastMove",
    "BlastPlayer",
    "BlastPowerup",
    "BlastPowerupKind",
    "BlastState",
]
