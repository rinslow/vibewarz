"""Bot — the base class a vibecoder subclasses to write a bot.

Override `act(state)` and (optionally) `on_start` / `on_end`.

`act` may return either an action dict OR a tuple `(action, reasoning_text)`
— the reasoning is stored on the replay so viewers see what your bot was
thinking on each tick.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel

from .protocol import MatchPlayer

ActionDict = dict[str, Any]
ActionModel = BaseModel
ActionValue = ActionDict | ActionModel
ActionResult = ActionValue | tuple[ActionValue, str]


class Bot:
    """Subclass me and override `act(state)`."""

    game: str = ""  # subclasses set this, e.g. "curve"
    state_model: ClassVar[type[BaseModel] | None] = None

    # Populated by the runner before the first act() call.
    seat: int = -1
    match_id: str | None = None
    players: list[MatchPlayer] | None = None

    def on_start(self, initial_state: dict[str, Any]) -> None:
        """Called once at game_start."""

    def act(self, state: dict[str, Any]) -> ActionResult:
        raise NotImplementedError

    def on_end(self, placement: list[int], reason: str) -> None:
        """Called once at game_end. Default impl is a no-op."""

    def _coerce_state(self, state: dict[str, Any]) -> Any:
        """Return the callback state for this bot.

        Plain ``Bot`` instances receive the raw dict for full backward
        compatibility. Game-specific bot subclasses set ``state_model`` and
        receive a pydantic model instead.
        """
        model = self.state_model
        if model is None or isinstance(state, model):
            return state
        return model.model_validate(state)

    def _normalize_action_output(self, out: Any) -> tuple[Any, str | None]:
        """Convert a user callback return value to the wire action dict."""
        if isinstance(out, tuple):
            action, reasoning = out
        else:
            action, reasoning = out, None

        if isinstance(action, BaseModel):
            action = action.model_dump(mode="json")

        if not isinstance(action, dict):
            # Let the existing caller-side legality handling substitute the
            # default action locally; live runner will send the malformed value
            # just as it historically did for legacy bots.
            return action, reasoning
        return action, reasoning

    def _state_as_dict(self, state: dict[str, Any] | BaseModel) -> dict[str, Any]:
        if isinstance(state, BaseModel):
            return state.model_dump(mode="json")
        return state

    def legal_actions(self, state: dict[str, Any] | BaseModel) -> list[ActionDict]:
        """Return legal actions for this bot's current game and seat."""
        from vibewarz_games import GAMES

        if self.game not in GAMES:
            raise RuntimeError(f"unknown game {self.game!r}; known: {sorted(GAMES)}")
        return GAMES[self.game]().legal_actions(self._state_as_dict(state), self.seat)

    def default_action(self, state: dict[str, Any] | BaseModel) -> ActionDict:
        """Return the engine default action for this bot's current game."""
        from vibewarz_games import GAMES

        if self.game not in GAMES:
            raise RuntimeError(f"unknown game {self.game!r}; known: {sorted(GAMES)}")
        return GAMES[self.game]().default_action(self._state_as_dict(state), self.seat)
