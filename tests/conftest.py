"""
Shared pytest fixtures and dependency mocks for BMO tests.

Heavy / system-only packages (ollama, spotipy, whisper, pygame, …) are injected
into sys.modules as MagicMocks *before* bmo_core / bmo_web are imported so the
test suite runs without those packages installed.
"""

import sys
import os
import types
from unittest.mock import MagicMock

import pytest

# ── src/ auf den Suchpfad legen (Dateien liegen in src/, nicht im Root) ─────
_SRC = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


# ── Mock heavy dependencies before any bmo_* import ────────────────────────

def _mock(name: str) -> MagicMock:
    m = MagicMock()
    m.__name__ = name
    m.__spec__ = None
    return m


_STUB_NAMES = [
    "ollama",
    "spotipy",
    "spotipy.oauth2",
    "whisper",
    "pygame",
    "pygame.mixer",
    "feedparser",
    "mss",          # neu: Screen-Capture
    "pyautogui",    # neu: Remote Control
    "winotify",     # neu: Windows Notifications
]

for _name in _STUB_NAMES:
    if _name not in sys.modules:
        sys.modules[_name] = _mock(_name)

# PIL: echtes ModuleType damit `from PIL import ImageGrab, Image` funktioniert
if "PIL" not in sys.modules:
    _pil = types.ModuleType("PIL")
    _pil.ImageGrab = MagicMock()   # type: ignore[attr-defined]
    _pil.Image     = MagicMock()   # type: ignore[attr-defined]
    sys.modules["PIL"]          = _pil
    sys.modules["PIL.ImageGrab"] = _pil.ImageGrab  # type: ignore[attr-defined]
    sys.modules["PIL.Image"]     = _pil.Image      # type: ignore[attr-defined]


# ── Import apps (safe now that stubs are registered) ────────────────────────

import bmo_core  # noqa: E402
import bmo_web   # noqa: E402


# ── Flask test clients ───────────────────────────────────────────────────────

@pytest.fixture()
def core_client():
    bmo_core.app.config["TESTING"] = True
    with bmo_core.app.test_client() as client:
        yield client


@pytest.fixture()
def web_client():
    bmo_web.app.config["TESTING"] = True
    bmo_web.app.config["SECRET_KEY"] = "test-secret-key"
    with bmo_web.app.test_client() as client:
        yield client


# ── Reset mutable global state between tests ────────────────────────────────

@pytest.fixture(autouse=True)
def reset_core_globals():
    """Clear conversation history and active timers before every test."""
    bmo_core._conversation_history = []
    bmo_core._active_timers = []
    bmo_core._spotify = None
    yield
    bmo_core._conversation_history = []
    bmo_core._active_timers = []
    bmo_core._spotify = None
