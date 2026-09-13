"""The quality floor: what the validator refuses and what it lets through."""

from contextlib import closing

import pytest
import validate_entry as v
from common import connect_readonly
from helpers import (
    VALID_CHECKPOINT,
    VALID_DECISION,
    VALID_INSIGHT,
    hook_input,
    register_source,
    run_script,
)


@pytest.fixture
def conn(db):
    register_source(db)
    with closing(connect_readonly(db.path)) as c:
        yield c


def errors_for(conn, content, kind="insight"):
    return v.validate_event(kind, content, conn)


def test_valid_entries_pass(conn):
    assert errors_for(conn, VALID_INSIGHT) == []
    assert errors_for(conn, VALID_DECISION, kind="decision") == []
    assert v.validate_checkpoint(VALID_CHECKPOINT, conn) == []


def test_note_needs_only_a_title_and_tags(conn):
    assert (
        errors_for(conn, "A stray remark\nwith a second line\ntags: #methodology", kind="note")
        == []
    )


def test_raw_and_unknown_kinds_are_refused(conn):
    assert (
        "reserved for hook-written raw events" in errors_for(conn, VALID_INSIGHT, kind="prompt")[0]
    )
    assert "unknown kind" in errors_for(conn, VALID_INSIGHT, kind="thought")[0]


def test_unicode_math_outside_latex_is_refused(conn):
    bad = VALID_INSIGHT.replace("Why: orthonormal", "Why: λ_k ≥ 0 because orthonormal")
    [error] = errors_for(conn, bad)
    assert error.startswith("math outside LaTeX: ") and "λ" in error and "≥" in error
    inside = VALID_INSIGHT.replace("Why: orthonormal", "Why: $λ_k ≥ 0$ so orthonormal")
    assert errors_for(conn, inside) == []


def test_tags_are_checked_against_the_vocabulary(conn):
    alias = VALID_INSIGHT.replace("#linear-algebra", "#linalg")
    [error] = errors_for(conn, alias)
    assert "unknown tag #linalg; use #linear-algebra" in error
    typo = VALID_INSIGHT.replace("#spectral-theorem", "#spectral-theorm")
    [error] = errors_for(conn, typo)
    assert "did you mean #spectral-theorem" in error
    malformed = VALID_INSIGHT.replace("#spectral-theorem", "#Spectral_Theorem")
    assert any("must look like #lower-case-words" in e for e in errors_for(conn, malformed))
    too_many = VALID_INSIGHT + " #topology #algebra #probability #statistics"
    assert any("keep at most 5" in e for e in errors_for(conn, too_many))


def test_tags_line_must_be_single_and_last(conn):
    missing = VALID_INSIGHT.rsplit("\n", 1)[0]
    assert any("missing the final line" in e for e in errors_for(conn, missing))
    not_last = VALID_INSIGHT + "\ntrailing remark"
    assert any("must be the last line" in e for e in errors_for(conn, not_last))
    twice = VALID_INSIGHT.replace("Open: the compact", "tags: #algebra\nOpen: the compact")
    assert any("more than one" in e for e in errors_for(conn, twice))


def test_template_lines_are_required_in_order(conn):
    missing = VALID_INSIGHT.replace(
        "Why: orthonormal eigenbasis plus a dimension count on the two subspaces\n", ""
    )
    assert any("missing Why:" in e for e in errors_for(conn, missing))
    swapped = VALID_INSIGHT.replace(
        "Context: comparing two proofs of Courant-Fischer for the seminar\nClaim:",
        "Claim:",
    ).replace("Why: orthonormal", "Context: comparing two proofs\nWhy: orthonormal")
    assert any("out of order" in e for e in errors_for(conn, swapped))
    empty = VALID_INSIGHT.replace(
        "Why: orthonormal eigenbasis plus a dimension count on the two subspaces", "Why:"
    )
    assert any("'Why:' is empty" in e for e in errors_for(conn, empty))
    none = VALID_INSIGHT.replace(
        "Why: orthonormal eigenbasis plus a dimension count on the two subspaces", "Why: none"
    )
    assert any("cannot be 'none'" in e for e in errors_for(conn, none))


def test_title_rules(conn):
    no_title = "\n".join(VALID_INSIGHT.split("\n")[1:])
    assert any("one-line title" in e for e in errors_for(conn, no_title))
    two_titles = "first\nsecond\n" + "\n".join(VALID_INSIGHT.split("\n")[1:])
    assert any("single line" in e for e in errors_for(conn, two_titles))


def test_links_must_point_at_existing_curated_entries(conn, memory):
    dangling = VALID_INSIGHT.replace("tags:", "Builds on: #99\ntags:")
    assert any("does not exist" in e for e in errors_for(conn, dangling))
    memory.append("a raw prompt", "prompt")
    memory.append(VALID_DECISION, "decision")
    raw = VALID_INSIGHT.replace("tags:", "Builds on: #1\ntags:")
    assert any("raw prompt event" in e for e in errors_for(conn, raw))
    good = VALID_INSIGHT.replace("tags:", "Builds on: #2\nSupersedes: #2\ntags:")
    assert errors_for(conn, good) == []
    junk = VALID_INSIGHT.replace("tags:", "Builds on: entry two\ntags:")
    assert any("event ids like #42" in e for e in errors_for(conn, junk))


def test_sources_must_be_registered(conn):
    unknown = VALID_INSIGHT.replace("Source: strang-la §6.4", "Source: nobody2020 p.3")
    [error] = errors_for(conn, unknown)
    assert "not registered" in error and "nobody2020" in error
    bad_key = VALID_INSIGHT.replace("Source: strang-la §6.4", "Source: Strang_LA §6.4")
    assert any("source key" in e for e in errors_for(conn, bad_key))
    two = VALID_INSIGHT.replace("Source: strang-la §6.4", "Source: strang-la §6.4; strang-la p.12")
    assert errors_for(conn, two) == []
    discussion = VALID_INSIGHT.replace("Source: strang-la §6.4", "Source: discussion")
    assert errors_for(conn, discussion) == []


def test_sources_table_missing_is_reported(db):
    with closing(connect_readonly(db.path)) as fresh:
        [error] = v.validate_event("insight", VALID_INSIGHT, fresh)
    assert "sources table does not exist" in error


def test_embedded_images_are_refused(conn):
    blob = VALID_INSIGHT.replace("Open: the compact", "Open: " + "QUJD" * 100 + "\nthe compact")
    assert any("embedded image data" in e for e in errors_for(conn, blob))


def test_checkpoint_rules(conn):
    no_next = VALID_CHECKPOINT.replace(
        "Next: finish the figure, then rehearse the dimension-count step\n", ""
    )
    assert any("missing Next:" in e for e in v.validate_checkpoint(no_next, conn))
    no_tags = VALID_CHECKPOINT.rsplit("\n", 1)[0]
    assert any("missing the final line" in e for e in v.validate_checkpoint(no_tags, conn))


def test_validator_without_a_database_still_checks_format():
    assert v.validate_event("insight", VALID_INSIGHT, None) == []
    assert any("unknown kind" in e for e in v.validate_event("x", VALID_INSIGHT, None))


def test_exit_codes_as_claude_code_sees_them(db):
    register_source(db)
    ok = run_script(
        "validate_entry.py", hook_input("append_event", kind="insight", content=VALID_INSIGHT)
    )
    assert ok.returncode == 0 and ok.stdout == ""
    refused = run_script(
        "validate_entry.py",
        hook_input(
            "append_event",
            kind="insight",
            content=VALID_INSIGHT.replace("#linear-algebra", "#linalg"),
        ),
    )
    assert refused.returncode == 2
    assert "second-brain refused this entry:" in refused.stderr
    assert "- unknown tag #linalg; use #linear-algebra" in refused.stderr
    checkpoint = run_script("validate_entry.py", hook_input("checkpoint", summary="Goal: x"))
    assert checkpoint.returncode == 2 and "refused this checkpoint" in checkpoint.stderr
    other = run_script("validate_entry.py", hook_input("read_query", query="SELECT 1"))
    assert other.returncode == 0
    no_env = run_script(
        "validate_entry.py",
        hook_input("append_event", kind="insight", content=VALID_INSIGHT),
        env={"MCP_SQLITE_DB": ""},
    )
    assert no_env.returncode == 0
