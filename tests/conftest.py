import sys
from pathlib import Path

import pytest
from mcp.client import Client
from mcp_sqlite_memory.db import Database
from mcp_sqlite_memory.memory import Memory
from mcp_sqlite_memory.server import build_server
from mcp_sqlite_memory.settings import Settings

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def settings(tmp_path):
    return Settings(
        db_path=tmp_path / "memory.db",
        query_timeout=5.0,
        max_cell_chars=8000,
        max_result_bytes=131072,
    )


@pytest.fixture
def db(settings, monkeypatch):
    database = Database(settings)
    monkeypatch.setenv("MCP_SQLITE_DB", str(database.path))
    monkeypatch.delenv("SECOND_BRAIN_CADENCE", raising=False)
    return database


@pytest.fixture
def memory(db):
    return Memory(db)


@pytest.fixture
def server(settings, db):
    return build_server(settings)


@pytest.fixture
async def client(server):
    async with Client(server) as c:
        yield c
