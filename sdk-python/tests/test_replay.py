"""Client.fetch_replay() — happy path + 302→S3 redirect follow.

The server has two replay storage backends:
  - Local (dev): returns a JSON envelope inline.
  - S3 (prod): returns 302 to a presigned S3 URL.

httpx follows redirects transparently, so the SDK doesn't care which
backend served the response. Verify both paths by injecting an
AsyncClient backed by a MockTransport.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import httpx
import pytest
from vibewarz.client import Client
from vibewarz.protocol import GameStartEvt, ReplayEnvelope, TickResultEvt


def _envelope_json() -> dict:
    return {
        "match_id": "m_test",
        "game_id": "curve",
        "events": [
            {
                "type": "game_start",
                "seed": 42,
                "state": {"tick": 0, "players": []},
                "match_id": "m_test",
                "game_id": "curve",
            },
            {
                "type": "game_end",
                "ts": 1,
                "match_id": "m_test",
                "placement": [0, 1],
                "reason": "elimination",
                "final_state": {"tick": 10, "players": []},
            },
        ],
    }


@contextmanager
def mock_http(handler) -> Iterator[httpx.AsyncClient]:
    """Wrap an httpx.MockTransport in the same AsyncClient flags
    fetch_replay would build for itself."""
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(
        transport=transport, follow_redirects=True, timeout=30.0
    )
    try:
        yield client
    finally:
        # AsyncClient.aclose is async; tests already drive the event loop
        # via pytest-asyncio, so the caller can await close itself. We rely
        # on GC for the MockTransport since it owns no real socket.
        pass


@pytest.mark.asyncio
async def test_fetch_replay_inline_envelope() -> None:
    expected = _envelope_json()

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/replays/m_test"
        return httpx.Response(200, json=expected)

    client = Client(url="wss://api.vibewarz.com/ws")
    with mock_http(handler) as http:
        env = await client.fetch_replay("m_test", http=http)
        await http.aclose()

    assert isinstance(env, ReplayEnvelope)
    assert env.match_id == "m_test"
    assert env.game_id == "curve"
    assert len(env.events) == 2
    assert isinstance(env.events[0], GameStartEvt)


@pytest.mark.asyncio
async def test_fetch_replay_follows_302() -> None:
    expected = _envelope_json()

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/api/replays/m_test":
            return httpx.Response(
                302,
                headers={"Location": "https://s3.example.com/replays/m_test.json"},
            )
        if req.url.host == "s3.example.com":
            return httpx.Response(200, json=expected)
        return httpx.Response(404)

    client = Client(url="wss://api.vibewarz.com/ws")
    with mock_http(handler) as http:
        env = await client.fetch_replay("m_test", http=http)
        await http.aclose()
    assert env.match_id == "m_test"
    assert env.game_id == "curve"


@pytest.mark.asyncio
async def test_fetch_replay_legacy_envelope_without_game_id() -> None:
    """Replays written before envelope tagging shipped don't have
    `envelope.game_id`. The model should still parse — game_id is
    Optional — leaving recovery to viewers via state-shape inference."""
    payload = {
        "match_id": "m_legacy",
        "events": [
            {
                "type": "game_start",
                "seed": 1,
                "state": {},
                "match_id": "m_legacy",
            },
        ],
    }

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = Client(url="ws://localhost:10000/ws")
    with mock_http(handler) as http:
        env = await client.fetch_replay("m_legacy", http=http)
        await http.aclose()
    assert env.match_id == "m_legacy"
    assert env.game_id is None


def test_game_start_names_parses_string_keys_and_defaults_none() -> None:
    """`names` is keyed by seat — string keys over the wire, int keys in the
    model (same coercion as TickResultEvt.actions). Absent on replays written
    before naming shipped, so it must default to None."""
    named = GameStartEvt.model_validate(
        {
            "type": "game_start",
            "seed": 1,
            "state": {},
            "match_id": "m1",
            "game_id": "vibelords",
            "names": {"0": "Anthropic", "1": "OpenAI"},
        }
    )
    assert named.names == {0: "Anthropic", 1: "OpenAI"}

    legacy = GameStartEvt.model_validate(
        {"type": "game_start", "seed": 1, "state": {}, "match_id": "m1"}
    )
    assert legacy.names is None


def test_tick_result_actions_parses_string_keys() -> None:
    """JSON has no integer keys — the server serializes `actions: dict[int,
    ...]` with string seat numbers ("0", "1", ...). Pydantic v2 coerces
    str→int on dict keys by default; this test pins that behavior so a
    future model_config change (e.g. strict mode) can't silently break the
    replay parse path.
    """
    evt = TickResultEvt.model_validate(
        {
            "type": "tick_result",
            "ts": 1,
            "match_id": "m1",
            "tick": 1,
            "state": {"tick": 1, "players": []},
            # String keys, exactly what arrives over the wire.
            "actions": {"0": {"turn": "left"}, "1": None, "2": {"turn": "right"}},
            "eliminated": [],
        }
    )
    assert evt.actions == {0: {"turn": "left"}, 1: None, 2: {"turn": "right"}}
    assert all(isinstance(k, int) for k in evt.actions)
