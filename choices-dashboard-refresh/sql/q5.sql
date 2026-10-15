-- Q5 · Funnels › After an ending
-- "Complete" = the app's >5-clip rule (see Q14). Player = af_id. Cut-off = {{CUTOFF}} IST.
-- An ending counts only if its whole follow-up window ended before the cut-off:
--   next story within 24h: complete endings at least 24h before the cut-off; within 72h: at least 72h before (none yet).
--   tree retry (24h): incomplete endings at least 24h before the cut-off.
-- Next story = bp_match_start of a DIFFERENT map (any match_format). Tree retry = tree_open (any story). Counted per player.
WITH dedup AS (
  SELECT event_id, event_type, event_timestamp AS ts, af_id, event_props FROM `choices-prod-data.choices_dev_sdk_base.raw_events`
  WHERE app.version IS NOT NULL AND af_id IS NOT NULL AND af_id != '' AND event_type IN ('bp_match_end','bp_match_start','tree_open')
    AND event_date BETWEEN DATE '2026-10-08' AND DATE '{{TODAY}}' AND event_timestamp <= TIMESTAMP('{{CUTOFF}}', 'Asia/Kolkata')
  QUALIFY ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY event_timestamp) = 1),
ev AS (SELECT event_type, ts, af_id, (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key='map') AS map,
         (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key='match_result') AS match_result FROM dedup),
cutoff AS (SELECT TIMESTAMP('{{CUTOFF}}', 'Asia/Kolkata') AS c),
complete_end AS (SELECT af_id, ts, map FROM ev, cutoff WHERE event_type='bp_match_end' AND match_result='complete' AND ts <= TIMESTAMP_SUB(c, INTERVAL 72 HOUR)),
complete_24 AS (SELECT af_id, ts, map FROM ev, cutoff WHERE event_type='bp_match_end' AND match_result='complete' AND ts <= TIMESTAMP_SUB(c, INTERVAL 24 HOUR)),
incomplete_end AS (SELECT af_id, ts FROM ev, cutoff WHERE event_type='bp_match_end' AND match_result='incomplete' AND ts <= TIMESTAMP_SUB(c, INTERVAL 24 HOUR)),
starts AS (SELECT af_id, ts, map FROM ev WHERE event_type='bp_match_start'),
trees AS (SELECT af_id, ts FROM ev WHERE event_type='tree_open')
SELECT
  (SELECT COUNT(DISTINCT af_id) FROM complete_end) AS complete_players_72h_eligible,
  (SELECT COUNT(DISTINCT c.af_id) FROM complete_end c JOIN starts s ON s.af_id=c.af_id AND s.map != c.map AND s.ts > c.ts AND s.ts <= TIMESTAMP_ADD(c.ts, INTERVAL 72 HOUR)) AS next_story_72h,
  (SELECT COUNT(DISTINCT af_id) FROM complete_24) AS complete_players_24h_eligible,
  (SELECT COUNT(DISTINCT c.af_id) FROM complete_24 c JOIN starts s ON s.af_id=c.af_id AND s.map != c.map AND s.ts > c.ts AND s.ts <= TIMESTAMP_ADD(c.ts, INTERVAL 24 HOUR)) AS next_story_24h,
  (SELECT COUNT(DISTINCT af_id) FROM incomplete_end) AS incomplete_players,
  (SELECT COUNT(DISTINCT i.af_id) FROM incomplete_end i JOIN trees t ON t.af_id=i.af_id AND t.ts > i.ts AND t.ts <= TIMESTAMP_ADD(i.ts, INTERVAL 24 HOUR)) AS tree_open_24h
