"""PreToolUse hook: validate append_event and checkpoint calls against the second-brain rules.

Exit 0 lets the call through. Exit 2 blocks it, and the message on stderr tells the model
exactly what to fix. Exit 1 reports a problem in the validator itself without blocking.

Hook-originated calls (the raw layer) never pass through PreToolUse, verified against Claude
Code 2.1.263, so everything that reaches this script was written by the model.
"""

import difflib
import re
import sqlite3
import sys
from contextlib import closing

from common import (
    PLUGIN_ROOT,
    RAW_KINDS,
    SYNTHESIS_KINDS,
    connect_readonly,
    db_path,
    read_hook_input,
)

TAGS_FILE = PLUGIN_ROOT / "references" / "tags.md"

TEMPLATES: dict[str, list[str]] = {
    "insight": ["Context", "Claim", "Why", "Rejected", "Open", "Source"],
    "decision": ["Context", "Options", "Rejected", "Decision", "Revisit when", "Source"],
    "reading": ["Source", "Claim", "Argument", "Fits", "Questions"],
    "open-question": ["Context", "Why it matters", "Would settle it", "Source"],
    "note": [],
}
CHECKPOINT_LABELS = ["Goal", "Done", "In progress", "Open", "Next"]
MAY_BE_NONE = {"Rejected", "Open", "Questions", "In progress"}
LINK_LABELS = {
    "Builds on": "builds-on",
    "Supersedes": "supersedes",
    "Corrects": "corrects",
    "Answers": "answers",
}
KNOWN_LABELS = (
    {label for labels in TEMPLATES.values() for label in labels}
    | set(CHECKPOINT_LABELS)
    | set(LINK_LABELS)
)
MAX_TAGS = 5
TAG_RE = re.compile(r"^#[a-z0-9]+(?:-[a-z0-9]+)*$")
SOURCE_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*$")
LINK_ID_RE = re.compile(r"^#(\d+)$")
BASE64_RE = re.compile(r"[A-Za-z0-9+/]{300,}={0,2}")
DISPLAY_MATH_RE = re.compile(r"\$\$.*?\$\$", re.DOTALL)
INLINE_MATH_RE = re.compile(r"\$[^$\n]+?\$")
MATH_SYMBOLS = frozenset(
    "∑∏∫√∞∂∇≤≥≠≈≡≅≃∝±×÷→←↔⇒⇐⇔↦∘∈∉∋⊂⊃⊆⊇∪∩∖∅∀∃∄∧∨¬⊕⊗ℝℕℤℚℂℙ𝔼ℓ"
    "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻ⁿ₀₁₂₃₄₅₆₇₈₉αβγδεζηθικλμνξπρστυφχψωΓΔΘΛΞΠΣΦΨΩ"
)


def load_tags(path=TAGS_FILE) -> tuple[set[str], dict[str, str]]:
    """Canonical tags and alias map from tags.md; lines read '#tag: definition (aliases: a, b)'."""
    canonical: set[str] = set()
    aliases: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return canonical, aliases
    for line in text.splitlines():
        match = re.match(r"^(#[a-z0-9-]+):\s*(.*)$", line.strip())
        if not match:
            continue
        tag, rest = match.groups()
        canonical.add(tag)
        alias_match = re.search(r"\(aliases?:\s*([^)]*)\)", rest)
        if alias_match:
            for alias in alias_match.group(1).split(","):
                alias = alias.strip().lstrip("#").lower()
                if alias:
                    aliases[alias] = tag
    return canonical, aliases


def strip_math(text: str) -> str:
    return INLINE_MATH_RE.sub(" ", DISPLAY_MATH_RE.sub(" ", text))


def math_outside_latex(text: str) -> str:
    found = sorted({ch for ch in strip_math(text) if ch in MATH_SYMBOLS})
    return "".join(found)


def split_sections(lines: list[str]) -> tuple[list[str], list[tuple[str, str]]]:
    """Title lines, then (label, value) sections; a section runs until the next known label."""
    title: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    for line in lines:
        match = re.match(r"^([A-Z][A-Za-z ]*?):(?:\s*(.*))?$", line)
        if match and match.group(1) in KNOWN_LABELS:
            sections.append((match.group(1), [match.group(2) or ""]))
        elif sections:
            sections[-1][1].append(line)
        else:
            title.append(line)
    return title, [(label, "\n".join(parts).strip()) for label, parts in sections]


def check_tags(lines: list[str], errors: list[str]) -> list[str]:
    """The final non-empty line must be the single 'tags:' line with 1-5 canonical tags."""
    tag_lines = [i for i, line in enumerate(lines) if line.startswith("tags:")]
    non_empty = [i for i, line in enumerate(lines) if line.strip()]
    if not tag_lines:
        errors.append("missing the final line 'tags: #a #b' (1 to 5 tags from references/tags.md)")
        return lines
    if len(tag_lines) > 1:
        errors.append("more than one 'tags:' line; keep exactly one, as the last line")
    if non_empty and tag_lines[-1] != non_empty[-1]:
        errors.append("the 'tags:' line must be the last line of the entry")
    tags = lines[tag_lines[-1]][5:].split()
    if not tags:
        errors.append("the 'tags:' line has no tags")
    if len(tags) > MAX_TAGS:
        errors.append(f"{len(tags)} tags; keep at most {MAX_TAGS}")
    canonical, aliases = load_tags()
    for tag in tags:
        if not TAG_RE.match(tag):
            errors.append(f"tag {tag!r} must look like #lower-case-words")
            continue
        if canonical and tag not in canonical:
            bare = tag[1:]
            hint = ""
            if bare in aliases:
                hint = f"; use {aliases[bare]}"
            else:
                close = difflib.get_close_matches(tag, sorted(canonical), n=3, cutoff=0.6)
                if close:
                    hint = "; did you mean " + ", ".join(close)
            errors.append(
                f"unknown tag {tag}{hint}. Add it to references/tags.md with a definition "
                "before using it"
            )
    return [line for i, line in enumerate(lines) if i not in tag_lines]


def check_template(kind: str, sections: list[tuple[str, str]], errors: list[str]) -> None:
    required = TEMPLATES[kind]
    present = [label for label, _ in sections]
    missing = [label for label in required if label not in present]
    if missing:
        errors.append(
            f"{kind} entries need the lines {', '.join(label + ':' for label in required)}; "
            f"missing {', '.join(label + ':' for label in missing)}"
        )
    order = [present.index(label) for label in required if label in present]
    if order != sorted(order):
        errors.append(f"template lines out of order; expected {', '.join(required)}")
    for label, value in sections:
        if label in LINK_LABELS or label == "Source":
            continue
        if label in required and not value:
            errors.append(f"'{label}:' is empty")
        elif label in required and value.lower() == "none" and label not in MAY_BE_NONE:
            errors.append(f"'{label}:' cannot be 'none'")


def check_links(sections: list[tuple[str, str]], conn, errors: list[str]) -> None:
    for label, value in sections:
        if label not in LINK_LABELS:
            continue
        tokens = value.split()
        if not tokens:
            errors.append(f"'{label}:' needs at least one event id such as #42")
        for token in tokens:
            match = LINK_ID_RE.match(token)
            if not match:
                errors.append(f"'{label}:' entries are event ids like #42, not {token!r}")
                continue
            if conn is None:
                continue
            row = conn.execute(
                "SELECT kind FROM memory_events WHERE id = ?", (int(match.group(1)),)
            ).fetchone()
            if row is None:
                errors.append(f"'{label}: {token}' points at an event that does not exist")
            elif row[0] in RAW_KINDS:
                errors.append(
                    f"'{label}: {token}' points at a raw {row[0]} event, not a curated entry"
                )


def check_source(sections: list[tuple[str, str]], conn, errors: list[str]) -> None:
    values = [value for label, value in sections if label == "Source"]
    if not values:
        return
    value = values[0]
    if not value:
        errors.append(
            "'Source:' is empty; give '<key> <locator>' entries separated by ';' or 'discussion'"
        )
        return
    if value.strip().lower() == "discussion":
        return
    table_exists = None
    for part in value.split(";"):
        part = part.strip()
        if not part:
            continue
        key = part.split()[0]
        if not SOURCE_KEY_RE.match(key):
            errors.append(f"source key {key!r} must be lower-case letters, digits, '.' or '-'")
            continue
        if conn is None:
            continue
        if table_exists is None:
            table_exists = bool(
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sources'"
                ).fetchone()
            )
        if not table_exists:
            errors.append("the sources table does not exist yet; run the second-brain setup first")
            return
        if conn.execute("SELECT 1 FROM sources WHERE key = ?", (key,)).fetchone() is None:
            errors.append(
                f"source {key!r} is not registered; INSERT it into sources with write_query first"
            )


def validate_event(kind: str, content: str, conn) -> list[str]:
    errors: list[str] = []
    if kind in RAW_KINDS:
        errors.append(
            f"kind {kind!r} is reserved for hook-written raw events; "
            f"use one of {', '.join(SYNTHESIS_KINDS)}"
        )
        return errors
    if kind not in SYNTHESIS_KINDS:
        errors.append(f"unknown kind {kind!r}; use one of {', '.join(SYNTHESIS_KINDS)}")
        return errors
    if BASE64_RE.search(content) or "data:image" in content:
        errors.append("embedded image data; transcribe it (LaTeX or a structured description)")
    symbols = math_outside_latex(content)
    if symbols:
        errors.append(f"math outside LaTeX: {symbols}; write formulas inside $...$ or $$...$$")
    lines = content.rstrip().split("\n")
    body = check_tags(lines, errors)
    title, sections = split_sections(body)
    title_lines = [line for line in title if line.strip()]
    if not title_lines:
        errors.append("the first line must be a one-line title")
    elif len(title_lines) > 1 and kind != "note":  # a note is free text after its title
        errors.append("the title must be a single line, followed directly by the template lines")
    elif len(title_lines[0]) > 120:
        errors.append("the title is longer than 120 characters")
    check_template(kind, sections, errors)
    check_links(sections, conn, errors)
    check_source(sections, conn, errors)
    return errors


def validate_checkpoint(summary: str, conn) -> list[str]:
    errors: list[str] = []
    symbols = math_outside_latex(summary)
    if symbols:
        errors.append(f"math outside LaTeX: {symbols}; write formulas inside $...$ or $$...$$")
    lines = summary.rstrip().split("\n")
    body = check_tags(lines, errors)
    _, sections = split_sections(body)
    present = [label for label, _ in sections]
    missing = [label for label in CHECKPOINT_LABELS if label not in present]
    if missing:
        errors.append(
            "checkpoint summaries need the lines "
            f"{', '.join(label + ':' for label in CHECKPOINT_LABELS)}; "
            f"missing {', '.join(label + ':' for label in missing)}"
        )
    order = [present.index(label) for label in CHECKPOINT_LABELS if label in present]
    if order != sorted(order):
        errors.append(f"checkpoint lines out of order; expected {', '.join(CHECKPOINT_LABELS)}")
    for label, value in sections:
        if label in ("Goal", "Next") and not value:
            errors.append(f"'{label}:' is empty")
    check_links(sections, conn, errors)
    return errors


def main() -> int:
    data = read_hook_input()
    tool = str(data.get("tool_name") or "")
    tool_input = data.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0
    path = db_path()
    conn = None
    try:
        if path is not None and path.is_file():
            conn = connect_readonly(path)
        with closing(conn) if conn is not None else closing(sqlite3.connect(":memory:")):
            if tool.endswith("__checkpoint"):
                errors = validate_checkpoint(str(tool_input.get("summary") or ""), conn)
            elif tool.endswith("__append_event"):
                errors = validate_event(
                    str(tool_input.get("kind") or "note"),
                    str(tool_input.get("content") or ""),
                    conn,
                )
            else:
                return 0
    except sqlite3.Error as exc:
        print(f"second-brain validator: database error ({exc}); entry not checked", file=sys.stderr)
        return 1
    if not errors:
        return 0
    what = "checkpoint" if tool.endswith("__checkpoint") else "entry"
    print(f"second-brain refused this {what}:", file=sys.stderr)
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    print("Fix every point above and call the tool again with the corrected text.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # a validator bug must never lock the memory
        print(
            f"second-brain validator crashed ({type(exc).__name__}: {exc}); entry not checked",
            file=sys.stderr,
        )
        sys.exit(1)
