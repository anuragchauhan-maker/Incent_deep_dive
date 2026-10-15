-- Q10 · Funnels › Onboarding and First 24 hours, by launch config and install date
-- Cohort = af_ids with bp_install (SDK install event) AND a bp_tutorial_start: tutorial_type 'home_launch' -> home, 'story_launch' -> story.
-- Window start = the device's first app event (bp_install sometimes arrives more than 60 s after it), so actions taken before
--   bp_install arrived still count. Window = 24 hours from that start, up to the cut-off ({{CUTOFF}} IST); recent installs are "so far".
-- Each step = the device fired that event at least once inside its window. Steps are counted independently.
-- Onboarding steps: Home shown = screen_view with screen 'Home' or 'Home/Home'; Story started = bp_match_start;
--   First choice made = choice_made. "Login success" is left out until its meaning is agreed (guest auto-login vs Google).
-- First-24h steps: Story start = bp_match_start; First clip played = branch_start; First choice shown = choice_shown;
--   First choice made = choice_made; Ran out of Energy = a backend exhausted = true credited to this device
--   (the account's closest earlier Android app event within 10 minutes).
WITH ev AS (
  SELECT event_id, event_type, event_date, event_timestamp AS ts, service_name, app.version AS ver, af_id, event_props
  FROM `choices-prod-data.choices_dev_sdk_base.raw_events`
  WHERE event_date >= DATE '2026-10-01' AND event_timestamp <= TIMESTAMP('{{CUTOFF}}', 'Asia/Kolkata')
  QUALIFY ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY event_timestamp) = 1
),
app AS (SELECT event_type, ts, af_id, (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key='app_user_id') AS app_user_id,
               (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key='screen') AS screen,
               (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key='tutorial_type') AS tutorial_type
        FROM ev WHERE ver IS NOT NULL AND af_id IS NOT NULL AND af_id != ''),
first_seen AS (SELECT af_id, MIN(ts) AS first_ts FROM app GROUP BY 1),
inst AS (SELECT af_id, MIN(ts) AS install_ts FROM app WHERE event_type='bp_install' GROUP BY 1),
cfg AS (SELECT af_id, ANY_VALUE(CASE tutorial_type WHEN 'home_launch' THEN 'home' WHEN 'story_launch' THEN 'story' END) AS cfg
        FROM app WHERE event_type='bp_tutorial_start' AND tutorial_type IN ('home_launch','story_launch') GROUP BY 1),
cohort AS (SELECT i.af_id, c.cfg, f.first_ts AS start_ts, DATE(i.install_ts, 'Asia/Kolkata') AS install_date
           FROM inst i JOIN first_seen f USING (af_id) JOIN cfg c USING (af_id)),
exh AS (SELECT event_id, ts, (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key='app_user_id') AS app_user_id
        FROM ev WHERE event_type='bp_balance_update' AND service_name='choices-backend-api'
          AND (SELECT p.bool_value FROM UNNEST(event_props) p WHERE p.key='exhausted')),
exh_dev AS (SELECT x.event_id, ANY_VALUE(x.ts) AS ts, ARRAY_AGG(a.af_id ORDER BY a.ts DESC LIMIT 1)[SAFE_OFFSET(0)] AS af_id
            FROM exh x JOIN app a ON a.app_user_id = x.app_user_id AND a.ts <= x.ts AND a.ts >= TIMESTAMP_SUB(x.ts, INTERVAL 10 MINUTE)
            GROUP BY x.event_id),
steps AS (
  SELECT c.af_id, c.cfg, c.install_date,
    LOGICAL_OR(a.event_type='screen_view' AND a.screen IN ('Home','Home/Home')) AS home_shown,
    LOGICAL_OR(a.event_type='bp_match_start') AS story_started,
    LOGICAL_OR(a.event_type='branch_start') AS clip_played,
    LOGICAL_OR(a.event_type='choice_shown') AS choice_shown,
    LOGICAL_OR(a.event_type='choice_made') AS choice_made
  FROM cohort c LEFT JOIN app a ON a.af_id = c.af_id AND a.ts >= c.start_ts AND a.ts < TIMESTAMP_ADD(c.start_ts, INTERVAL 24 HOUR)
  GROUP BY 1, 2, 3),
ran_out AS (SELECT DISTINCT c.af_id FROM cohort c JOIN exh_dev d ON d.af_id = c.af_id AND d.ts >= c.start_ts AND d.ts < TIMESTAMP_ADD(c.start_ts, INTERVAL 24 HOUR))
SELECT s.cfg, s.install_date, COUNT(*) AS installs,
  COUNTIF(s.home_shown) AS home_shown, COUNTIF(s.story_started) AS story_started, COUNTIF(s.choice_made) AS first_choice_made,
  COUNTIF(s.clip_played) AS first_clip_played, COUNTIF(s.choice_shown) AS first_choice_shown,
  COUNTIF(r.af_id IS NOT NULL) AS ran_out_of_energy
FROM steps s LEFT JOIN ran_out r USING (af_id)
GROUP BY 1, 2 ORDER BY 1, 2
