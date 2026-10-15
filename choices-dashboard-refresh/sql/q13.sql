-- Q13 · Daily L0, every column and every filter (All, launch config, Energy). Replaces Q1, Q3, Q6, Q8, Q9 and Q12 on the page.
-- Same definitions as Q1, Q3, Q6, Q8, Q9 and Q12, computed per device and then grouped by the device's segment.
-- Segments (same as the Cohorts tab, QC1):
--   launch_config = bp_tutorial_start.tutorial_type (home_launch -> home, story_launch -> story); devices without one appear only under 'all'.
--   energy = 'yes' if the device was ever credited with a backend exhausted = true up to the cut-off (Q8 device rule:
--     the account's closest earlier Android app event within 10 minutes), else 'no'.
-- Energy spent in a segment = backend spends credited to the segment's devices by the same rule (Q7's 'all' total counts
--   spends by account, so segments can differ slightly from it).
-- Events up to the cut-off ({{CUTOFF}} IST; the last day is partial).
WITH ev AS (
  SELECT event_id, event_type, event_date AS d, event_timestamp AS ts, service_name, app.version AS ver, af_id,
    NULLIF(bp_user_id, '') AS bp, session_id, event_props
  FROM `choices-prod-data.choices_dev_sdk_base.raw_events`
  WHERE event_date >= DATE '2026-10-01' AND event_timestamp <= TIMESTAMP('{{CUTOFF}}', 'Asia/Kolkata')
  QUALIFY ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY event_timestamp) = 1
),
app AS (
  SELECT event_type, d, ts, af_id, bp, session_id,
    (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key = 'app_user_id') AS app_user_id,
    (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key = 'tutorial_type') AS tutorial_type,
    (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key = 'match_result') AS match_result,
    (SELECT COALESCE(CAST(p.int_value AS FLOAT64), p.float_value) FROM UNNEST(event_props) p WHERE p.key = 'match_metrics.seconds_watched') AS secs,
    (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key = 'app_session_id') AS asess,
    (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key = 'branch_id') AS branch,
    (SELECT COALESCE(CAST(p.int_value AS FLOAT64), p.float_value) FROM UNNEST(event_props) p WHERE p.key = 'ttff_ms') AS ttff_ms,
    (SELECT COALESCE(CAST(p.int_value AS FLOAT64), p.float_value) FROM UNNEST(event_props) p WHERE p.key = 'start_latency_ms') AS start_latency_ms,
    (SELECT COALESCE(CAST(p.int_value AS FLOAT64), p.float_value) FROM UNNEST(event_props) p WHERE p.key = 'transition_ms') AS transition_ms
  FROM ev WHERE ver IS NOT NULL AND af_id IS NOT NULL AND af_id != ''),
bal AS (
  SELECT event_id, d, ts,
    (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key = 'app_user_id') AS app_user_id,
    (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key = 'reason') AS reason,
    (SELECT p.int_value FROM UNNEST(event_props) p WHERE p.key = 'delta') AS delta,
    (SELECT p.bool_value FROM UNNEST(event_props) p WHERE p.key = 'exhausted') AS exhausted
  FROM ev WHERE event_type = 'bp_balance_update' AND service_name = 'choices-backend-api'),
credit AS (
  SELECT b.event_id, ANY_VALUE(b.d) AS d, ANY_VALUE(b.reason) AS reason, ANY_VALUE(b.delta) AS delta, ANY_VALUE(b.exhausted) AS exhausted,
    ARRAY_AGG(a.af_id ORDER BY a.ts DESC LIMIT 1)[SAFE_OFFSET(0)] AS af_id
  FROM bal b JOIN app a ON a.app_user_id = b.app_user_id AND a.ts <= b.ts AND a.ts >= TIMESTAMP_SUB(b.ts, INTERVAL 10 MINUTE)
  GROUP BY b.event_id),
seg AS (
  SELECT dv.af_id,
    IFNULL(c.cfg, 'none') AS cfg,
    IF(x.xaf IS NOT NULL, 'yes', 'no') AS energy
  FROM (SELECT DISTINCT af_id FROM app) dv
  LEFT JOIN (SELECT DISTINCT af_id AS xaf FROM credit WHERE exhausted) x ON x.xaf = dv.af_id
  LEFT JOIN (SELECT af_id, ANY_VALUE(CASE tutorial_type WHEN 'story_launch' THEN 'story' WHEN 'home_launch' THEN 'home' END) AS cfg
             FROM app WHERE event_type = 'bp_tutorial_start' GROUP BY 1) c USING (af_id)),
days AS (SELECT day FROM UNNEST(GENERATE_DATE_ARRAY(DATE '{{FROM}}', DATE '{{TODAY}}')) AS day),
-- new vs returning (Q12 rule)
dev_first AS (SELECT af_id, MIN(d) AS fd FROM app WHERE event_type = 'bp_app_launch' GROUP BY 1),
link AS (SELECT DISTINCT af_id, bp FROM app WHERE bp IS NOT NULL),
user_first AS (SELECT l.bp, MIN(f.fd) AS ufd FROM link l JOIN dev_first f USING (af_id) GROUP BY 1),
dev_user_first AS (SELECT l.af_id, MIN(u.ufd) AS ufd FROM link l JOIN user_first u USING (bp) GROUP BY 1),
-- per device per day facts
dd AS (
  SELECT d, af_id,
    LOGICAL_OR(event_type = 'bp_app_launch') AS launched,
    LOGICAL_OR(event_type = 'bp_match_start') AS started,
    LOGICAL_OR(event_type = 'choice_made') AS chose,
    COUNTIF(event_type = 'choice_made') AS choices,
    COUNTIF(event_type = 'branch_start') AS branches,
    COUNT(DISTINCT IF(event_type = 'bp_session_start', session_id, NULL)) AS sessions,
    COUNTIF(event_type = 'bp_match_start') AS story_starts,
    COUNTIF(event_type = 'bp_match_end' AND match_result = 'complete') AS completions,
    SUM(IF(event_type = 'bp_match_end', IFNULL(secs, 0), 0)) AS watch_secs
  FROM app WHERE d BETWEEN DATE '{{FROM}}' AND DATE '{{TODAY}}' GROUP BY 1, 2),
en AS (SELECT d, af_id, SUM(IF(reason = 'spend', -delta, 0)) AS energy, LOGICAL_OR(IFNULL(exhausted, FALSE)) AS exh
       FROM credit WHERE af_id IS NOT NULL GROUP BY 1, 2),
facts AS (
  SELECT dd.*, s.cfg AS g_cfg, s.energy AS eseg,
    IFNULL(en.energy, 0) AS energy_spent, IFNULL(en.exh, FALSE) AS exh,
    LEAST(f.fd, IFNULL(u.ufd, f.fd)) < dd.d AS returning
  FROM dd JOIN seg s USING (af_id)
  LEFT JOIN en ON en.af_id = dd.af_id AND en.d = dd.d
  LEFT JOIN dev_first f ON f.af_id = dd.af_id
  LEFT JOIN dev_user_first u ON u.af_id = dd.af_id),
a_day AS (
  SELECT d, IF(GROUPING(g_cfg) = 1, 'all', g_cfg) AS cfg, IF(GROUPING(eseg) = 1, 'all', eseg) AS energy,
    COUNTIF(launched) AS dau,
    COUNTIF(launched AND NOT returning) AS new_dau, COUNTIF(launched AND returning) AS returning_dau,
    COUNTIF(started) AS sdau, COUNTIF(chose) AS cdau, SUM(choices) AS choices, SUM(branches) AS branches,
    SUM(sessions) AS sessions, SUM(story_starts) AS story_starts, SUM(completions) AS story_completions,
    ROUND(SUM(watch_secs) / 60, 1) AS watch_min, SUM(energy_spent) AS energy_spent,
    COUNTIF(launched AND exh) AS exhausted_users
  FROM facts GROUP BY GROUPING SETS ((d), (d, g_cfg), (d, eseg), (d, g_cfg, eseg))),
-- WAU: devices with bp_app_launch in the 7 days ending that day
w AS (
  SELECT dy.day AS d, IF(GROUPING(s.cfg) = 1, 'all', s.cfg) AS cfg, IF(GROUPING(s.energy) = 1, 'all', s.energy) AS energy,
    COUNT(DISTINCT a.af_id) AS wau
  FROM days dy JOIN app a ON a.event_type = 'bp_app_launch' AND a.d BETWEEN DATE_SUB(dy.day, INTERVAL 6 DAY) AND dy.day
  JOIN seg s ON s.af_id = a.af_id
  GROUP BY GROUPING SETS ((dy.day), (dy.day, s.cfg), (dy.day, s.energy), (dy.day, s.cfg, s.energy))),
-- video health (Q3 rules), exact p75 by linear interpolation (same as PERCENTILE_CONT)
stalled_pairs AS (SELECT DISTINCT asess, branch FROM app WHERE event_type = 'video_stall'),
bs AS (SELECT a.d, a.af_id, a.asess, a.branch, COALESCE(a.ttff_ms, a.start_latency_ms) AS start_ms, a.transition_ms, s.cfg AS g_cfg, s.energy AS g_energy,
         sp.asess IS NOT NULL AS has_stall
       FROM app a JOIN seg s USING (af_id) LEFT JOIN stalled_pairs sp ON sp.asess = a.asess AND sp.branch = a.branch
       WHERE a.event_type = 'branch_start' AND a.d BETWEEN DATE '{{FROM}}' AND DATE '{{TODAY}}'),
v AS (
  SELECT d, IF(GROUPING(g_cfg) = 1, 'all', g_cfg) AS cfg, IF(GROUPING(g_energy) = 1, 'all', g_energy) AS energy,
    ARRAY_AGG(start_ms IGNORE NULLS ORDER BY start_ms) AS a_start,
    ARRAY_AGG(transition_ms IGNORE NULLS ORDER BY transition_ms) AS a_seam,
    COUNT(DISTINCT CONCAT(asess, '|', branch)) AS clip_plays,
    COUNT(DISTINCT IF(has_stall, CONCAT(asess, '|', branch), NULL)) AS stalled
  FROM bs GROUP BY GROUPING SETS ((d), (d, g_cfg), (d, g_energy), (d, g_cfg, g_energy))),
v2 AS (
  SELECT d, cfg, energy, clip_plays, stalled,
    (SELECT IF(ARRAY_LENGTH(a_start) = 0, NULL, a_start[SAFE_OFFSET(CAST(FLOOR(0.75 * (ARRAY_LENGTH(a_start) - 1)) AS INT64))]
       + (a_start[SAFE_OFFSET(CAST(CEIL(0.75 * (ARRAY_LENGTH(a_start) - 1)) AS INT64))] - a_start[SAFE_OFFSET(CAST(FLOOR(0.75 * (ARRAY_LENGTH(a_start) - 1)) AS INT64))])
       * (0.75 * (ARRAY_LENGTH(a_start) - 1) - FLOOR(0.75 * (ARRAY_LENGTH(a_start) - 1))))) AS p75_start,
    (SELECT IF(ARRAY_LENGTH(a_seam) = 0, NULL, a_seam[SAFE_OFFSET(CAST(FLOOR(0.75 * (ARRAY_LENGTH(a_seam) - 1)) AS INT64))]
       + (a_seam[SAFE_OFFSET(CAST(CEIL(0.75 * (ARRAY_LENGTH(a_seam) - 1)) AS INT64))] - a_seam[SAFE_OFFSET(CAST(FLOOR(0.75 * (ARRAY_LENGTH(a_seam) - 1)) AS INT64))])
       * (0.75 * (ARRAY_LENGTH(a_seam) - 1) - FLOOR(0.75 * (ARRAY_LENGTH(a_seam) - 1))))) AS p75_seam
  FROM v),
-- retention (Q9 rules): bp_install cohorts by install date
inst AS (SELECT af_id, MIN(d) AS idate FROM app WHERE event_type = 'bp_install' GROUP BY 1),
launch_days AS (SELECT DISTINCT af_id, d FROM app WHERE event_type = 'bp_app_launch'),
choice_days AS (SELECT DISTINCT af_id, d FROM app WHERE event_type = 'choice_made'),
r AS (
  SELECT i.idate AS d, IF(GROUPING(s.cfg) = 1, 'all', s.cfg) AS cfg, IF(GROUPING(s.energy) = 1, 'all', s.energy) AS energy,
    COUNT(*) AS installs,
    COUNTIF(l1.af_id IS NOT NULL) AS d1_launch, COUNTIF(c1.af_id IS NOT NULL) AS d1_choice, COUNTIF(l7.af_id IS NOT NULL) AS d7_launch
  FROM inst i JOIN seg s USING (af_id)
  LEFT JOIN launch_days l1 ON l1.af_id = i.af_id AND l1.d = DATE_ADD(i.idate, INTERVAL 1 DAY)
  LEFT JOIN choice_days c1 ON c1.af_id = i.af_id AND c1.d = DATE_ADD(i.idate, INTERVAL 1 DAY)
  LEFT JOIN launch_days l7 ON l7.af_id = i.af_id AND l7.d = DATE_ADD(i.idate, INTERVAL 7 DAY)
  WHERE i.idate BETWEEN DATE '{{FROM}}' AND DATE '{{TODAY}}'
  GROUP BY GROUPING SETS ((i.idate), (i.idate, s.cfg), (i.idate, s.cfg, s.energy), (i.idate, s.energy)))
SELECT a.d AS date, a.cfg, a.energy,
  a.dau, a.new_dau, a.returning_dau, IFNULL(w.wau, 0) AS wau, a.sdau, a.cdau, a.choices, a.branches, a.sessions,
  a.story_starts, a.story_completions, a.watch_min, a.energy_spent, a.exhausted_users,
  r.installs, r.d1_launch, r.d1_choice, r.d7_launch,
  ROUND(v2.p75_start) AS p75_latency_ms, ROUND(v2.p75_seam) AS p75_seam_ms,
  v2.clip_plays, v2.stalled, ROUND(100 * v2.stalled / NULLIF(v2.clip_plays, 0), 2) AS rebuffer_pct
FROM a_day a
LEFT JOIN w USING (d, cfg, energy)
LEFT JOIN v2 USING (d, cfg, energy)
LEFT JOIN r USING (d, cfg, energy)
WHERE a.cfg != 'none'
ORDER BY date, cfg, energy
