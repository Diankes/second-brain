# second-brain

A Claude Code plugin that turns the [mcp-sqlite-memory](https://github.com/Diankes/mcp-sqlite-memory)
server into a second brain for long-running work: reading papers, books and other sources,
working through ideas, and keeping the reasoning recoverable over many sessions and many
months. It is policy on top of the server's tools, plus hooks that make the important parts
happen whether or not the model feels like it. The shipped tag vocabulary leans towards
math-heavy study; the mechanism does not care what the domain is.

**Just want to use this day to day?** Start with [the quickstart](references/quickstart.md) —
everything below here is the technical reference underneath it.

Two layers, kept apart on purpose:

- **Raw layer, hook-driven, always happens.** Every prompt, every response, every context
  compaction and every session end is written to the memory log by a hook calling
  `append_event` on the running server, and a snapshot of the database file is taken at
  compaction and session end. No model judgment and no model tokens are involved: the harness
  calls the tools directly.
- **Curated layer, model-written, format-enforced.** Insights, decisions, readings, open
  questions and checkpoints are written by the model from templates, with LaTeX-only math, a
  controlled tag vocabulary, registered sources and explicit links. A hook validates every one
  before it is written and refuses violations with the exact reason. Another hook refuses to end
  a turn once too many prompts have gone by without a curated entry.

The goal is that an entry read six months later ramps you back up on what was thought and why,
the way revisiting an old codebase does.

## What the hooks do

| Event | Type | Effect |
|---|---|---|
| `UserPromptSubmit` | `mcp_tool` | `append_event(kind="prompt", content=<the prompt>)` |
| `PreCompact` | `mcp_tool` | `append_event(kind="compaction", ...)` with trigger and session id |
| `PreCompact` | `mcp_tool` | `snapshot(reason="compaction: <trigger>")`: a database snapshot before the context is compacted |
| `SessionEnd` | `mcp_tool` | `append_event(kind="session-end", ...)` with the reason |
| `SessionEnd` | `mcp_tool` | `snapshot(reason="session-end: <reason>")`: a database snapshot as the session closes |
| `SessionStart` (compact) | `mcp_tool` | `get_resume_context(max_events=40, exclude_kinds="prompt,compaction,session-end,response")` injected into context after compaction |
| `SessionStart` (all) | command | injects `references/core-rules.md` plus the database path and cadence |
| `Stop` | command | `scripts/cadence.py`: blocks the turn once when prompts since the last curated entry reach the threshold |
| `Stop` | `mcp_tool` | `append_event(kind="response", content=<last_assistant_message>)`: the model's own reply, verbatim |
| `PreToolUse` on `append_event` and `checkpoint` | command | `scripts/validate_entry.py`: template, tags, math, links, sources, no images |

Hooks call `append_event` on the same server process the model uses, so every raw event is
hashed and chained by the server and lands in `query_log` like any other call. Hooks never write
checkpoints: `get_resume_context` shows the latest checkpoint as the state summary, and a
mechanical one would hide the real one.

The raw `response` events are the model's verbatim replies. They exist so the record is
complete; the curated layer stays a deliberate, sparse distillation and is not a substitute
for them. The `synthesis` view and the resume call exclude `response` along with the other raw
kinds, so nothing downstream gets noisier.

**Upgrading an existing database** to this version of the plugin: the `synthesis` view stored
in the database still excludes only the three older raw kinds. Run once, through the server:

```
create_view(name="synthesis",
            select_sql="SELECT id, ts, session, kind, content FROM memory_events WHERE kind NOT IN ('prompt', 'compaction', 'session-end', 'response')",
            description="curated entries only (insight, decision, reading, open-question, note); hook-written raw events are excluded",
            replace=true)
```

The other views build on `synthesis`, so nothing else changes.

## What the validator enforces

1. Math is LaTeX. Unicode math symbols outside `$...$` or `$$...$$` are refused.
2. Kind is one of `insight`, `decision`, `reading`, `open-question`, `note`. The raw kinds are
   reserved for hooks.
3. Exactly one `tags:` line, last, with one to five tags from `references/tags.md`. Unknown tags
   are refused with the closest existing tags; aliases map to their canonical tag.
4. The template for the kind: a one-line title, then the labelled lines in order, non-empty
   unless the template allows `none`. Templates are in `references/templates.md`.
5. `Builds on:`, `Supersedes:`, `Corrects:`, `Answers:` reference existing curated entries.
6. `Source:` keys exist in the `sources` table, or the value is `discussion`.
7. No embedded image data. Transcribe; if the original matters, the user saves the file and the
   entry cites its path.

Checkpoint summaries follow `Goal:`, `Done:`, `In progress:`, `Open:`, `Next:`, `tags:`.

## The tag vocabulary is yours to edit

`references/tags.md` ships as a starter set for math-heavy academic work: a "Subjects" section
of topic tags, an "Objects and moves" section (definition, theorem, proof technique,
counterexample, computation, pitfall) and a "Work and process" section. Before the first real
session, replace the subject tags with the ones your own domain needs and keep the other two
sections and the mechanism: one tag per line as `#tag: definition (aliases: a, b)`, hyphenated
lower-case names, aliases for the spellings you tend to reach for. The validator reads the file
on every call, so a tag exists the moment its line does, and never before. That is what keeps
recall working months later: no `#eigen` next to `#eigenvalues` next to `#linalg`.

## Views

Setup creates a `sources` table and nine views through `create_view`, so they carry
descriptions in `get_schema`: `synthesis` (curated entries only), `event_lines`, `event_tags`,
`event_links`, `event_sources` (all parsed from the entry text with recursive CTEs),
`current_synthesis` (superseded entries hidden), `open_questions`, `readings`, `topics`. Links
and sources therefore need no schema change in the server: the conventions are validated on the
way in and parsed on the way out. At 6,000 events the topic index takes about 20 ms and the
"what did I learn about X and from where" join about 90 ms.

## Install

Requires the server at v0.3.0 or later (the `snapshot` tool), [uv](https://docs.astral.sh/uv/)
and ripgrep.

1. Use one folder for the work as the Claude Code project, for example `F:\study`. The
   plugin is project-scoped on purpose: personal hooks would fire in every coding project too.
2. Clone the plugin into that project's skills directory. Any folder there with a
   `.claude-plugin/plugin.json` loads as a plugin the next session, once the folder is trusted:

   ```
   git clone https://github.com/Diankes/second-brain F:\study\.claude\skills\second-brain
   ```

3. Put the database path and the cadence in the project's `.claude/settings.json`. The hook
   scripts read both from the environment:

   ```json
   {
     "env": {
       "MCP_SQLITE_DB": "F:\\study\\memory.db",
       "SECOND_BRAIN_CADENCE": "6"
     },
     "permissions": {
       "allow": [
         "mcp__sqlite-memory__read_query",
         "mcp__sqlite-memory__write_query",
         "mcp__sqlite-memory__list_tables",
         "mcp__sqlite-memory__describe_table",
         "mcp__sqlite-memory__get_schema",
         "mcp__sqlite-memory__create_view",
         "mcp__sqlite-memory__append_event",
         "mcp__sqlite-memory__snapshot",
         "mcp__sqlite-memory__verify_chain",
         "mcp__sqlite-memory__checkpoint",
         "mcp__sqlite-memory__get_resume_context",
         "mcp__sqlite-memory__search_text"
       ],
       "ask": ["mcp__sqlite-memory__destructive_query"]
     }
   }
   ```

4. Register the server for the project with the same path and the read caps raised for
   long-form notes:

   ```
   claude mcp add sqlite-memory --scope local -- uvx --from git+https://github.com/Diankes/mcp-sqlite-memory@v0.3.0 mcp-sqlite-memory --db F:\study\memory.db --max-cell-chars 8000 --max-result-bytes 131072
   ```

   The server name must be `sqlite-memory`: the hooks address it by that name.

5. Start a session in the project and run `/second-brain:memory setup` once. It creates the
   `sources` table and the views. If the hooks are not listed under `/hooks`, run
   `/reload-plugins`.

6. Check: after your first prompt, `read_query("SELECT id, kind FROM memory_events")` shows a
   `prompt` row you did not write.

## Configuration

| Variable | Read by | Default |
|---|---|---|
| `MCP_SQLITE_DB` | validator, cadence, rules injection | required; set it in `.claude/settings.json` |
| `SECOND_BRAIN_CADENCE` | cadence | 6 prompts; 0 disables the Stop-hook check |

Dense derivation sessions may want a higher threshold and quick back-and-forth a lower one;
change the setting, no code involved.

## Verified behaviour

Tested against Claude Code 2.1.263 and 2.1.270 on Windows with throwaway `claude -p` sessions:

- `mcp_tool` hooks write through the running server: the prompt and session-end events landed
  in `memory_events` and in `query_log`.
- Hook-originated tool calls do not pass through `PreToolUse` or `PostToolUse`. Loggers
  registered with no matcher saw nothing. So the validator only ever sees model-written entries,
  and it refuses the raw kinds outright.
- `stop_hook_active` is `false` on the first Stop and `true` after a block; `cadence.py` exits 0
  when it is true, so it never blocks twice in a row. Claude Code adds a cap of eight consecutive
  blocks on top.
- The server's own `session` id is per server process, and a hook can run against a freshly
  spawned server (the SessionEnd hook did). Group a session by its raw `prompt` and
  `session-end` markers and time order, not by that column.
- The whole loop, with the plugin loaded through `--plugin-dir` and the cadence set to 1: the
  SessionStart digest was injected and followed (the model called `get_resume_context` first),
  the prompt event was written by the hook, the Stop hook blocked once, the model answered it
  with a checkpoint in the exact template and a canonical tag, the validator passed it, and the
  session ended without looping. `env` values from settings reached the hook scripts.
- `Stop` fires more than once per visible turn when `cadence.py` blocks. With the cadence at 1
  and the prompt "Reply with exactly the word hello.", the log read: `prompt` (hook),
  `get_resume_context` (model, per the injected rules), `response` (first Stop, blocked),
  `checkpoint` (model, after one refusal by the validator), `response` (second Stop, allowed),
  `session-end` and `snapshot` (SessionEnd hooks). Two `response` events for one visible turn
  is correct: both are genuine final assistant text. In that run both were "hello", because
  the checkpoint is a tool call with no assistant text and the model then repeated its one-word
  answer; a chattier model would leave two different texts. The snapshot file appeared in
  `<db>.snapshots/` with the reason `session-end: other` in `query_log`.

Known limit: `mcp_tool` hooks cannot run at `SessionStart` on a fresh start, so the first
resume of a session depends on the model following the injected rules. After compaction the
reload is hook-driven.

## Development

```
uv sync --all-groups
uv run pytest
uv run ruff check scripts tests
```

The dev group installs the server from a release tag, so `tests/test_views.py` bootstraps the
views through the real `create_view` policy, and the validator and cadence tests run the hook
scripts as subprocesses with the JSON Claude Code would send.

## Files

```
.claude-plugin/plugin.json     plugin manifest
hooks/hooks.json               the hooks above
SKILL.md                       the policy the model loads (/second-brain:memory)
references/core-rules.md       digest injected at every session start
references/templates.md        entry and checkpoint templates
references/tags.md             canonical tag vocabulary
references/views.sql           sources table and the nine views
references/resume-playbook.md  queries for resuming a topic
references/quickstart.md       the plain-language day-to-day guide
scripts/                       validate_entry.py, cadence.py, inject_rules.py, common.py
tests/                         validator, cadence, views, file consistency
```

## License

MIT, see `LICENSE`.
