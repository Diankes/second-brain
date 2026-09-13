# Resuming a topic from weeks ago

The aim is to reload the reasoning, not just the conclusions, with the fewest tokens. Search
finds ids; `read_query` reads content. Every query below is a `read_query` call unless noted.

1. Find the tag. If unsure of the exact tag, list the index:
   ```sql
   SELECT tag, entries, latest_id FROM topics
   ```
2. List the entries for the tag, newest first, titles only (the title is the first line):
   ```sql
   SELECT e.id, e.ts, e.kind, substr(e.content, 1, instr(e.content || char(10), char(10)) - 1) AS title
   FROM current_synthesis e JOIN event_tags t ON t.id = e.id
   WHERE t.tag = '#spectral-theorem' ORDER BY e.id DESC
   ```
   `current_synthesis` already hides superseded entries. Use `synthesis` instead when the history
   of a belief matters.
3. Read the ones that matter in full, oldest first so the reasoning reads forward:
   ```sql
   SELECT id, kind, content FROM memory_events WHERE id IN (57, 61, 88) ORDER BY id
   ```
4. Follow the chain when an entry says `Builds on:`:
   ```sql
   WITH RECURSIVE chain(id, depth) AS (
       SELECT 88, 0
       UNION ALL
       SELECT l.to_id, depth + 1 FROM event_links l JOIN chain c ON l.from_id = c.id
       WHERE l.rel = 'builds-on' AND depth < 6
   )
   SELECT c.depth, e.id, e.kind, substr(e.content, 1, 100) FROM chain c JOIN memory_events e ON e.id = c.id
   ORDER BY depth DESC
   ```
5. Check what is still open on the topic:
   ```sql
   SELECT q.id, substr(q.content, 1, 120) FROM open_questions q JOIN event_tags t ON t.id = q.id
   WHERE t.tag = '#spectral-theorem'
   ```
6. Where it came from:
   ```sql
   SELECT s.key, s.title, count(*) AS entries FROM event_tags t
   JOIN event_sources es ON es.event_id = t.id JOIN sources s ON s.key = es.source_key
   WHERE t.tag = '#spectral-theorem' GROUP BY s.key
   ```
7. Only when the tag index misses (the entry predates the tag, or the wording is all you have),
   fall back to text search, which also scans raw prompts and responses:
   `search_text(pattern="Courant.Fischer", table="memory_events", columns=["content"],
   where="kind NOT IN ('prompt','compaction','session-end','response')", ignore_case=true)`
   then read the ids it returns.

After reloading, do not write a "resumed" entry: that is noise. Write the next real insight or
decision, and link it with `Builds on:` to what you just read.
