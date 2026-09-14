---
name: memory
description: "How to record and recall work with the sqlite-memory server across many sessions and months, for reading papers, books and other sources, and working through ideas. Use when something is worth remembering, when resuming a topic from an earlier session, when writing a checkpoint, when the memory validator refuses an entry, or to set up a new memory database (setup)."
argument-hint: "[setup | resume #tag | source <key>]"
---

# second-brain

The sqlite-memory server is a second brain: an append-only, hash-chained event log with
checkpoints, an audit log, and views that turn conventions in the text into SQL. This skill is
the policy for using it so that an entry read months from now ramps you back up on what was
thought and why. Hooks enforce the timing (raw capture, cadence, validation); this file tells
you what to write and how to find it again.

Tool contracts, exactly as the server exposes them:

- `append_event(content, kind="note")`: one curated entry; the server hashes and chains it.
- `checkpoint(summary)`: a state summary anchored to the chain head.
- `get_resume_context(max_events=50, exclude_kinds="")`: latest checkpoint, events since it, chain status.
- `read_query(query, limit=100)`: one SELECT; CSV back, `# N rows` trailer.
- `write_query(query)`: INSERT, UPDATE, CREATE TABLE; never DELETE.
- `create_view(name, select_sql, description="", replace=false)`: a saved query with its purpose.
- `search_text(pattern, table, columns=null, where=null, key_column=null, limit=100, ignore_case=false, fixed_strings=false, context_chars=80)`: SQL filter, then ripgrep.
- `verify_chain()`, `list_tables()`, `describe_table(table)`, `get_schema(include_system=false)`.

## Two layers

| Layer | Kinds | Who writes | When |
|---|---|---|---|
| raw | `prompt`, `response`, `compaction`, `session-end` | hooks, automatically | every prompt, every response, compaction, session end |
| curated | `insight`, `decision`, `reading`, `open-question`, `note`, plus checkpoints | you, by template | judgment calls, with a cadence floor |

The raw layer is the record; never write those kinds yourself (the validator refuses). The
curated layer is the index; keep it worth reading. Not everything deserves an entry: a curated
entry captures a conclusion and the reasoning behind it, an open thread, or what a source
established. Chit-chat, restatements of the prompt and intermediate scratch work do not.

## At the start of a session

If the context already contains a resume block (the SessionStart hook injects one after
compaction), continue from it. Otherwise call
`get_resume_context(max_events=40, exclude_kinds="prompt,compaction,session-end,response")`
first and read the checkpoint before doing anything else. If it reports `chain BROKEN`, tell the user
before writing anything.

## Writing a curated entry

1. Pick the kind: `insight` (something now understood), `decision` (a choice with alternatives),
   `reading` (what a source establishes), `open-question` (a thread that needs settling),
   `note` (rare, when nothing else fits).
2. If it cites a source, make sure the key is registered:
   `read_query("SELECT key FROM sources WHERE key = 'strang-la'")`. If not, register it first
   (see Sources).
3. Write the content from the template for that kind in
   [references/templates.md](references/templates.md): one title line, the labelled lines in
   order, optional link lines, then the final `tags:` line. Values may span lines, so display
   math fits under `Claim:` or `Why:`.
4. Choose one to five tags from [references/tags.md](references/tags.md). To use a tag that is
   not there, add a line `#tag: definition (aliases: ...)` to that file first, with the Edit tool,
   then use it. Prefer widening an existing tag over creating a near-duplicate.
5. Call `append_event(content=..., kind=...)`. The reply gives the event id; use it in later
   `Builds on:` lines.

If the validator refuses the call, its message lists every problem. Fix the text and call
again. Do not change the kind to `note` to get past a template check, do not drop a tag to get
past the vocabulary check, and do not paraphrase a formula to get past the math check.

## Checkpoints

Write `checkpoint(summary)` at a milestone, before the context gets long, and whenever the Stop
hook asks (it blocks the turn once when too many prompts have passed without a curated entry).
The summary follows the checkpoint template: `Goal:`, `Done:` (with event ids), `In progress:`,
`Open:`, `Next:` (the first concrete step when resuming), then `tags:`. A good `Next:` line is
what makes the next session start fast.

## Math and images

Math is LaTeX, always: inline `$...$`, display `$$...$$`. Never paraphrase a formula in words
and never use Unicode math symbols outside LaTeX; the validator refuses both. Photographed
equations get transcribed into LaTeX. Diagrams get a structured description: what the axes or
nodes are, what the arrows mean, what the figure is evidence for. Nothing is stored as an
image: the server is CSV-first and you cannot write pasted image bytes to disk. If the original
matters, ask the user to save the file under the project's `attachments/` folder and cite its
path in `Context:` or `Source:`.

## Sources

`sources` is a plain table created by setup: `key, kind, title, authors, year, locator, added,
notes`. Keys are short and stable: `cooper2020` for a paper, `strang-la` for a textbook,
`mit-18.06` for a course. Register with

```sql
INSERT INTO sources(key, kind, title, authors, year, locator, added)
VALUES ('strang-la', 'textbook', 'Introduction to Linear Algebra', 'Gilbert Strang', 2016, '5th ed.', '2026-09-13')
```

through `write_query`. Entries cite `Source: strang-la §6.4; mit-18.06 lec24 12:30`, several
separated by `;`, each a key followed by a locator (section, page, timestamp, theorem number),
or `Source: discussion` when the entry came from our own work. The `event_sources` view parses
these lines, so "what did I learn about X and from where" is a join, never a memory exercise.

## Links

Four optional lines, placed just before `tags:`, each holding event ids like `#42 #57`:

- `Builds on:` this entry extends those.
- `Supersedes:` this entry replaces those; they drop out of `current_synthesis` but stay in
  `synthesis` and in the chain.
- `Corrects:` those were wrong in a way this entry fixes.
- `Answers:` closes those open questions.

The validator checks the ids exist and are curated entries. To relate two old entries after the
fact, write a short `note` carrying the link line.

## Resuming a topic

Follow [references/resume-playbook.md](references/resume-playbook.md): `topics` for the index,
`current_synthesis` joined with `event_tags` for the titles, `read_query` on `memory_events` for
the full content oldest-first, `event_links` for the chain of reasoning, `open_questions` for
what is still open, `event_sources` joined with `sources` for where it came from. Fall back to
`search_text` only when the tag index misses. Do not write a "resumed" entry; write the next
real one and link it.

## Setup (first time on a database)

Run the blocks in [references/views.sql](references/views.sql) in order: the `-- table:` block
through `write_query` as written, and each `-- view:` block through
`create_view(name=<name>, select_sql=<the SELECT>, description=<the description line>)`. A view
that already exists makes `create_view` refuse; that is fine, move on. Finish with
`read_query("SELECT * FROM topics", limit=5)` and `get_schema()` to confirm the nine views are
there.

## Arguments

- `setup`: run the setup above.
- `resume #tag`: run the resume playbook for that tag and report what you reloaded.
- `source <key>`: ask for the missing fields, then register the source.

## Reference files

- [references/templates.md](references/templates.md): the exact entry and checkpoint templates.
- [references/tags.md](references/tags.md): the canonical tag vocabulary, edit to extend.
- [references/views.sql](references/views.sql): the sources table and the nine views.
- [references/resume-playbook.md](references/resume-playbook.md): the queries for resuming a topic.
- [references/core-rules.md](references/core-rules.md): the digest a hook injects at every session start.
