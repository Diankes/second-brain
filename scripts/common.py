"""Shared helpers for the second-brain hook scripts. Standard library only, so the hooks
start fast and need nothing installed beyond a Python interpreter."""

import json
import os
import sqlite3
import sys
from pathlib import Path

RAW_KINDS = ("prompt", "compaction", "session-end", "response")  # hooks only, never the model
SYNTHESIS_KINDS = ("insight", "decision", "reading", "open-question", "note")
PLUGIN_ROOT = Path(__file__).resolve().parent.parent
DB_ENV = "MCP_SQLITE_DB"
CADENCE_ENV = "SECOND_BRAIN_CADENCE"
DEFAULT_CADENCE = 6


def read_hook_input() -> dict:
    """The JSON Claude Code writes to a hook's stdin; {} when there is none."""
    try:
        raw = sys.stdin.read()
    except OSError:
        return {}
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def db_path() -> Path | None:
    value = os.environ.get(DB_ENV, "").strip()
    return Path(value).expanduser() if value else None


def connect_readonly(path: Path) -> sqlite3.Connection:
    """Open the memory database without ever taking a write lock."""
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2.0)


def cadence_threshold() -> int:
    try:
        return int(os.environ.get(CADENCE_ENV, DEFAULT_CADENCE))
    except ValueError:
        return DEFAULT_CADENCE


def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload))
    sys.stdout.flush()
