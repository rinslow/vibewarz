"""Typed SDK models for Poker bots."""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal

from pydantic import Field

from ..bot import ActionResult, Bot
from .base import ActionModel, StateModel

PokerPhase = Literal[
    "between_hands",
    "preflop",
    "flop",
    "turn",
    "river",
    "showdown",
    "hand_complete",
    "done",
]


class PokerFoldAction(ActionModel):
    type: Literal["fold"] = "fold"


class PokerCheckAction(ActionModel):
    type: Literal["check"] = "check"


class PokerCallAction(ActionModel):
    type: Literal["call"] = "call"


class PokerBetAction(ActionModel):
    type: Literal["bet"] = "bet"
    amount: int


class PokerRaiseAction(ActionModel):
    type: Literal["raise"] = "raise"
    to: int


PokerAction = Annotated[
    PokerFoldAction
    | PokerCheckAction
    | PokerCallAction
    | PokerBetAction
    | PokerRaiseAction,
    Field(discriminator="type"),
]


class PokerBlindLevel(StateModel):
    sb: int
    bb: int
    hands: int


class PokerSidePot(StateModel):
    amount: int
    eligible_seats: list[int]


class PokerPotDistribution(StateModel):
    seat: int
    amount: int


class PokerPlayer(StateModel):
    seat: int
    stack: int
    in_tournament: bool
    in_hand: bool
    folded: bool
    all_in: bool
    committed_round: int
    committed_hand: int
    hole_cards: list[str] = Field(default_factory=list)
    color: str
    last_action: PokerAction | dict[str, object] | None = None


class PokerHistoryEntry(StateModel):
    hand: int
    phase: str
    seat: int
    action: PokerAction | dict[str, object]


class PokerState(StateModel):
    tick: int
    hand_number: int
    phase: PokerPhase
    button: int
    blind_schedule: list[PokerBlindLevel] = Field(default_factory=list)
    level_idx: int
    hands_at_level: int
    small_blind: int
    big_blind: int
    deck: list[str] = Field(default_factory=list)
    community_cards: list[str] = Field(default_factory=list)
    pot: int
    side_pots: list[PokerSidePot] = Field(default_factory=list)
    current_bet: int
    min_raise: int
    action_on: int | None
    last_aggressor: int | None
    acted_this_round: list[int] = Field(default_factory=list)
    raise_locked_seats: list[int] = Field(default_factory=list)
    players: list[PokerPlayer]
    history: list[PokerHistoryEntry] = Field(default_factory=list)
    history_delta: list[PokerHistoryEntry] = Field(default_factory=list)
    placement: list[int] = Field(default_factory=list)
    pot_distribution: list[PokerPotDistribution] | None = None
    showdown_hands: dict[int, str] | None = None

    def player(self, seat: int) -> PokerPlayer:
        for player in self.players:
            if player.seat == seat:
                return player
        raise KeyError(f"seat {seat} not found")

    def to_call(self, seat: int) -> int:
        player = self.player(seat)
        return max(0, self.current_bet - player.committed_round)


class PokerBot(Bot):
    """Base class for typed Poker bots."""

    game = "poker"
    state_model: ClassVar[type[PokerState]] = PokerState

    def on_start(self, initial_state: PokerState) -> None:
        """Called once at game_start."""

    def act(self, state: PokerState) -> ActionResult:
        raise NotImplementedError


__all__ = [
    "PokerAction",
    "PokerBetAction",
    "PokerBlindLevel",
    "PokerBot",
    "PokerCallAction",
    "PokerCheckAction",
    "PokerFoldAction",
    "PokerHistoryEntry",
    "PokerPhase",
    "PokerPlayer",
    "PokerPotDistribution",
    "PokerRaiseAction",
    "PokerSidePot",
    "PokerState",
]
