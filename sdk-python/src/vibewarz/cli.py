"""CLI: `vibewarz login`, `vibewarz play <script>`, `vibewarz replay <id>`,
`vibewarz play-local --game <id> --bot a.py --bot b.py`."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
from pathlib import Path

import typer

from .bot import Bot
from .client import Client, default_api_url
from .play_local import DEFAULT_REPLAY_DIR
from .play_local import play as play_in_process
from .runner import run as run_bot

app = typer.Typer(add_completion=False, help="vibewarz — write bots, climb leaderboards.")


@app.command()
def login() -> None:
    """Print the steps to authenticate against the live arena.

    There's no CLI-driven login flow — the platform issues API keys
    through the web UI (Google sign-in). This command exists so users
    who type `vibewarz login` (a reasonable guess) get pointed at the
    right place instead of nothing.
    """
    typer.echo(
        "vibewarz authenticates via API key from your profile. Three steps:\n"
        "\n"
        "  1. Sign in at https://vibewarz.com (Google)\n"
        "  2. Open https://vibewarz.com/account to create a bot and copy its key\n"
        "  3. export VIBEWARZ_API_KEY=vw_live_...\n"
        "\n"
        "Then `vibewarz play my_bot.py --mode ranked` to climb the ladder.\n"
        "Local-only matches don't need any of this — see `vibewarz play-local --help`."
    )


@app.command()
def play(
    script: Path = typer.Argument(..., exists=True, readable=True, help="Path to a .py file containing a Bot subclass."),
    mode: str = typer.Option("practice", help="ranked | practice | challenge"),
    loop: int = typer.Option(1, help="Number of matches to play in a row."),
    bot_label: str = typer.Option(None, help="Label shown in replays."),
    guest_name: str = typer.Option(None, help="Override guest display name."),
) -> None:
    """Run a bot script against the live API."""
    spec = importlib.util.spec_from_file_location("user_bot_module", script)
    if spec is None or spec.loader is None:
        typer.echo(f"Could not load {script}", err=True)
        raise typer.Exit(1)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["user_bot_module"] = mod
    spec.loader.exec_module(mod)

    bot_cls = None
    for name in dir(mod):
        obj = getattr(mod, name)
        if (
            isinstance(obj, type)
            and issubclass(obj, Bot)
            and obj is not Bot
            and obj.__module__ == mod.__name__
        ):
            bot_cls = obj
            break
    if bot_cls is None:
        typer.echo("No Bot subclass found in script.", err=True)
        raise typer.Exit(1)

    run_bot(bot_cls(), mode=mode, loop=loop, bot_label=bot_label, guest_name=guest_name)


@app.command("play-local")
def play_local(
    game: str = typer.Option(..., help="Game id, e.g. curve | poker | blast."),
    bot: list[Path] = typer.Option(..., "--bot", help="Path to a bot script. Pass --bot once per seat."),
    name: list[str] = typer.Option(
        None,
        "--name",
        help="Display name for a seat, in --bot order. Pass --name once per --bot (or not at all).",
    ),
    seed: int = typer.Option(None, help="Random seed for reproducible matches."),
    max_ticks: int = typer.Option(None, help="Override the game's default max-ticks limit."),
    verbose: bool = typer.Option(False, help="Print eliminations + illegal-action substitutions."),
    record: bool = typer.Option(
        True,
        "--record/--no-record",
        help=(
            "Write a JSONL replay to ./data/replays/{match_id}.jsonl. On by "
            "default — pass --no-record for throwaway runs (e.g. benchmark loops)."
        ),
    ),
    replay_dir: Path = typer.Option(
        None,
        "--replay-dir",
        help="Override the replay output directory. Defaults to ./data/replays.",
    ),
) -> None:
    """Run an in-process match between N bot scripts. No server, no auth."""
    for p in bot:
        if not p.exists() or not p.is_file():
            typer.echo(f"bot file not found: {p}", err=True)
            raise typer.Exit(1)
    try:
        result = play_in_process(
            game_id=game,
            bot_paths=list(bot),
            seed=seed,
            max_ticks=max_ticks,
            verbose=verbose,
            record=record,
            replay_dir=replay_dir,
            names=list(name) if name else None,
        )
    except RuntimeError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    typer.echo(
        f"{result.match_id}: placement={result.placement} reason={result.reason} ticks={result.ticks}"
    )
    if result.replay_path is not None:
        typer.echo(f"replay: {result.replay_path}")
        typer.echo(f"watch:  vibewarz replay {result.match_id} --watch")


@app.command()
def replay(
    match_id: str,
    watch: bool = typer.Option(
        False,
        "--watch",
        help=(
            "Boot the bundled React viewer and open it in a browser. The URL "
            "is also printed to stdout so headless/SSH sessions can use it."
        ),
    ),
    api_url: str = typer.Option(
        None,
        "--api-url",
        envvar="VIBEWARZ_API_URL",
        help="Remote API to fetch from (e.g. wss://api.vibewarz.com/ws). When unset, walks ./data/replays for a local JSONL file.",
    ),
    api_key: str = typer.Option(
        None,
        "--api-key",
        envvar="VIBEWARZ_API_KEY",
        help="API key for authenticated fetch. Replays are currently public; this is forward-compat.",
    ),
    path: Path = typer.Option(
        None,
        "--path",
        help="Explicit JSONL file path. Overrides the default ./data/replays lookup.",
    ),
    pretty: bool = typer.Option(
        None,
        "--pretty/--compact",
        help=(
            "Pretty-print (indented) vs compact (one JSON object per line). "
            "Defaults: --pretty for local file reads (open-and-skim), "
            "--compact for remote fetches (jq-friendly). Ignored with --watch."
        ),
    ),
) -> None:
    """Print a replay's tick log to stdout, or open it in the React viewer.

    With --watch: boots a local HTTP server on 127.0.0.1 (random port),
    opens the bundled @vibewarz/replay-viewer SPA, and serves the JSONL as
    the replay envelope. Press Ctrl-C to stop. Requires the viewer assets
    that ship with the wheel.

    With --api-url (or VIBEWARZ_API_URL): fetches over HTTP from the live
    API. Default output is compact, one JSON object per line — pipe to jq:

      vibewarz replay m_abc1234 | jq 'select(.type=="game_end")'

    Without flags: walks ./data/replays for a JSONL file (the local
    backend writes there during dev). Default output is indented for
    direct reading; pass --compact if you're piping somewhere.
    """
    if watch:
        if api_url:
            typer.echo(
                "--watch serves a local JSONL file; --api-url is ignored. "
                "Drop --api-url to use the bundled viewer with a local replay.",
                err=True,
            )
        jsonl = _locate_local_jsonl(match_id, path)
        if jsonl is None:
            raise typer.Exit(1)
        # Imported lazily so users on a stripped-down install (no viewer_dist
        # because they vendored the SDK) only hit the missing-asset error
        # when they actually try to use --watch.
        from .replay_server import serve as _serve

        try:
            _serve(jsonl, match_id)
        except RuntimeError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(1) from e
        return

    if api_url:
        envelope = asyncio.run(_fetch_remote_replay(match_id, api_url, api_key))
        events = envelope.get("events", [])
        typer.echo(
            f"fetched {len(events)} events for {match_id} (game={envelope.get('game_id')})",
            err=True,
        )
        # Remote default: compact (one-per-line) so the output pipes
        # cleanly through jq without `slurp` mode.
        indent = 2 if pretty is True else None
        for evt in events:
            typer.echo(json.dumps(evt, indent=indent))
        return

    jsonl = _locate_local_jsonl(match_id, path)
    if jsonl is None:
        raise typer.Exit(1)
    # Local default: indented. Preserves the pre-remote-mode behavior of
    # `vibewarz replay <id>` for users who just want to eyeball a file.
    indent = None if pretty is False else 2
    for line in jsonl.read_text().splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        typer.echo(json.dumps(obj, indent=indent))


def _locate_local_jsonl(match_id: str, explicit_path: Path | None) -> Path | None:
    if explicit_path is not None:
        if not explicit_path.exists():
            typer.echo(f"replay file not found: {explicit_path}", err=True)
            return None
        return explicit_path
    root = DEFAULT_REPLAY_DIR.resolve()
    candidates = list(root.rglob(f"{match_id}.jsonl"))
    if not candidates:
        typer.echo(
            f"No replay file found for {match_id} under {root}. "
            "Set --api-url or VIBEWARZ_API_URL to fetch from the live API, "
            "or pass --path /path/to/{match_id}.jsonl.",
            err=True,
        )
        return None
    return candidates[0]


async def _fetch_remote_replay(match_id: str, api_url: str, api_key: str | None) -> dict:
    # We don't need a WS connection for the fetch, but Client owns the
    # url→http translation logic. Use it without opening a socket.
    key = api_key or os.environ.get("VIBEWARZ_API_KEY")
    client = Client(url=api_url or default_api_url(), api_key=key)
    envelope = await client.fetch_replay(match_id)
    return envelope.model_dump(mode="json")


if __name__ == "__main__":
    app()
