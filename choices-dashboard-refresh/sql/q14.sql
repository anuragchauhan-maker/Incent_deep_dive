-- Q14 · Funnels › Story table: per story per day, play starts, players, % of players making at least N choices, % reaching a complete ending
-- Player = device (af_id). A player counts on a day for a story if they fired bp_match_start for that story that day.
-- Choices = the player's choice_made events in that story that day (all visits added up, so resumes don't restart the count).
-- Complete = the player had a bp_match_end with match_result = 'complete' in that story that day (the app's >5-clip rule).
-- new_starts = bp_match_start with match_format = 'start' (resume and replay excluded). Day = event_date (IST).
-- Events up to the cut-off ({{CUTOFF}} IST; the last day is partial).
WITH ev AS (
  SELECT event_id, event_type, event_date AS d, af_id, event_props FROM `choices-prod-data.choices_dev_sdk_base.raw_events`
  WHERE app.version IS NOT NULL AND af_id IS NOT NULL AND af_id != '' AND event_type IN ('bp_match_start','choice_made','bp_match_end')
    AND event_date BETWEEN DATE '{{FROM}}' AND DATE '{{TODAY}}' AND event_timestamp <= TIMESTAMP('{{CUTOFF}}', 'Asia/Kolkata')
  QUALIFY ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY event_timestamp) = 1),
k AS (SELECT event_type, d, af_id,
  (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key = 'map') AS map,
  (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key = 'story_title') AS title,
  (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key = 'match_format') AS mf,
  (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key = 'match_result') AS mr FROM ev),
titles AS (SELECT map, MAX(title) AS story FROM k WHERE event_type = 'bp_match_start' AND map IS NOT NULL GROUP BY 1),
pd AS (
  SELECT d, af_id, map,
    COUNTIF(event_type = 'bp_match_start') AS starts, COUNTIF(event_type = 'bp_match_start' AND mf = 'start') AS new_starts,
    COUNTIF(event_type = 'choice_made') AS choices,
    LOGICAL_OR(event_type = 'bp_match_end' AND mr = 'complete') AS completed
  FROM k WHERE map IS NOT NULL GROUP BY 1, 2, 3)
SELECT pd.d AS date, t.story,
  SUM(starts) AS play_starts, SUM(new_starts) AS new_starts, COUNTIF(starts > 0) AS players,
  COUNTIF(starts > 0 AND choices >= 1) c1, COUNTIF(starts > 0 AND choices >= 2) c2, COUNTIF(starts > 0 AND choices >= 3) c3,
  COUNTIF(starts > 0 AND choices >= 4) c4, COUNTIF(starts > 0 AND choices >= 5) c5, COUNTIF(starts > 0 AND choices >= 6) c6,
  COUNTIF(starts > 0 AND choices >= 7) c7, COUNTIF(starts > 0 AND choices >= 8) c8, COUNTIF(starts > 0 AND choices >= 10) c10,
  COUNTIF(starts > 0 AND completed) AS complete_players,
  COUNTIF(starts = 0) AS players_without_start_that_day
FROM pd JOIN titles t USING (map)
GROUP BY 1, 2 ORDER BY 2, 1
