# second-brain: rules for this session

The sqlite-memory server is your second brain for this work. It has two layers.

- Raw layer: hooks record every prompt, every context compaction and every session end
  automatically. Never write the kinds `prompt`, `compaction` or `session-end` yourself.
- Curated layer: you write `insight`, `decision`, `reading`, `open-question` and `note` entries
  with `append_event`, and state summaries with `checkpoint`. This layer is the index. Write each
  entry so that reading it in six months ramps you back up on what was thought and why.

Session start: unless this context already contains a resume block, call
`get_resume_context(max_events=40, exclude_kinds="prompt,compaction,session-end")` first.

Hard rules. A hook validates every `append_event` and `checkpoint` and refuses violations with
the reason; fix the text, never work around it.

1. Math is LaTeX: inline `$...$`, display `$$...$$`. Never paraphrase a formula in words, never
   use Unicode math symbols outside LaTeX.
2. Curated entries follow the template for their kind (the skill's `references/templates.md`):
   a one-line title, the labelled lines in order, and a final line `tags: #a #b` with one to five
   tags from `references/tags.md`. To use a new tag, add it to that file with a definition first.
   That file is meant to be edited: its subject tags are a starter set for math-heavy study, to
   be swapped for the user's own domain; the "Objects and moves" section and the one-tag-per-line
   mechanism stay.
3. Sources are cited as `Source: <key> <locator>` (several separated by `;`), with keys registered
   in the `sources` table, or `Source: discussion` when the entry came from our own work.
4. Links between entries are lines `Builds on: #id`, `Supersedes: #id`, `Corrects: #id`,
   `Answers: #id`. Superseded entries drop out of `current_synthesis` without being deleted.
5. Images are transcribed (LaTeX for equations, a structured description for diagrams), never
   stored. If the original matters, the user saves the file and the entry cites its path.

Finding things: `search_text` finds ids, `read_query` reads content. Views: `synthesis`,
`current_synthesis`, `event_tags`, `event_links`, `event_sources`, `open_questions`, `readings`,
`topics`. Never DELETE or UPDATE memory rows; the server refuses it anyway.

For templates, the tag list, the topic resume playbook and setup: load `/second-brain:memory`.
