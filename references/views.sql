-- second-brain bootstrap. Run once per database through the sqlite-memory tools:
--   "-- table:" blocks go to write_query as written;
--   "-- view:" blocks go to create_view(name, select_sql, description) with the SELECT below
--   the header and the "-- description:" text as the description.
-- Order matters: later views read earlier ones. Re-running is harmless: the table uses
-- IF NOT EXISTS and create_view refuses to redefine an existing view unless replace=true.

-- table: sources
CREATE TABLE IF NOT EXISTS sources (
    key     TEXT PRIMARY KEY,
    kind    TEXT NOT NULL CHECK (kind IN ('paper', 'lecture', 'textbook', 'notes', 'other')),
    title   TEXT NOT NULL,
    authors TEXT,
    year    INTEGER,
    locator TEXT,
    added   TEXT NOT NULL,
    notes   TEXT
);

-- view: synthesis
-- description: curated entries only (insight, decision, reading, open-question, note); hook-written raw events are excluded
SELECT id, ts, session, kind, content FROM memory_events
WHERE kind NOT IN ('prompt', 'compaction', 'session-end', 'response');

-- view: event_lines
-- description: helper: one row per line of each curated entry (id, line); the parsing views build on it
WITH RECURSIVE lines(id, line, rest) AS (
    SELECT id, '', content || char(10) FROM synthesis
    UNION ALL
    SELECT id, substr(rest, 1, instr(rest, char(10)) - 1), substr(rest, instr(rest, char(10)) + 1)
    FROM lines WHERE rest <> ''
)
SELECT id, line FROM lines WHERE line <> '';

-- view: event_tags
-- description: (id, tag) pairs parsed from the final "tags:" line of each curated entry
WITH RECURSIVE split(id, tag, rest) AS (
    SELECT id, '', trim(substr(line, 6)) || ' ' FROM event_lines WHERE line LIKE 'tags:%'
    UNION ALL
    SELECT id, substr(rest, 1, instr(rest, ' ') - 1), substr(rest, instr(rest, ' ') + 1)
    FROM split WHERE rest <> ''
)
SELECT id, tag FROM split WHERE tag LIKE '#%';

-- view: event_links
-- description: (from_id, rel, to_id) parsed from "Builds on:", "Supersedes:", "Corrects:" and "Answers:" lines
WITH RECURSIVE
  rel(id, rel, rest) AS (
    SELECT id,
      CASE WHEN line LIKE 'Builds on:%' THEN 'builds-on'
           WHEN line LIKE 'Supersedes:%' THEN 'supersedes'
           WHEN line LIKE 'Corrects:%' THEN 'corrects'
           ELSE 'answers' END,
      trim(substr(line, instr(line, ':') + 1)) || ' '
    FROM event_lines
    WHERE line LIKE 'Builds on:%' OR line LIKE 'Supersedes:%'
       OR line LIKE 'Corrects:%' OR line LIKE 'Answers:%'
  ),
  ids(id, rel, token, rest) AS (
    SELECT id, rel, '', rest FROM rel
    UNION ALL
    SELECT id, rel, substr(rest, 1, instr(rest, ' ') - 1), substr(rest, instr(rest, ' ') + 1)
    FROM ids WHERE rest <> ''
  )
SELECT id AS from_id, rel, CAST(substr(token, 2) AS INTEGER) AS to_id
FROM ids WHERE token LIKE '#%';

-- view: event_sources
-- description: (event_id, source_key, locator) parsed from "Source:" lines; "discussion" is skipped; join with sources on key
WITH RECURSIVE
  src(id, rest) AS (
    SELECT id, trim(substr(line, 8)) || ';' FROM event_lines WHERE line LIKE 'Source:%'
  ),
  parts(id, part, rest) AS (
    SELECT id, '', rest FROM src
    UNION ALL
    SELECT id, trim(substr(rest, 1, instr(rest, ';') - 1)), substr(rest, instr(rest, ';') + 1)
    FROM parts WHERE rest <> ''
  )
SELECT id AS event_id,
       CASE WHEN instr(part, ' ') > 0 THEN substr(part, 1, instr(part, ' ') - 1) ELSE part END AS source_key,
       CASE WHEN instr(part, ' ') > 0 THEN substr(part, instr(part, ' ') + 1) ELSE NULL END AS locator
FROM parts WHERE part <> '' AND part <> 'discussion';

-- view: current_synthesis
-- description: curated entries that no later entry supersedes; the present state of what we know
SELECT * FROM synthesis
WHERE id NOT IN (SELECT to_id FROM event_links WHERE rel = 'supersedes');

-- view: open_questions
-- description: open-question entries that nothing has answered or superseded yet
SELECT * FROM current_synthesis
WHERE kind = 'open-question'
  AND id NOT IN (SELECT to_id FROM event_links WHERE rel = 'answers');

-- view: readings
-- description: reading entries with their source key and locator, newest first
SELECT s.id, s.ts, es.source_key, es.locator, s.content
FROM synthesis s JOIN event_sources es ON es.event_id = s.id
WHERE s.kind = 'reading' ORDER BY s.id DESC;

-- view: topics
-- description: entries per tag with the newest entry id; the topic index for resuming work
SELECT tag, count(*) AS entries, max(id) AS latest_id FROM event_tags
GROUP BY tag ORDER BY entries DESC;
