from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from vibewarz import (
    Bot,
    CurveAction,
    CurveBot,
    CurveState,
    PokerState,
    VibelordsState,
)
from vibewarz.games import BlastState
from vibewarz.play_local import play
from vibewarz_games.blast.game import Blast
from vibewarz_games.curve.game import Curve
from vibewarz_games.poker.game import Poker
from vibewarz_games.vibelords.game import Vibelords


def test_typed_bot_coerces_state_and_normalizes_action_model() -> None:
    class TurnRight(CurveBot):
        def act(self, state: CurveState):
            assert isinstance(state, CurveState)
            return CurveAction(turn="RIGHT"), "turning"

    bot = TurnRight()
    bot.seat = 0
    raw = Curve().snapshot_view_for(Curve().initial_state(seed=1, num_players=4), 0)

    typed = bot._coerce_state({**raw, "future_server_field": {"ok": True}})
    assert isinstance(typed, CurveState)
    assert typed.future_server_field == {"ok": True}
    assert typed.player(0).seat == 0

    action, reasoning = bot._normalize_action_output(bot.act(typed))
    assert action == {"turn": "RIGHT"}
    assert reasoning == "turning"


def test_action_models_forbid_extra_fields() -> None:
    with pytest.raises(ValidationError):
        CurveAction(turn="LEFT", surprise=True)


def test_legacy_bot_still_receives_raw_dict() -> None:
    class Legacy(Bot):
        game = "curve"

        def act(self, state):
            return {"turn": "STRAIGHT"}

    bot = Legacy()
    raw = {"tick": 0}
    assert bot._coerce_state(raw) is raw
    assert bot._normalize_action_output(bot.act(raw)) == ({"turn": "STRAIGHT"}, None)


def test_all_state_models_validate_real_bot_views() -> None:
    cases = [
        (Curve(), CurveState, 4),
        (Blast(), BlastState, 2),
        (Poker(), PokerState, 2),
        (Vibelords(), VibelordsState, 2),
    ]
    for engine, model, num_players in cases:
        state = engine.initial_state(seed=7, num_players=num_players)
        view = engine.snapshot_view_for(state, 0)
        typed = model.model_validate(view)
        assert typed.tick == 0


def test_play_local_accepts_typed_action_models(tmp_path: Path) -> None:
    bot_path = tmp_path / "curve_typed.py"
    bot_path.write_text(
        """
from vibewarz import CurveAction, CurveBot

class TypedCurve(CurveBot):
    def act(self, state):
        return CurveAction(turn="RIGHT")
""".lstrip(),
        encoding="utf-8",
    )

    result = play(
        "curve",
        [bot_path, bot_path, bot_path, bot_path],
        seed=1,
        max_ticks=1,
        record=True,
        replay_dir=tmp_path,
    )

    assert result.replay_path is not None
    events = [json.loads(line) for line in result.replay_path.read_text().splitlines()]
    tick = next(evt for evt in events if evt["type"] == "tick_result")
    assert tick["actions"] == {
        "0": {"turn": "RIGHT"},
        "1": {"turn": "RIGHT"},
        "2": {"turn": "RIGHT"},
        "3": {"turn": "RIGHT"},
    }


def test_play_local_poker_on_start_uses_typed_redacted_view(
    tmp_path: Path,
    monkeypatch,
) -> None:
    probe_path = tmp_path / "probe.jsonl"
    bot_path = tmp_path / "poker_probe.py"
    bot_path.write_text(
        """
import json
import os
from pathlib import Path

from vibewarz import PokerBot, PokerCheckAction, PokerFoldAction

class ProbePoker(PokerBot):
    def on_start(self, state):
        Path(os.environ["VW_PROBE_PATH"]).open("a", encoding="utf-8").write(
            json.dumps({
                "seat": self.seat,
                "state_type": type(state).__name__,
                "own_hole_cards": state.player(self.seat).hole_cards,
                "other_hole_cards": [
                    p.hole_cards for p in state.players if p.seat != self.seat
                ],
            }) + "\\n"
        )

    def act(self, state):
        if state.to_call(self.seat) > 0:
            return PokerFoldAction()
        return PokerCheckAction()
""".lstrip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("VW_PROBE_PATH", str(probe_path))

    play("poker", [bot_path, bot_path], seed=1, max_ticks=1, record=False)

    records = [json.loads(line) for line in probe_path.read_text().splitlines()]
    assert {record["seat"] for record in records} == {0, 1}
    for record in records:
        assert record["state_type"] == "PokerState"
        assert len(record["own_hole_cards"]) == 2
        assert record["other_hole_cards"] == [[]]


def test_vibelords_typed_views_preserve_queue_redaction() -> None:
    engine = Vibelords()
    state = engine.initial_state(seed=1, num_players=2)
    state = engine.step(
        state,
        {0: {"type": "build", "unit": "pike"}, 1: {"type": "noop"}},
    ).state

    seat0_view = VibelordsState.model_validate(engine.view_for(state, 0))
    seat1_view = VibelordsState.model_validate(engine.view_for(state, 1))

    assert len(seat0_view.player(0).queue) == 1
    assert seat1_view.player(0).queue == []
