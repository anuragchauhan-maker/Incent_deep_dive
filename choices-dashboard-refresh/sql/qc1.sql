-- QC1 · Cohorts tab: install cohorts by day since install (D0..D14), every filter combination
-- Cohort = devices in choices_dev_base.appsflyer_installs (new installs; reinstalls are not included). Device = appsflyer_id = af_id
--   (check AF2: on 13 Oct every AppsFlyer install matches an app af_id).
-- Install time = TIMESTAMP(install_time): install_time is UTC (check AF3: matches bp_install within 0.1 min).
--   NOT ts_epoch_seconds, which is 330 min early (pipeline bug, check AF3). Install date = IST date of the install time.
-- day_n = IST calendar days since the install date (D0 = install day). Only days up to {{TODAY}}, which is partial (cut-off {{CUTOFF}} IST).
-- Filters: launch_config = bp_tutorial_start.tutorial_type (story_launch -> story, home_launch -> home); devices without one appear only under 'all'.
--   energy_filter = 'yes' if the device was ever credited with a backend exhausted = true (Q8 rule), else 'no'.
--   campaign = AppsFlyer media_source.
-- One row per cohort x filter; days = JSON list of [day_n, dau, sdau, cdau, choices, energy, stories_started, stories_completed,
--   watch_min, exhausted, ever_exhausted], one per day so far (D0..D14).
-- Per day: dau = bp_app_launch that day; sdau = bp_match_start; cdau = choice_made; choices = choice_made events;
--   energy = backend spends credited to the device (Q8 rule; SUM(-delta)); stories_started = bp_match_start events;
--   stories_completed = bp_match_end with match_result = 'complete'; watch_min = SUM(match_metrics.seconds_watched)/60;
--   exhausted = devices credited with an exhaustion that day; ever_exhausted = devices credited with one on or before that day.
WITH ev AS (
  SELECT event_id, event_type, event_date, event_timestamp AS ts, service_name, app.version AS ver, af_id, event_props
  FROM `choices-prod-data.choices_dev_sdk_base.raw_events`
  WHERE event_date >= DATE '2026-10-01' AND event_timestamp <= TIMESTAMP('{{CUTOFF}}', 'Asia/Kolkata')
  QUALIFY ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY event_timestamp) = 1
),
app AS (
  SELECT event_type, event_date, ts, af_id,
    (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key='app_user_id') AS app_user_id,
    (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key='tutorial_type') AS tutorial_type,
    (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key='match_result') AS match_result,
    (SELECT COALESCE(CAST(p.int_value AS FLOAT64), p.float_value) FROM UNNEST(event_props) p WHERE p.key='match_metrics.seconds_watched') AS secs
  FROM ev WHERE ver IS NOT NULL AND af_id IS NOT NULL AND af_id != ''),
af AS (
  SELECT appsflyer_id AS af_id, DATE(TIMESTAMP(install_time), 'Asia/Kolkata') AS install_date, IFNULL(NULLIF(media_source, ''), 'unknown') AS campaign
  FROM `choices-prod-data.choices_dev_base.appsflyer_installs`
  WHERE TIMESTAMP(install_time) <= TIMESTAMP('{{CUTOFF}}', 'Asia/Kolkata')
    AND DATE(TIMESTAMP(install_time), 'Asia/Kolkata') >= DATE '{{COHORT_FROM}}'  -- older cohorts are past D14: stored and final
  QUALIFY ROW_NUMBER() OVER (PARTITION BY appsflyer_id ORDER BY TIMESTAMP(install_time)) = 1),
cfg AS (SELECT af_id, ANY_VALUE(CASE tutorial_type WHEN 'story_launch' THEN 'story' WHEN 'home_launch' THEN 'home' END) AS cfg
        FROM app WHERE event_type = 'bp_tutorial_start' GROUP BY 1),
bal AS (
  SELECT event_id, event_date, ts,
    (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key='app_user_id') AS app_user_id,
    (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key='reason') AS reason,
    (SELECT p.int_value FROM UNNEST(event_props) p WHERE p.key='delta') AS delta,
    (SELECT p.bool_value FROM UNNEST(event_props) p WHERE p.key='exhausted') AS exhausted
  FROM ev WHERE event_type = 'bp_balance_update' AND service_name = 'choices-backend-api'),
credit AS (
  SELECT b.event_id, ANY_VALUE(b.event_date) AS date, ANY_VALUE(b.reason) AS reason, ANY_VALUE(b.delta) AS delta, ANY_VALUE(b.exhausted) AS exhausted,
    ARRAY_AGG(a.af_id ORDER BY a.ts DESC LIMIT 1)[SAFE_OFFSET(0)] AS af_id
  FROM bal b JOIN app a ON a.app_user_id = b.app_user_id AND a.ts <= b.ts AND a.ts >= TIMESTAMP_SUB(b.ts, INTERVAL 10 MINUTE)
  GROUP BY b.event_id),
first_exh AS (SELECT af_id, MIN(date) AS d FROM credit WHERE exhausted GROUP BY 1),
dev AS (SELECT af.*, IFNULL(c.cfg, 'none') AS cfg, IF(f.af_id IS NULL, 'no', 'yes') AS energy_flag
        FROM af LEFT JOIN cfg c USING (af_id) LEFT JOIN first_exh f USING (af_id)),
grid AS (SELECT d.*, n AS day_n, DATE_ADD(d.install_date, INTERVAL n DAY) AS day
         FROM dev d, UNNEST(GENERATE_ARRAY(0, 14)) AS n WHERE DATE_ADD(d.install_date, INTERVAL n DAY) <= DATE '{{TODAY}}'),
app_day AS (
  SELECT af_id, event_date,
    LOGICAL_OR(event_type = 'bp_app_launch') AS active, LOGICAL_OR(event_type = 'bp_match_start') AS story, LOGICAL_OR(event_type = 'choice_made') AS chose,
    COUNTIF(event_type = 'choice_made') AS choices, COUNTIF(event_type = 'bp_match_start') AS stories_started,
    COUNTIF(event_type = 'bp_match_end' AND match_result = 'complete') AS stories_completed,
    SUM(IF(event_type = 'bp_match_end', IFNULL(secs, 0), 0)) AS watch_secs
  FROM app GROUP BY 1, 2),
energy_day AS (SELECT af_id, date, SUM(IF(reason = 'spend', -delta, 0)) AS energy, LOGICAL_OR(IFNULL(exhausted, FALSE)) AS exh
               FROM credit WHERE af_id IS NOT NULL GROUP BY 1, 2),
facts AS (
  SELECT g.install_date, g.day_n, g.cfg AS g_cfg, g.energy_flag AS g_energy, g.campaign AS g_campaign,
    IFNULL(a.active, FALSE) AS is_dau, IFNULL(a.story, FALSE) AS is_sdau, IFNULL(a.chose, FALSE) AS is_cdau,
    IFNULL(a.choices, 0) AS n_choices, IFNULL(e.energy, 0) AS n_energy, IFNULL(a.stories_started, 0) AS n_started,
    IFNULL(a.stories_completed, 0) AS n_completed, IFNULL(a.watch_secs, 0) AS n_watch_secs,
    IFNULL(e.exh, FALSE) AS is_exhausted, (f.d IS NOT NULL AND f.d <= g.day) AS is_ever_exhausted
  FROM grid g
  LEFT JOIN app_day a ON a.af_id = g.af_id AND a.event_date = g.day
  LEFT JOIN energy_day e ON e.af_id = g.af_id AND e.date = g.day
  LEFT JOIN first_exh f ON f.af_id = g.af_id)
SELECT install_date, launch_config, energy_filter, campaign, MAX(installs) AS installs,
  CONCAT('[', STRING_AGG(TO_JSON_STRING([CAST(day_n AS FLOAT64), dau, sdau, cdau, choices, energy, stories_started, stories_completed, watch_min, exhausted, ever_exhausted]), ',' ORDER BY day_n), ']') AS days
FROM (
  SELECT install_date, day_n,
    IF(GROUPING(g_cfg) = 1, 'all', g_cfg) AS launch_config,
    IF(GROUPING(g_energy) = 1, 'all', g_energy) AS energy_filter,
    IF(GROUPING(g_campaign) = 1, 'all', g_campaign) AS campaign,
    COUNT(*) AS installs, COUNTIF(is_dau) AS dau, COUNTIF(is_sdau) AS sdau, COUNTIF(is_cdau) AS cdau,
    SUM(n_choices) AS choices, SUM(n_energy) AS energy, SUM(n_started) AS stories_started, SUM(n_completed) AS stories_completed,
    ROUND(SUM(n_watch_secs) / 60, 1) AS watch_min, COUNTIF(is_exhausted) AS exhausted, COUNTIF(is_ever_exhausted) AS ever_exhausted
  FROM facts
  GROUP BY GROUPING SETS (
    (install_date, day_n), (install_date, day_n, g_cfg), (install_date, day_n, g_energy), (install_date, day_n, g_campaign),
    (install_date, day_n, g_cfg, g_energy), (install_date, day_n, g_cfg, g_campaign), (install_date, day_n, g_energy, g_campaign),
    (install_date, day_n, g_cfg, g_energy, g_campaign)))
WHERE launch_config != 'none'
GROUP BY 1, 2, 3, 4
ORDER BY 1, 2, 3, 4
