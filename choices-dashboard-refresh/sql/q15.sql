-- Q15 · Funnels › Retention by first story (no AppsFlyer needed)
-- First story = the story of the device's first-ever bp_match_start (history from 30 Sep). is_first_story_start is not used:
--   the app sends it but the pipeline drops true/false properties, so the earliest bp_match_start stands in.
-- D1 / D3 / D7 = the device fired bp_app_launch 1 / 3 / 7 IST calendar days after its first-story date.
-- The page counts a player in a Dn column only once that day has finished (last full day: the day before the cut-off), so partial days don't pull rates down.
-- Events up to {{CUTOFF}} IST.
WITH ev AS (
  SELECT event_id, event_type, event_date AS d, event_timestamp AS ts, af_id,
    (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key = 'map') AS map,
    (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key = 'story_title') AS title
  FROM `choices-prod-data.choices_dev_sdk_base.raw_events`
  WHERE app.version IS NOT NULL AND af_id IS NOT NULL AND af_id != '' AND event_timestamp <= TIMESTAMP('{{CUTOFF}}', 'Asia/Kolkata')
  QUALIFY ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY event_timestamp) = 1),
first_story AS (
  SELECT af_id, ARRAY_AGG(STRUCT(d, map) ORDER BY ts LIMIT 1)[OFFSET(0)] f
  FROM ev WHERE event_type = 'bp_match_start' AND map IS NOT NULL GROUP BY 1),
titles AS (SELECT map, MAX(title) title FROM ev WHERE event_type='bp_match_start' AND map IS NOT NULL GROUP BY 1),
launch AS (SELECT DISTINCT af_id, d FROM ev WHERE event_type = 'bp_app_launch')
SELECT fs.f.d AS first_date, t.title AS story, COUNT(*) AS players,
  COUNTIF(l1.af_id IS NOT NULL) d1, COUNTIF(l3.af_id IS NOT NULL) d3, COUNTIF(l7.af_id IS NOT NULL) d7
FROM first_story fs JOIN titles t ON t.map = fs.f.map
LEFT JOIN launch l1 ON l1.af_id = fs.af_id AND l1.d = DATE_ADD(fs.f.d, INTERVAL 1 DAY)
LEFT JOIN launch l3 ON l3.af_id = fs.af_id AND l3.d = DATE_ADD(fs.f.d, INTERVAL 3 DAY)
LEFT JOIN launch l7 ON l7.af_id = fs.af_id AND l7.d = DATE_ADD(fs.f.d, INTERVAL 7 DAY)
GROUP BY 1, 2 ORDER BY 1, 2
