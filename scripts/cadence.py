"""Stop hook: refuse to end the turn once too many prompts have gone by without a curated entry.

The trigger is deterministic; the content is the model's. This script never writes anything.

Loop safety, in order:
1. If stop_hook_active is true, Claude is already continuing because of a Stop hook; this
   script exits 0 immediately, so it blocks at most once per turn.
2. Blocking only helps when the model can satisfy the condition: any curated append_event or a
   checkpoint moves the anchor, and the count drops to zero.
3. Claude Code itself stops honouring a Stop hook after eight consecutive blocks.

The threshold comes from SECOND_BRAIN_CADENCE (default 6, 0 disables).
"""

import sqlite3
import sys
from contextlib import closing

from common import SYNTHESIS_KINDS, cadence_threshold, connect_readonly, db_path, read_hook_input

REASON = (
    "second-brain: {n} prompts since the last curated entry (threshold {threshold}). Before "
    "stopping, record what this stretch produced with append_event, kind insight, decision, "
    "reading or open-question, following the template for that kind in the second-brain "
    "plugin (references/templates.md, or load /second-brain:memory). If nothing here "
    "deserves a curated entry, write a checkpoint instead, with the summary:\n"
    "Goal: ...\nDone: ...\nIn progress: ...\nOpen: ...\nNext: ...\ntags: #...\n"
    "SECOND_BRAIN_CADENCE tunes the threshold; 0 disables this check."
)


def prompts_since_last_curated(conn: sqlite3.Connection) -> int:
    placeholders = ", ".join("?" for _ in SYNTHESIS_KINDS)
    curated = conn.execute(
        f"SELECT coalesce(max(id), 0) FROM memory_events WHERE kind IN ({placeholders})",
        SYNTHESIS_KINDS,
    ).fetchone()[0]
    checkpointed = conn.execute(
        "SELECT coalesce(max(last_event_id), 0) FROM memory_checkpoints"
    ).fetchone()[0]
    anchor = max(curated, checkpointed)
    return conn.execute(
        "SELECT count(*) FROM memory_events WHERE kind = 'prompt' AND id > ?", (anchor,)
    ).fetchone()[0]


def main() -> int:
    data = read_hook_input()
    if data.get("stop_hook_active"):
        return 0
    threshold = cadence_threshold()
    if threshold <= 0:
        return 0
    path = db_path()
    if path is None or not path.is_file():
        return 0
    try:
        with closing(connect_readonly(path)) as conn:
            n = prompts_since_last_curated(conn)
    except sqlite3.Error as exc:
        print(f"second-brain cadence: could not read the database ({exc})", file=sys.stderr)
        return 1  # visible, never blocking
    if n < threshold:
        return 0
    print(REASON.format(n=n, threshold=threshold), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
