-- Q7 · Daily L0, "All" cut: Energy spent (Android players)
-- Backend bp_balance_update (service_name = 'choices-backend-api'), reason = 'spend'. Energy = SUM(-delta).
-- Counts a spend if its app_user_id appears on any Android app event (backend events carry af_id = 'not-set').
-- Spends by accounts never seen in app events (likely iOS) are excluded (excluded_other). 8 Oct is NULL: no backend balance events yet.
-- Events up to the cut-off ({{CUTOFF}} IST; the last day is partial).
WITH ev AS (
  SELECT event_id, event_type, event_date, service_name, app.version AS ver,
    (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key='app_user_id') AS app_user_id,
    (SELECT p.string_value FROM UNNEST(event_props) p WHERE p.key='reason') AS reason,
    (SELECT p.int_value FROM UNNEST(event_props) p WHERE p.key='delta') AS delta
  FROM `choices-prod-data.choices_dev_sdk_base.raw_events`
  WHERE event_date >= DATE '2026-10-01' AND event_timestamp <= TIMESTAMP('{{CUTOFF}}', 'Asia/Kolkata')
  QUALIFY ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY event_timestamp) = 1),
android_users AS (SELECT DISTINCT app_user_id FROM ev WHERE ver IS NOT NULL AND app_user_id IS NOT NULL),
backend AS (SELECT * FROM ev WHERE event_type='bp_balance_update' AND service_name='choices-backend-api'),
days AS (SELECT d AS date FROM UNNEST(GENERATE_DATE_ARRAY(DATE '{{FROM}}', DATE '{{TODAY}}')) AS d),
spend AS (SELECT b.event_date AS date, SUM(IF(a.app_user_id IS NOT NULL, -b.delta, 0)) AS energy_spent, SUM(IF(a.app_user_id IS NULL, -b.delta, 0)) AS excluded_other
  FROM backend b LEFT JOIN android_users a USING (app_user_id) WHERE b.reason = 'spend' GROUP BY 1)
SELECT days.date, IF(days.date < (SELECT MIN(event_date) FROM backend), NULL, IFNULL(spend.energy_spent, 0)) AS energy_spent, IFNULL(excluded_other,0) excluded_other
FROM days LEFT JOIN spend USING (date) ORDER BY 1
