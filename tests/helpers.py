"""Shared test helpers: run hook scripts as subprocesses, parse views.sql, bootstrap a database."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
VIEWS_SQL = ROOT / "references" / "views.sql"

VALID_INSIGHT = """Spectral theorem gives the variational characterisation of eigenvalues
Context: comparing two proofs of Courant-Fischer for the seminar
Claim: for symmetric $A$ with eigenvalues $\\lambda_1 \\ge \\dots \\ge \\lambda_n$,
$$\\lambda_k = \\max_{\\dim S = k} \\min_{x \\in S,\\, \\|x\\| = 1} x^\\top A x .$$
Why: orthonormal eigenbasis plus a dimension count on the two subspaces
Rejected: the induction in the lecture notes; it hides the dimension-counting step
Open: the compact self-adjoint case
Source: strang-la §6.4
tags: #linear-algebra #spectral-theorem"""

VALID_DECISION = """Use the variational proof in the seminar
Context: two proofs available, forty minutes of slot
Options: A: variational proof; B: induction from the notes
Rejected: B because the audience has not seen the induction hypothesis
Decision: present A, with the dimension count on one slide
Revisit when: the slot changes or the audience changes
Source: discussion
tags: #seminar #spectral-theorem"""

VALID_CHECKPOINT = """Goal: a clean seminar talk on Courant-Fischer
Done: proof chosen (#2), variational statement recorded (#1)
In progress: slides, dimension-count figure half done
Open: whether to mention compact operators
Next: finish the figure, then rehearse the dimension-count step
tags: #seminar #spectral-theorem"""


def run_script(name: str, payload: dict, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run a hook script exactly as Claude Code would: JSON on stdin, environment, exit code."""
    merged = dict(os.environ)
    if env:
        merged.update(env)
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=merged,
        timeout=60,
    )


def hook_input(tool: str, **tool_input) -> dict:
    return {
        "session_id": "test",
        "hook_event_name": "PreToolUse",
        "tool_name": f"mcp__sqlite-memory__{tool}",
        "tool_input": tool_input,
    }


def parse_views_sql(path: Path = VIEWS_SQL) -> list[dict]:
    """Blocks of views.sql: {'kind': 'table'|'view', 'name', 'description', 'sql'}."""
    blocks: list[dict] = []
    current: dict | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        header = re.match(r"^-- (table|view): (\S+)\s*$", line)
        if header:
            current = {
                "kind": header.group(1),
                "name": header.group(2),
                "description": "",
                "sql": "",
            }
            blocks.append(current)
            continue
        if current is None:
            continue
        description = re.match(r"^-- description: (.*)$", line)
        if description:
            current["description"] = description.group(1).strip()
        elif not line.startswith("--"):
            current["sql"] += line + "\n"
    for block in blocks:
        block["sql"] = block["sql"].strip().rstrip(";").strip()
    return blocks


def register_source(db, key="strang-la", kind="textbook", title="Introduction to Linear Algebra"):
    with db.internal() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS sources (key TEXT PRIMARY KEY, kind TEXT NOT NULL, "
            "title TEXT NOT NULL, authors TEXT, year INTEGER, locator TEXT, added TEXT NOT NULL, "
            "notes TEXT)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO sources(key, kind, title, added) VALUES (?, ?, ?, '2026-09-13')",
            (key, kind, title),
        )


def text(result) -> str:
    return "".join(b.text for b in result.content if getattr(b, "type", None) == "text")
