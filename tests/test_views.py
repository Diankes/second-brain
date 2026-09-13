"""views.sql through the real server: every block passes the policy, and the views parse."""

import pytest
from helpers import VALID_DECISION, VALID_INSIGHT, parse_views_sql, text

pytestmark = pytest.mark.anyio

EXPECTED_VIEWS = [
    "synthesis",
    "event_lines",
    "event_tags",
    "event_links",
    "event_sources",
    "current_synthesis",
    "open_questions",
    "readings",
    "topics",
]


async def bootstrap(client):
    for block in parse_views_sql():
        if block["kind"] == "table":
            result = await client.call_tool("write_query", {"query": block["sql"]})
        else:
            result = await client.call_tool(
                "create_view",
                {
                    "name": block["name"],
                    "select_sql": block["sql"],
                    "description": block["description"],
                },
            )
        assert not result.is_error, f"{block['name']}: {text(result)}"


async def test_bootstrap_creates_table_and_views(client):
    blocks = parse_views_sql()
    assert [b["name"] for b in blocks if b["kind"] == "view"] == EXPECTED_VIEWS
    assert all(b["description"] for b in blocks if b["kind"] == "view")
    await bootstrap(client)
    schema = text(await client.call_tool("get_schema", {}))
    assert "CREATE TABLE sources" in schema
    for name in EXPECTED_VIEWS:
        assert f'CREATE VIEW "{name}"' in schema
    again = await client.call_tool("create_view", {"name": "topics", "select_sql": "SELECT 1"})
    assert again.is_error and "replace=true" in text(again)


async def test_views_parse_tags_links_and_sources(client, memory, db):
    await bootstrap(client)
    with db.internal() as conn:
        conn.execute(
            "INSERT INTO sources(key, kind, title, added) VALUES "
            "('strang-la', 'textbook', 'Introduction to Linear Algebra', '2026-09-13')"
        )
    memory.append("raw prompt with tags: #linear-algebra in the middle", "prompt")  # id 1
    memory.append(VALID_INSIGHT, "insight")  # id 2
    memory.append(VALID_DECISION.replace("tags:", "Builds on: #2\ntags:"), "decision")  # id 3
    memory.append(
        "Does it hold for compact operators?\nContext: from #2\nWhy it matters: thesis chapter 2\n"
        "Would settle it: a proof or a counterexample in $\\ell^2$\nSource: discussion\n"
        "tags: #functional-analysis #spectral-theorem",
        "open-question",
    )  # id 4
    memory.append(
        "Yes, with the same argument\nContext: answering #4\n"
        "Claim: the max-min holds on $\\ell^2$\n"
        "Why: compactness gives an orthonormal eigenbasis\nRejected: none\nOpen: none\n"
        "Source: strang-la §6.4; strang-la p.12\nAnswers: #4\nSupersedes: #2\n"
        "tags: #functional-analysis #spectral-theorem",
        "insight",
    )  # id 5
    memory.append("the assistant's own reply\ntags: #optimization", "response")  # id 6, raw

    topics = text(
        await client.call_tool(
            "read_query", {"query": "SELECT tag, entries, latest_id FROM topics ORDER BY tag"}
        )
    )
    assert "#spectral-theorem,4,5" in topics and "#linear-algebra,1,2" in topics
    assert "middle" not in topics  # the raw prompt is not parsed
    assert "#optimization" not in topics  # neither is the raw response
    links = text(
        await client.call_tool(
            "read_query",
            {"query": "SELECT from_id, rel, to_id FROM event_links ORDER BY from_id, rel"},
        )
    )
    assert links.splitlines()[1:-1] == ["3,builds-on,2", "5,answers,4", "5,supersedes,2"]
    sources = text(
        await client.call_tool(
            "read_query",
            {
                "query": "SELECT event_id, source_key, locator FROM event_sources "
                "ORDER BY event_id, locator"
            },
        )
    )
    assert (
        "2,strang-la,§6.4" in sources
        and "5,strang-la,p.12" in sources
        and "5,strang-la,§6.4" in sources
    )
    assert "discussion" not in sources
    current = text(
        await client.call_tool(
            "read_query", {"query": "SELECT id FROM current_synthesis ORDER BY id"}
        )
    )
    assert current.splitlines()[1:-1] == ["3", "4", "5"]  # 2 is superseded, 1 is raw
    open_questions = text(
        await client.call_tool("read_query", {"query": "SELECT id FROM open_questions"})
    )
    assert open_questions.splitlines()[1:-1] == []  # 4 was answered by 5
    learned = text(
        await client.call_tool(
            "read_query",
            {
                "query": (
                    "SELECT s.title, count(*) FROM event_tags t "
                    "JOIN event_sources es ON es.event_id = t.id "
                    "JOIN sources s ON s.key = es.source_key "
                    "WHERE t.tag = '#spectral-theorem' GROUP BY s.title"
                )
            },
        )
    )
    assert "Introduction to Linear Algebra,3" in learned
