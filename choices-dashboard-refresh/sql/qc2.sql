-- QC2 · Cohorts tab › Activation table, per install date and filter combination
-- Cohort, filters and Energy crediting exactly as QC1 (install time = TIMESTAMP(install_time), UTC; check AF3). D0 = the IST install date.
-- story_start_users = devices with bp_match_start on D0; first_choice_users = devices with choice_made on D0;
-- exhausted_d0_users = devices credited with an exhaustion on D0.
-- median_min_to_choice = median minutes from the AppsFlyer install time to the device's first choice_made at or after the install
--   (devices that made one, up to the cut-off). Activity from more than 10 minutes before the install is ignored: AppsFlyer can count
--   a device that was already playing as a new install.
-- median_d0_choices = median number of choice_made on D0, over all installs (0 counts).
-- First session = the device's earliest SDK session_id (by first event time). median_first_session_choices = median choice_made in it,
--   over devices with a session. median_first_session_min = median duration_ms / 60000 from the bp_session_end whose own
--   session_id property equals that session (check AF3: bp_session_end carries duration_ms and session_id on every event),
--   over devices whose first session has ended.
-- Medians are exact: the middle value (or the mean of the two middle values) of the sorted list.
WITH ev AS (
  SELECT event_id, event_type, event_date, event_timestamp AS ts, service_name, app.version AS ver, af_id, session_id, event_props
  FROM `choices-prod-data.choices_dev_sdk_base.raw_events`
  WHERE event_date >= DATE '2026-10-01' AND event_timestamp <= TIMESTAMP('{{CUTOFF}}', 'Asia/Kolkata')
  QUALIFY ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY event_timestamp) = 1
),
app AS (
  SELECT event_type, event_date, ts, af_id, session_id,
    (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key='app_user_id') AS app_user_id,
    (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key='tutorial_type') AS tutorial_type,
    (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key='session_id') AS ended_session_id,
    (SELECT p.int_value FROM UNNEST(event_props) p WHERE p.key='duration_ms') AS duration_ms
  FROM ev WHERE ver IS NOT NULL AND af_id IS NOT NULL AND af_id != ''),
af AS (
  SELECT appsflyer_id AS af_id, TIMESTAMP(install_time) AS install_ts, DATE(TIMESTAMP(install_time), 'Asia/Kolkata') AS install_date,
    IFNULL(NULLIF(media_source, ''), 'unknown') AS campaign
  FROM `choices-prod-data.choices_dev_base.appsflyer_installs`
  WHERE TIMESTAMP(install_time) <= TIMESTAMP('{{CUTOFF}}', 'Asia/Kolkata')
    AND DATE(TIMESTAMP(install_time), 'Asia/Kolkata') >= DATE '{{COHORT_FROM}}'  -- older cohorts are past D14: stored and final
  QUALIFY ROW_NUMBER() OVER (PARTITION BY appsflyer_id ORDER BY TIMESTAMP(install_time)) = 1),
cfg AS (SELECT af_id, ANY_VALUE(CASE tutorial_type WHEN 'story_launch' THEN 'story' WHEN 'home_launch' THEN 'home' END) AS cfg
        FROM app WHERE event_type = 'bp_tutorial_start' GROUP BY 1),
bal AS (
  SELECT event_id, event_date, ts,
    (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key='app_user_id') AS app_user_id,
    (SELECT p.bool_value FROM UNNEST(event_props) p WHERE p.key='exhausted') AS exhausted
  FROM ev WHERE event_type = 'bp_balance_update' AND service_name = 'choices-backend-api'),
credit AS (
  SELECT b.event_id, ANY_VALUE(b.event_date) AS date, ANY_VALUE(b.exhausted) AS exhausted,
    ARRAY_AGG(a.af_id ORDER BY a.ts DESC LIMIT 1)[SAFE_OFFSET(0)] AS af_id
  FROM bal b JOIN app a ON a.app_user_id = b.app_user_id AND a.ts <= b.ts AND a.ts >= TIMESTAMP_SUB(b.ts, INTERVAL 10 MINUTE)
  GROUP BY b.event_id),
first_exh AS (SELECT af_id, MIN(date) AS d FROM credit WHERE exhausted GROUP BY 1),
first_sess AS (  -- first SDK session from the install on (a device AppsFlyer re-counts as a new install may have older sessions)
  SELECT a.af_id, ARRAY_AGG(a.session_id ORDER BY a.ts LIMIT 1)[SAFE_OFFSET(0)] AS sid
  FROM app a JOIN af USING (af_id)
  WHERE a.session_id IS NOT NULL AND a.session_id != '' AND a.ts >= TIMESTAMP_SUB(af.install_ts, INTERVAL 10 MINUTE) GROUP BY 1),
dev AS (
  SELECT af.af_id, af.install_date, af.campaign, IFNULL(c.cfg, 'none') AS g_cfg, IF(f.af_id IS NULL, 'no', 'yes') AS g_energy,
    EXISTS(SELECT 1 FROM app a WHERE a.af_id = af.af_id AND a.event_type = 'bp_match_start' AND a.event_date = af.install_date) AS d0_story,
    EXISTS(SELECT 1 FROM app a WHERE a.af_id = af.af_id AND a.event_type = 'choice_made' AND a.event_date = af.install_date) AS d0_choice,
    (f.d = af.install_date) AS d0_exhausted,
    (SELECT GREATEST(TIMESTAMP_DIFF(MIN(a.ts), af.install_ts, SECOND), 0) / 60 FROM app a WHERE a.af_id = af.af_id AND a.event_type = 'choice_made'
       AND a.ts >= TIMESTAMP_SUB(af.install_ts, INTERVAL 10 MINUTE)) AS min_to_choice,
    (SELECT COUNT(*) FROM app a WHERE a.af_id = af.af_id AND a.event_type = 'choice_made' AND a.event_date = af.install_date) AS d0_choices,
    (SELECT COUNTIF(a.event_type = 'choice_made') FROM app a WHERE a.af_id = af.af_id AND a.session_id = s.sid) AS fs_choices,
    (SELECT MAX(a.duration_ms) / 60000 FROM app a WHERE a.af_id = af.af_id AND a.event_type = 'bp_session_end' AND a.ended_session_id = s.sid) AS fs_min,
    s.sid IS NOT NULL AS has_session
  FROM af LEFT JOIN cfg c USING (af_id) LEFT JOIN first_exh f USING (af_id) LEFT JOIN first_sess s USING (af_id)),
agg AS (
  SELECT install_date,
    IF(GROUPING(g_cfg) = 1, 'all', g_cfg) AS launch_config,
    IF(GROUPING(g_energy) = 1, 'all', g_energy) AS energy_filter,
    IF(GROUPING(campaign) = 1, 'all', campaign) AS campaign_out,
    COUNT(*) AS installs, COUNTIF(d0_story) AS story_start_users, COUNTIF(d0_choice) AS first_choice_users, COUNTIF(IFNULL(d0_exhausted, FALSE)) AS exhausted_d0_users,
    ARRAY_AGG(min_to_choice IGNORE NULLS ORDER BY min_to_choice) AS a_mtc,
    ARRAY_AGG(d0_choices ORDER BY d0_choices) AS a_d0,
    ARRAY_AGG(IF(has_session, fs_choices, NULL) IGNORE NULLS ORDER BY IF(has_session, fs_choices, NULL)) AS a_fsc,
    ARRAY_AGG(fs_min IGNORE NULLS ORDER BY fs_min) AS a_fsm
  FROM dev
  GROUP BY GROUPING SETS (
    (install_date), (install_date, g_cfg), (install_date, g_energy), (install_date, campaign),
    (install_date, g_cfg, g_energy), (install_date, g_cfg, campaign), (install_date, g_energy, campaign),
    (install_date, g_cfg, g_energy, campaign)))
SELECT install_date, launch_config, energy_filter, campaign_out AS campaign, installs, story_start_users, first_choice_users, exhausted_d0_users,
  ROUND((a_mtc[SAFE_OFFSET(DIV(ARRAY_LENGTH(a_mtc) - 1, 2))] + a_mtc[SAFE_OFFSET(DIV(ARRAY_LENGTH(a_mtc), 2))]) / 2, 1) AS median_min_to_choice,
  ROUND((a_d0[SAFE_OFFSET(DIV(ARRAY_LENGTH(a_d0) - 1, 2))] + a_d0[SAFE_OFFSET(DIV(ARRAY_LENGTH(a_d0), 2))]) / 2, 1) AS median_d0_choices,
  ROUND((a_fsc[SAFE_OFFSET(DIV(ARRAY_LENGTH(a_fsc) - 1, 2))] + a_fsc[SAFE_OFFSET(DIV(ARRAY_LENGTH(a_fsc), 2))]) / 2, 1) AS median_first_session_choices,
  ROUND((a_fsm[SAFE_OFFSET(DIV(ARRAY_LENGTH(a_fsm) - 1, 2))] + a_fsm[SAFE_OFFSET(DIV(ARRAY_LENGTH(a_fsm), 2))]) / 2, 1) AS median_first_session_min,
  ARRAY_LENGTH(a_mtc) AS n_min_to_choice, ARRAY_LENGTH(a_fsc) AS n_first_session, ARRAY_LENGTH(a_fsm) AS n_first_session_with_end
FROM agg
WHERE launch_config != 'none'
ORDER BY install_date, launch_config, energy_filter, campaign