"""Low-level WS client — encodes/decodes vibewarz protocol frames.

The high-level `run()` helper in runner.py wraps this with the Bot lifecycle.
Power users can use Client directly for batched/parallel play.

Wire frames are validated by the shared Pydantic models in
`vibewarz.protocol`, so the client gets typed objects (e.g. `TickRequestS2C`)
instead of raw dicts.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection

# Use the package-level __version__ (sourced from importlib.metadata in
# __init__.py) so the wire tag and `vibewarz.__version__` can never drift.
from . import __version__
from .protocol import (
    ApiKeyAuth,
    AuthPayload,
    ClientMessage,
    GuestAuth,
    HelloC2S,
    QueueC2S,
    ServerMessage,
    UserInfo,
    WelcomeS2C,
    decode_server,
    encode_client,
)


class Client:
    def __init__(
        self,
        url: str,
        api_key: str | None = None,
        guest_name: str | None = None,
        guest_token: str | None = None,
    ) -> None:
        self.url = url
        self.api_key = api_key
        self.guest_name = guest_name
        self.guest_token = guest_token
        self._ws: ClientConnection | None = None
        self.session_id: str | None = None
        self.user: UserInfo | None = None

    async def __aenter__(self) -> Client:
        self._ws = await websockets.connect(self.url, max_size=8 * 1024 * 1024)
        await self._hello()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._ws:
            await self._ws.close()

    def _build_auth(self) -> AuthPayload:
        if self.api_key:
            return ApiKeyAuth(token=self.api_key)
        if self.guest_token:
            return GuestAuth(token=self.guest_token)
        return GuestAuth(display_name=self.guest_name)

    async def _hello(self) -> None:
        assert self._ws is not None
        hello = HelloC2S(
            id=uuid.uuid4().hex[:8],
            sdk_version=f"python-{__version__}",
            auth=self._build_auth(),
        )
        await self._ws.send(encode_client(hello))
        welcome = decode_server(await self._ws.recv())
        if not isinstance(welcome, WelcomeS2C):
            raise RuntimeError(f"expected welcome, got {welcome!r}")
        self.session_id = welcome.session_id
        self.user = welcome.user

    async def send(self, msg: ClientMessage) -> None:
        assert self._ws is not None
        await self._ws.send(encode_client(msg))

    async def recv(self) -> ServerMessage:
        assert self._ws is not None
        return decode_server(await self._ws.recv())

    async def messages(self) -> AsyncIterator[ServerMessage]:
        assert self._ws is not None
        async for raw in self._ws:
            yield decode_server(raw)

    async def queue(self, game: str, mode: str = "ranked", bot_label: str | None = None) -> None:
        await self.send(
            QueueC2S(
                id=uuid.uuid4().hex[:8],
                game=game,
                mode=mode,
                bot_label=bot_label,
            )
        )


# Public production WS endpoint. Override with VIBEWARZ_API_URL when
# pointing at a local dev server or a staging environment, e.g.
#   export VIBEWARZ_API_URL=ws://localhost:10000/ws
DEFAULT_API_URL = "wss://api.vibewarz.com/ws"


def default_api_url() -> str:
    return os.environ.get("VIBEWARZ_API_URL", DEFAULT_API_URL)


def api_http_url(ws_url: str | None = None) -> str:
    url = ws_url or default_api_url()
    if url.startswith("ws://"):
        return "http://" + url[5:].rstrip("/").removesuffix("/ws")
    if url.startswith("wss://"):
        return "https://" + url[6:].rstrip("/").removesuffix("/ws")
    return url
