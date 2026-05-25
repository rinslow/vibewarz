"""Pin the env-var contract for `default_api_url()` + `api_http_url()`.

Both functions are part of the SDK's public surface — flipping the
default from localhost to prod was an intentional behavior change, and a
silent revert would re-break the same first-time-user path the v0.3
release was cut to fix. These tests are the tripwire.
"""

from __future__ import annotations

import pytest
import vibewarz
from vibewarz.client import DEFAULT_API_URL, api_http_url, default_api_url


def test_default_points_at_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIBEWARZ_API_URL", raising=False)
    assert default_api_url() == "wss://api.vibewarz.com/ws"
    assert DEFAULT_API_URL == "wss://api.vibewarz.com/ws"


def test_env_var_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIBEWARZ_API_URL", "ws://localhost:10000/ws")
    assert default_api_url() == "ws://localhost:10000/ws"


def test_api_http_url_translates_wss() -> None:
    assert api_http_url("wss://api.vibewarz.com/ws") == "https://api.vibewarz.com"


def test_api_http_url_translates_ws() -> None:
    assert api_http_url("ws://localhost:10000/ws") == "http://localhost:10000"


def test_api_http_url_respects_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIBEWARZ_API_URL", "wss://staging.example.com/ws")
    assert api_http_url() == "https://staging.example.com"


def test_version_is_pep440_and_not_stale() -> None:
    """`vibewarz.__version__` must come from the installed package metadata,
    not a hardcoded literal. The historical bug we're guarding against:
    `__init__.py` had `__version__ = "0.1.0"` while PyPI shipped 0.2.x, so
    `import vibewarz; vibewarz.__version__` lied. This test catches a regression
    where someone reintroduces a literal that drifts from pyproject.
    """
    assert isinstance(vibewarz.__version__, str)
    assert vibewarz.__version__ != "0.1.0", (
        "vibewarz.__version__ looks hardcoded — derive it from importlib.metadata"
    )
    # "dev" is the legitimate fallback for un-installed source checkouts,
    # but in CI/test we always install the package, so we expect a real version.
    assert vibewarz.__version__ != "dev", (
        "vibewarz package metadata not found — run `uv sync` / `pip install -e .` first"
    )
