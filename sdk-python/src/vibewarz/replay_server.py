"""Tiny stdlib HTTP server that serves a single local JSONL replay to the
bundled React viewer.

Why this exists: `vibewarz play-local` writes a JSONL replay to disk, but the
viewer is a static SPA built from `@vibewarz/replay-viewer`. The SPA fetches
`/replay.json` (the envelope shape the platform's `/api/replays/{id}` also
returns) and then renders. So all this module does is:

  GET /replay.json  →  {match_id, game_id, events: [...]}
  GET /             →  the SPA's index.html (with viewer_dist/assets/*)
  GET /assets/...   →  the SPA's JS/CSS bundles

No DB, no auth, no FastAPI dep — stdlib only, fits in a wheel.

The viewer assets live under `sdk-python/src/vibewarz/viewer_dist/`, populated
by `pnpm -F viewer build` at the OSS workspace root and committed for end
users who install via pip.
"""

from __future__ import annotations

import contextlib
import json
import threading
import webbrowser
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any

from .protocol.replay import ReplayEnvelope


def _read_envelope(jsonl_path: Path, match_id: str) -> dict[str, Any]:
    """Parse a JSONL file into the ReplayEnvelope shape.

    Validates via the pydantic models so a corrupt line surfaces early
    rather than blowing up the SPA with an unhelpful console error.
    Mirrors the closed-source LocalReplayStore.serve() output verbatim.
    """
    events: list[dict[str, Any]] = []
    with jsonl_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                events.append(json.loads(stripped))
    game_id: str | None = None
    if events and events[0].get("type") == "game_start":
        gid = events[0].get("game_id")
        if isinstance(gid, str):
            game_id = gid
    envelope: dict[str, Any] = {
        "match_id": match_id,
        "events": events,
    }
    if game_id is not None:
        envelope["game_id"] = game_id
    # Round-trip through pydantic so the envelope shape matches the platform's
    # `/api/replays/{id}` output exactly. This is the same JSON the React
    # viewer consumes server-side or here — single schema, two transports.
    return ReplayEnvelope.model_validate(envelope).model_dump(mode="json")


_MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".map": "application/json",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}


def _viewer_dist_root() -> Path:
    """Return the path to the bundled viewer_dist directory.

    Uses importlib.resources so the lookup works the same whether the
    package was installed as a wheel or in editable mode.
    """
    ref = resources.files("vibewarz").joinpath("viewer_dist")
    # `as_file` would give a context manager for zipped installs, but
    # hatchling produces a regular wheel layout for this package — the
    # MultiplexedPath / PosixPath subclass returned by `files()` exposes a
    # filesystem path via its __fspath__/`__str__`. Cast to Path for
    # ergonomic joinpath/exists() calls below.
    return Path(str(ref))


class _ReplayHandler(BaseHTTPRequestHandler):
    """HTTP handler bound to a single (envelope, viewer_dist) pair.

    The envelope and root are stuffed onto the server instance by `serve()`
    below; the handler picks them up via self.server. This keeps the
    handler class itself thread-safe and avoids module-level mutable state.
    """

    # silence the per-request log; the CLI prints what matters once at boot.
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002, ARG002
        return

    def do_GET(self) -> None:  # noqa: N802
        envelope: dict[str, Any] = self.server.envelope  # type: ignore[attr-defined]
        viewer_root: Path = self.server.viewer_root  # type: ignore[attr-defined]

        path = self.path.split("?", 1)[0]
        if path == "/replay.json":
            body = json.dumps(envelope).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return

        # Static file lookup. "/" → index.html; anything else is resolved
        # under viewer_dist. Constrain to that subtree so a `..` traversal
        # can't escape into the user's filesystem.
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        try:
            target = (viewer_root / rel).resolve()
            target.relative_to(viewer_root.resolve())
        except (ValueError, OSError):
            self.send_error(404)
            return
        if not target.exists() or not target.is_file():
            # SPA-style fallback: serve index.html for unknown routes so deep
            # links work. Limit to extensionless paths to avoid masking real
            # 404s on missing JS/CSS bundles.
            if not Path(rel).suffix:
                target = viewer_root / "index.html"
                if not target.exists():
                    self.send_error(404)
                    return
            else:
                self.send_error(404)
                return

        mime = _MIME.get(target.suffix.lower(), "application/octet-stream")
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class _ReplayServer(ThreadingHTTPServer):
    """ThreadingHTTPServer with envelope + viewer_root attributes attached."""

    envelope: dict[str, Any]
    viewer_root: Path
    daemon_threads = True
    allow_reuse_address = True


@contextmanager
def _bind(host: str, port: int) -> Iterator[_ReplayServer]:
    server = _ReplayServer((host, port), _ReplayHandler)
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def serve(
    jsonl_path: Path,
    match_id: str,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    open_browser: bool = True,
) -> None:
    """Boot the viewer for one replay and block until Ctrl-C.

    Pass port=0 to let the OS pick a free port; the actual URL is printed
    to stdout so headless / SSH sessions can copy it.
    """
    envelope = _read_envelope(jsonl_path, match_id)
    viewer_root = _viewer_dist_root()
    if not viewer_root.exists() or not (viewer_root / "index.html").exists():
        raise RuntimeError(
            f"viewer assets not found at {viewer_root}. If you're running "
            "from a source checkout, build them with `pnpm -F viewer build` "
            "at the workspace root."
        )

    with _bind(host, port) as server:
        server.envelope = envelope
        server.viewer_root = viewer_root
        bound_host, bound_port = server.server_address[:2]
        url = f"http://{bound_host}:{bound_port}/?match_id={match_id}"
        # Print first; webbrowser.open may block briefly on platforms where
        # it spawns a real browser process, and we want the URL visible
        # immediately for SSH / headless sessions.
        print(f"vibewarz replay viewer: {url}", flush=True)
        print("Press Ctrl-C to stop.", flush=True)

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        if open_browser:
            # No browser available (SSH session, container) → swallow; the
            # URL is already on stdout, so the user can still get there.
            with contextlib.suppress(Exception):
                webbrowser.open(url)

        with contextlib.suppress(KeyboardInterrupt):
            thread.join()
