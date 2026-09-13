"""SessionStart hook: put the core rules in front of the model before the first prompt.

This is the part of the quality floor that does not wait for the model to load the skill.
The full policy, templates and tag list stay in the skill and load on demand.
"""

import sys

from common import DB_ENV, PLUGIN_ROOT, cadence_threshold, db_path, emit, read_hook_input

RULES_FILE = PLUGIN_ROOT / "references" / "core-rules.md"


def main() -> int:
    read_hook_input()  # drain stdin; nothing in it changes the rules
    try:
        rules = RULES_FILE.read_text(encoding="utf-8").strip()
    except OSError as exc:
        print(f"second-brain: cannot read {RULES_FILE}: {exc}", file=sys.stderr)
        return 1
    path = db_path()
    if path is None:
        status = (
            f"{DB_ENV} is not set: hooks cannot find the memory database; "
            "set it in .claude/settings.json under env"
        )
    elif not path.is_file():
        status = (
            f"memory database {path} does not exist yet; "
            "it is created when the sqlite-memory server starts"
        )
    else:
        status = f"memory database: {path}"
    context = f"{rules}\n\n{status}. Checkpoint cadence: {cadence_threshold()} prompts."
    emit({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}})
    return 0


if __name__ == "__main__":
    sys.exit(main())
