"""Typed SDK models for Rock Paper Scissors bots."""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal

from pydantic import ConfigDict, Field

from ..bot import ActionResult, Bot
from .base import ActionModel, StateModel

RockPaperScissorsColor = Literal[0, 1]
RockPaperScissorsPhase = Literal["setup", "play", "fight", "end"]
RockPaperScissorsPieceType = Literal[
    "unassigned",
    "rock",
    "paper",
    "scissors",
    "trap",
    "flag",
    "hidden",
]
RockPaperScissorsSetupPieceType = Literal["rock", "paper", "scissors", "trap", "flag"]
RockPaperScissorsFightCommit = Literal["rock", "paper", "scissors"]
RockPaperScissorsMoveType = Literal["movement", "capture"]


class RockPaperScissorsDims(StateModel):
    w: int
    h: int


class RockPaperScissorsPiece(StateModel):
    type: RockPaperScissorsPieceType
    color: RockPaperScissorsColor
    visible_to_enemy: bool = False


class RockPaperScissorsBoard(StateModel):
    squares: list[RockPaperScissorsPiece | None]

    def piece_at(self, square: int) -> RockPaperScissorsPiece | None:
        return self.squares[square]


class RockPaperScissorsPlayer(StateModel):
    seat: int
    color: RockPaperScissorsColor
    color_hex: str
    has_committed_setup: bool
    setup_valid: bool
    fight_commit: RockPaperScissorsFightCommit | None = None


class RockPaperScissorsState(StateModel):
    tick: int
    phase: RockPaperScissorsPhase
    dims: RockPaperScissorsDims
    board: RockPaperScissorsBoard
    current_turn: RockPaperScissorsColor
    players: list[RockPaperScissorsPlayer]
    winner: RockPaperScissorsColor | None = None
    fight_location: int | None = None
    fight_attacker: int | None = None
    placement: list[int] = Field(default_factory=list)

    def player(self, seat: int) -> RockPaperScissorsPlayer:
        for player in self.players:
            if player.seat == seat:
                return player
        raise KeyError(f"seat {seat} not found")

    def piece_at(self, square: int) -> RockPaperScissorsPiece | None:
        return self.board.piece_at(square)


class RockPaperScissorsSetupPiece(ActionModel):
    type: RockPaperScissorsSetupPieceType
    color: RockPaperScissorsColor


class RockPaperScissorsSetupAssignment(ActionModel):
    square: int
    piece: RockPaperScissorsSetupPiece


class RockPaperScissorsSetupAction(ActionModel):
    type: Literal["setup"] = "setup"
    assignments: list[RockPaperScissorsSetupAssignment]


class RockPaperScissorsMoveAction(ActionModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["move"] = "move"
    from_square: int = Field(alias="from")
    to: int
    move_type: RockPaperScissorsMoveType | None = None

    def model_dump(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs.setdefault("by_alias", True)
        return super().model_dump(*args, **kwargs)


class RockPaperScissorsFightAction(ActionModel):
    type: Literal["fight"] = "fight"
    piece: RockPaperScissorsFightCommit


class RockPaperScissorsPassAction(ActionModel):
    type: Literal["pass"] = "pass"


RockPaperScissorsAction = Annotated[
    RockPaperScissorsSetupAction
    | RockPaperScissorsMoveAction
    | RockPaperScissorsFightAction
    | RockPaperScissorsPassAction,
    Field(discriminator="type"),
]


class RockPaperScissorsBot(Bot):
    """Base class for typed Rock Paper Scissors bots."""

    game = "rock-paper-scissors"
    state_model: ClassVar[type[RockPaperScissorsState]] = RockPaperScissorsState

    def on_start(self, initial_state: RockPaperScissorsState) -> None:
        """Called once at game_start."""

    def act(self, state: RockPaperScissorsState) -> ActionResult:
        raise NotImplementedError


__all__ = [
    "RockPaperScissorsAction",
    "RockPaperScissorsBoard",
    "RockPaperScissorsBot",
    "RockPaperScissorsColor",
    "RockPaperScissorsDims",
    "RockPaperScissorsFightAction",
    "RockPaperScissorsFightCommit",
    "RockPaperScissorsMoveAction",
    "RockPaperScissorsMoveType",
    "RockPaperScissorsPassAction",
    "RockPaperScissorsPhase",
    "RockPaperScissorsPiece",
    "RockPaperScissorsPieceType",
    "RockPaperScissorsPlayer",
    "RockPaperScissorsSetupAction",
    "RockPaperScissorsSetupAssignment",
    "RockPaperScissorsSetupPiece",
    "RockPaperScissorsSetupPieceType",
    "RockPaperScissorsState",
]
