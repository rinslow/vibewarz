"""Typed SDK models for Vibelords bots."""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal

from pydantic import Field

from ..bot import ActionResult, Bot
from .base import ActionModel, StateModel

VibelordsUnitType = Literal["pike", "cavalry", "archer"]
VibelordsFxKind = Literal["hit", "arrow", "death", "airstrike"]


class VibelordsBuildAction(ActionModel):
    type: Literal["build"] = "build"
    unit: VibelordsUnitType


class VibelordsAdvanceAgeAction(ActionModel):
    type: Literal["advance_age"] = "advance_age"


class VibelordsSpecialAction(ActionModel):
    type: Literal["special"] = "special"


class VibelordsNoopAction(ActionModel):
    type: Literal["noop"] = "noop"


VibelordsAction = Annotated[
    VibelordsBuildAction
    | VibelordsAdvanceAgeAction
    | VibelordsSpecialAction
    | VibelordsNoopAction,
    Field(discriminator="type"),
]


class VibelordsLane(StateModel):
    length: float


class VibelordsQueueItem(StateModel):
    unit: VibelordsUnitType
    age: int
    ready_tick: int


class VibelordsPlayer(StateModel):
    seat: int
    color: str
    gold: float
    xp: int
    age: int
    special_cd: int
    dmg_dealt: float
    queue: list[VibelordsQueueItem] = Field(default_factory=list)


class VibelordsBase(StateModel):
    seat: int
    x: float
    hp: float
    max_hp: float


class VibelordsUnit(StateModel):
    id: str
    owner: int
    unit: VibelordsUnitType
    age: int
    x: float
    hp: float
    max_hp: float
    atk_cd: int


class VibelordsFx(StateModel):
    kind: VibelordsFxKind
    owner: int
    age: int | None = None
    unit: VibelordsUnitType | None = None
    x: float | None = None
    x0: float | None = None
    x1: float | None = None
    crit: bool | None = None


class VibelordsState(StateModel):
    tick: int
    max_ticks: int
    lane: VibelordsLane
    bases: list[VibelordsBase]
    players: list[VibelordsPlayer]
    units: list[VibelordsUnit] = Field(default_factory=list)
    fx: list[VibelordsFx] = Field(default_factory=list)
    next_unit_id: int | None = None
    placement: list[int] = Field(default_factory=list)

    def player(self, seat: int) -> VibelordsPlayer:
        for player in self.players:
            if player.seat == seat:
                return player
        raise KeyError(f"seat {seat} not found")

    def base(self, seat: int) -> VibelordsBase:
        for base in self.bases:
            if base.seat == seat:
                return base
        raise KeyError(f"seat {seat} not found")


class VibelordsBot(Bot):
    """Base class for typed Vibelords bots."""

    game = "vibelords"
    state_model: ClassVar[type[VibelordsState]] = VibelordsState

    def on_start(self, initial_state: VibelordsState) -> None:
        """Called once at game_start."""

    def act(self, state: VibelordsState) -> ActionResult:
        raise NotImplementedError


__all__ = [
    "VibelordsAction",
    "VibelordsAdvanceAgeAction",
    "VibelordsBase",
    "VibelordsBot",
    "VibelordsBuildAction",
    "VibelordsFx",
    "VibelordsFxKind",
    "VibelordsLane",
    "VibelordsNoopAction",
    "VibelordsPlayer",
    "VibelordsQueueItem",
    "VibelordsSpecialAction",
    "VibelordsState",
    "VibelordsUnit",
    "VibelordsUnitType",
]
