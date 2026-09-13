"""The plugin's static files agree with the scripts that enforce them."""

import json
import re

import validate_entry as v
from helpers import ROOT, run_script

LABEL_RE = re.compile(r"^([A-Z][A-Za-z ]*?):")


def labels_in_templates() -> dict[str, list[str]]:
    """Kind -> labelled lines inside the fenced block under each '## kind' heading."""
    text = (ROOT / "references" / "templates.md").read_text(encoding="utf-8")
    result: dict[str, list[str]] = {}
    kind = None
    in_block = False
    for line in text.splitlines():
        if line.startswith("## "):
            heading = re.match(r"^## ([a-z-]+)$", line)
            kind = heading.group(1) if heading else None  # "## Worked example" ends a section
            if kind:
                result[kind] = []
            continue
        if line.startswith("```"):
            in_block = not in_block
            continue
        if in_block and kind:
            match = LABEL_RE.match(line)
            if match and match.group(1) not in v.LINK_LABELS:
                result[kind].append(match.group(1))
    return result


def test_templates_match_the_validator():
    found = labels_in_templates()
    for kind, labels in v.TEMPLATES.items():
        assert found[kind] == labels, kind
    assert found["checkpoint"] == v.CHECKPOINT_LABELS


def test_tag_vocabulary_parses_and_is_well_formed():
    canonical, aliases = v.load_tags()
    assert len(canonical) >= 20
    assert all(v.TAG_RE.match(tag) for tag in canonical)
    assert aliases["linalg"] == "#linear-algebra"
    assert not (set(aliases) & {tag[1:] for tag in canonical}), "an alias duplicates a tag"


def test_hooks_json_points_at_existing_scripts_and_real_tools():
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    assert set(hooks) == {
        "UserPromptSubmit",
        "PreCompact",
        "SessionEnd",
        "SessionStart",
        "Stop",
        "PreToolUse",
    }
    for groups in hooks.values():
        for group in groups:
            for hook in group["hooks"]:
                if hook["type"] == "command":
                    script = hook["args"][-1]
                    assert script.startswith("${CLAUDE_PLUGIN_ROOT}/scripts/"), script
                    assert (ROOT / "scripts" / script.rsplit("/", 1)[-1]).is_file(), script
                    assert hook["command"] == "uv" and hook["args"][:4] == [
                        "run",
                        "--no-project",
                        "--python",
                        "3.12",
                    ]
                else:
                    assert hook["type"] == "mcp_tool" and hook["server"] == "sqlite-memory"
                    assert hook["tool"] in {"append_event", "get_resume_context", "snapshot"}
                    if hook["tool"] == "append_event":
                        assert hook["input"]["kind"] in v.RAW_KINDS
                    if hook["tool"] == "get_resume_context":
                        excluded = set(hook["input"]["exclude_kinds"].split(","))
                        assert excluded == set(v.RAW_KINDS)
    stop_tools = [h["type"] for h in hooks["Stop"][0]["hooks"]]
    assert stop_tools == ["command", "mcp_tool"]  # cadence check plus response capture
    for event in ("PreCompact", "SessionEnd"):
        tools = [h["tool"] for h in hooks[event][0]["hooks"]]
        assert tools == ["append_event", "snapshot"], event
    pre = hooks["PreToolUse"][0]
    assert pre["matcher"] == "mcp__sqlite-memory__append_event|mcp__sqlite-memory__checkpoint"


def test_inject_rules_emits_the_digest(db):
    result = run_script("inject_rules.py", {"hook_event_name": "SessionStart", "source": "startup"})
    assert result.returncode == 0
    payload = json.loads(result.stdout)["hookSpecificOutput"]
    assert payload["hookEventName"] == "SessionStart"
    context = payload["additionalContext"]
    assert "Hard rules" in context and "get_resume_context" in context
    assert str(db.path) in context and "Checkpoint cadence: 6 prompts" in context
    unset = run_script("inject_rules.py", {}, env={"MCP_SQLITE_DB": ""})
    assert (
        "MCP_SQLITE_DB is not set"
        in json.loads(unset.stdout)["hookSpecificOutput"]["additionalContext"]
    )
