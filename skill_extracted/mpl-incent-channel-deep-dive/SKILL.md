---
name: mpl-incent-channel-deep-dive
description: "How to analyze MPL incent marketing channel quality by combining spend, D7 depositor conversion, D7 level-21+ progression, and D7 ROAS, optionally sliced by campaign category (Bingo/Solitaire/GinRummy or any other) and sub-source (af_siteid). Use this skill whenever the user asks to review incent channels, compare incent source quality, investigate scale-down or scale-up effects on incent channels, build a channel deep-dive dashboard, analyze each of the incent channels individually, look at af_siteid / vc-* sub-source performance, or compute weekly D7 ROAS by incent channel. Also trigger when the user mentions \"incent quality review\", \"which incent channels should we scale\", \"why is this channel's quality dropping\". This is the authoritative recipe — do not improvise from scratch."
---

# MPL Incent Channel Deep Dive

Canonical workflow to assess whether an incent spend decision (scale-up, scale-down, turn off, shift category) is healthy or costly. Measures four orthogonal signals per channel × week: how much we spent, how many logins we got, how quickly those users convert to depositors, how far they progress in levels, and how much D7 revenue came back per dollar spent.

## When to use this skill

Trigger on any request about:
- Reviewing or comparing incent channel quality (InboxDollars, MyAppFree, FreeCash, AdAction, KashKick)
- Scale-up/down decisions: "did we lose good volume", "did the cut improve quality"
- Sub-source (`af_siteid`, `vc-*`) or campaign-category (Bingo/Solitaire/GinRummy) drilldowns
- Building or updating the incent dashboard (`incent_dashboard_v*.html`)
- Any question combining spend + user quality on incent channels

Do NOT use for: non-incent channels (programmatic DSPs like Moloco/Applovin/Liftoff/Smadex are NOT incent), Blastplus/Scarfall (MPL-only workflow), or pure level-progression metrics (use `mpl-cohort-level-progression` skill instead).

## Universe — any channel tagged under incent channel type

example
```
inboxdollars_int   -- campaign keyword: "inboxdollar" (singular, not plural!)
myappfre_int       -- campaign keyword: "myappfre"
freecash_int       -- campaign keyword: "freecash"
adaction5_int      -- campaign keyword: "adaction"
kashkick_int       -- campaign keyword: "kashkick"
```

Programmatic DSPs (applovin, moloco, liftoff, smadex) are **not** incent and must not be included unless the user explicitly asks for a broader DSP comparison.

## Country scope

US-only by default. Never mix with BR without explicit ask — incent sources and user quality signals differ structurally between markets.

## The four metrics — definitions

Every channel × week (and optionally × category or × siteid) row carries these:

### 1. Spend

Source: `mpl-prod-data.dw_silver.marketing_spends_fat`.

The spend table has **no `media_source` column** — channel must be inferred from `campaign_name` via keyword match using the patterns above. The full campaign naming convention is `mcspapac_Mplus(-SL)_<Channel>_<Category>_<OS>_<Incent>_<Goal>_MF18_<Country>_<date>`, so the 4th underscore-separated token is the **category** (Bingo, Solitaire, GinRummy).

InboxDollars naming gotcha: campaigns use the singular form `Inboxdollar` (matches LIKE `'%inboxdollar%'`), not `inboxdollars`. This caught me out once.

### 2. D7 Dep CVR — depositor conversion

Share of **all logins** (NOT just Player logins) that made a deposit within D0-D7 (inclusive) of the login date.

```
d7_dep_cvr = COUNT(logins where dep IS NOT NULL AND dep_date - login_date ∈ [0, 7])
           / COUNT(all logins)
```

**MANDATE — denominator scope (set 2026-05):** Dep CVR is computed over the **full login cohort with no `user_type` filter**, because depositor activity meaningfully includes users who never reach Player gameplay state in the window. Filtering to `user_type LIKE '%Player%'` overstates CVR by ~2-4 pp (it drops the "Rest" cohort denominator without dropping the small number of those who deposit). The Lvl>20 metric is the only one that uses the Player filter — see Metric 3.

Sourced from `fact_login_channels_revenue.dep` (non-NULL = deposited) and `.dep_date`. Deposit window is **through end of D7, 8 days inclusive** — same as the level window. Earlier iterations used `BETWEEN 0 AND 6`, which was wrong; always use `BETWEEN 0 AND 7`.

### 3. D7 Level > 20 % — level progression

Share of **player logins** that reached level 21+ within 7 days of login. **MANDATE — Lvl>20 is the ONLY metric that uses `user_type LIKE '%Player%'` on the denominator.** Spend, Dep CVR, and ROAS all use the full login set with no user_type filter. Rely on the `mpl-cohort-level-progression` skill for the full definition. Key points:

- Denominator: `user_type LIKE '%Player%'` login rows (hard requirement, enforced)
- Numerator: `d7_max_level >= 21` (i.e. `> 20`)
- Level source: `dw_silver.user_level_up_fat` with `SELECT DISTINCT user_id, dt, level` pre-dedup
- Window: `[login_date, LEAST(login_date + 7, next_login_date - 1)]` — capped at next reinstall via the `next_login_date` column


### 4. D7 ROAS

Return on ad spend, D7 window, CM1-based.

```
d7_roas = SUM(d7_cm1) / SUM(spend) × 100     -- expressed as a percentage
```

- `d7_cm1` is on `fact_login_channels_revenue` directly; it's cumulative CM1 through day 7 since login. Can be negative (refunds, bonuses net of revenue).
- Spend comes from `marketing_spends_fat` for the same channel × category × week.
- When spend is 0 for a selection, show "—", not 0 — dividing by zero is meaningless and should not color the cell.
- Coloring convention for the table: ≥30% green, 10–30% neutral, <10% red.

Benchmark each of the above metric by calculating the exact metric definition at overall(platform) level i.e Including all the channels (organic as well)

## Campaign category derivation

Three meaningful categories based on campaign name keywords:

| Keyword in campaign name | Category |
|---|---|
| `bingo` | Bingo |
| `solitaire` | Solitaire |
| `ginrummy` | GinRummy |
| (anything else) | Other — keep for completeness, usually near-zero |

Apply this derivation **identically on both sides** — to `marketing_spends_fat.campaign_name` (spend side) and `fact_login_channels_revenue.campaign` (login side). Same regex, same fallback, so spend and logins roll up to the same category key.

## Sub-source (af_siteid) attribution

Some channels have meaningful sub-source structure:

- **AdAction**: numeric siteids (e.g. `329825370`, `329830666`) — these are offerwall providers / sub-publishers
- **MyAppFree**: siteids like `3739`, `2036`, `2615937` — publisher-level
- **InboxDollars**: `Prodege` (pre-Mar 23 2026) and `vc-*` codes (post-Mar 23). This is a provider reporting change, **not an acquisition event** — always annotate this in the dashboard
- **FreeCash**: single siteid, no useful breakdown
- **KashKick**: too small to break down

### Attribution logic

Logins carry `appsflyer_id` but not `af_siteid`. Pull siteid from `marketing_installs_fat` per `appsflyer_id + media_source`, taking the **latest non-null siteid per user** (ROW_NUMBER ... ORDER BY dt DESC, rn = 1). Look back at least 5–6 months to catch older reinstalls. Example:

```sql
installs_latest AS (
  SELECT appsflyer_id, media_source, af_siteid FROM (
    SELECT appsflyer_id, media_source, af_siteid, dt,
           ROW_NUMBER() OVER (PARTITION BY appsflyer_id ORDER BY dt DESC) AS rn
    FROM `mpl-prod-data.dw_silver.marketing_installs_fat`
    WHERE dt BETWEEN '<start-6mo>' AND '<end>'
      AND country_code = 'US'
      AND media_source IN (<incent list>)
      AND appsflyer_id IS NOT NULL
  ) WHERE rn = 1
)
```

Filter the dashboard's siteid table to siteids with ≥200 total player logins across the window — anything smaller is too noisy.

## Canonical query — channel × category × week rollup

The query has TWO login CTEs because the denominators differ: `logins_all` (no Player filter) feeds Dep CVR, reinstalls, and CM1; `logins_player` feeds Lvl>20 only. Joining them at the end on (week_start, media_source, category) gives one row per cell with both denominators preserved.

```sql
WITH incent_channels AS (
  SELECT media_source FROM UNNEST([
    'inboxdollars_int','myappfre_int','freecash_int','adaction5_int','kashkick_int'
  ]) AS media_source
),
-- ALL logins (no Player filter) → Dep CVR, reinstall %, CM1, ROAS
logins_all AS (
  SELECT
    f.user_id, f.login_date,
    DATE_TRUNC(f.login_date, WEEK(MONDAY)) AS login_week,
    f.media_source, f.install_type, f.dep, f.dep_date, f.d7_cm1,
    CASE
      WHEN LOWER(f.campaign) LIKE '%bingo%'     THEN 'Bingo'
      WHEN LOWER(f.campaign) LIKE '%solitaire%' THEN 'Solitaire'
      WHEN LOWER(f.campaign) LIKE '%ginrummy%'  THEN 'GinRummy'
      ELSE 'Other'
    END AS category
  FROM `mpl-prod-data.dw_gold.fact_login_channels_revenue` f
  WHERE f.dt BETWEEN '<start>' AND '<end>'
    AND f.country_code = 'US'
    AND f.media_source IN (SELECT media_source FROM incent_channels)
),
dep_metrics AS (
  SELECT
    login_week AS week_start, media_source, category,
    COUNT(*) AS logins_all,
    SUM(CASE WHEN install_type='reinstall' THEN 1 ELSE 0 END) AS reinstalls,
    SUM(CASE WHEN dep IS NOT NULL AND dep_date IS NOT NULL
              AND DATE_DIFF(dep_date, login_date, DAY) BETWEEN 0 AND 7
             THEN 1 ELSE 0 END) AS d7_deps,
    ROUND(SUM(COALESCE(d7_cm1, 0)), 2) AS d7_cm1_total
  FROM logins_all
  GROUP BY ALL
),
-- Player-only logins → Lvl>20 ONLY
logins_player AS (
  SELECT
    f.user_id, f.login_date, f.next_login_date,
    DATE_TRUNC(f.login_date, WEEK(MONDAY)) AS login_week,
    f.media_source,
    CASE
      WHEN LOWER(f.campaign) LIKE '%bingo%'     THEN 'Bingo'
      WHEN LOWER(f.campaign) LIKE '%solitaire%' THEN 'Solitaire'
      WHEN LOWER(f.campaign) LIKE '%ginrummy%'  THEN 'GinRummy'
      ELSE 'Other'
    END AS category
  FROM `mpl-prod-data.dw_gold.fact_login_channels_revenue` f
  WHERE f.dt BETWEEN '<start>' AND '<end>'
    AND f.country_code = 'US'
    AND f.media_source IN (SELECT media_source FROM incent_channels)
    AND f.user_type LIKE '%Player%'      -- ONLY here, never elsewhere
),
level_events AS (
  SELECT DISTINCT user_id, dt, SAFE_CAST(level AS INT64) AS lvl
  FROM `mpl-prod-data.dw_silver.user_level_up_fat`
  WHERE dt BETWEEN '<start>' AND DATE_ADD('<end>', INTERVAL 7 DAY)
    AND country_code = 'US'
),
windows AS (
  SELECT l.*,
    LEAST(
      DATE_ADD(l.login_date, INTERVAL 7 DAY),
      COALESCE(
        IF(l.next_login_date IS NOT NULL
           AND l.next_login_date <= DATE_ADD(l.login_date, INTERVAL 7 DAY),
           DATE_SUB(l.next_login_date, INTERVAL 1 DAY), NULL),
        DATE_ADD(l.login_date, INTERVAL 7 DAY)
      )
    ) AS window_end
  FROM logins_player l
),
with_level AS (
  SELECT
    w.login_week, w.media_source, w.category, w.user_id, w.login_date,
    MAX(le.lvl) AS d7_max_level
  FROM windows w
  LEFT JOIN level_events le
    ON le.user_id = w.user_id
   AND le.dt BETWEEN w.login_date AND w.window_end
  GROUP BY ALL
),
lvl_metrics AS (
  SELECT
    login_week AS week_start, media_source, category,
    COUNT(*) AS logins_player,
    COUNTIF(d7_max_level > 20) AS d7_lvl_gt20
  FROM with_level
  GROUP BY ALL
),
spend AS (
  SELECT
    DATE_TRUNC(dt, WEEK(MONDAY)) AS week_start,
    CASE
      WHEN LOWER(campaign_name) LIKE '%inboxdollar%' THEN 'inboxdollars_int'
      WHEN LOWER(campaign_name) LIKE '%myappfre%'    THEN 'myappfre_int'
      WHEN LOWER(campaign_name) LIKE '%freecash%'    THEN 'freecash_int'
      WHEN LOWER(campaign_name) LIKE '%adaction%'    THEN 'adaction5_int'
      WHEN LOWER(campaign_name) LIKE '%kashkick%'    THEN 'kashkick_int'
    END AS media_source,
    CASE
      WHEN LOWER(campaign_name) LIKE '%bingo%'     THEN 'Bingo'
      WHEN LOWER(campaign_name) LIKE '%solitaire%' THEN 'Solitaire'
      WHEN LOWER(campaign_name) LIKE '%ginrummy%'  THEN 'GinRummy'
      ELSE 'Other'
    END AS category,
    ROUND(SUM(spends), 2) AS spend
  FROM `mpl-prod-data.dw_silver.marketing_spends_fat`
  WHERE dt BETWEEN '<start>' AND '<end>'
    AND country_code = 'US'
    AND (LOWER(campaign_name) LIKE '%inboxdollar%'
      OR LOWER(campaign_name) LIKE '%myappfre%'
      OR LOWER(campaign_name) LIKE '%freecash%'
      OR LOWER(campaign_name) LIKE '%adaction%'
      OR LOWER(campaign_name) LIKE '%kashkick%')
  GROUP BY ALL
)
SELECT
  COALESCE(d.week_start, l.week_start, s.week_start)     AS week_start,
  COALESCE(d.media_source, l.media_source, s.media_source) AS media_source,
  COALESCE(d.category, l.category, s.category)           AS category,
  COALESCE(s.spend, 0)         AS spend,
  COALESCE(d.logins_all, 0)    AS logins_all,
  COALESCE(l.logins_player, 0) AS logins_player,
  COALESCE(d.reinstalls, 0)    AS reinstalls,
  COALESCE(d.d7_deps, 0)       AS d7_deps,
  COALESCE(l.d7_lvl_gt20, 0)   AS d7_lvl_gt20,
  COALESCE(d.d7_cm1_total, 0)  AS d7_cm1_total,
  ROUND(100 * SAFE_DIVIDE(d.d7_deps,    d.logins_all),    2) AS d7_dep_cvr_pct,
  ROUND(100 * SAFE_DIVIDE(l.d7_lvl_gt20, l.logins_player), 2) AS d7_lvl_gt20_pct,
  ROUND(100 * SAFE_DIVIDE(d.reinstalls, d.logins_all),    2) AS reinstall_pct,
  ROUND(100 * SAFE_DIVIDE(d.d7_cm1_total, s.spend),       1) AS d7_roas_pct
FROM dep_metrics d
FULL OUTER JOIN lvl_metrics l USING (week_start, media_source, category)
FULL OUTER JOIN spend       s USING (week_start, media_source, category)
WHERE COALESCE(d.media_source, l.media_source, s.media_source) IS NOT NULL
ORDER BY media_source, category, week_start
```

The `FULL OUTER JOIN` matters because some (channel, category, week) cells have spend but no logins yet (very recent) or logins but no current spend (historical tail).

## Siteid-weekly query (Panel IV data)

Same structure as the canonical query, but replace the `category` derivation with siteid attribution from `marketing_installs_fat`. The dual-cohort split (logins_all for Dep CVR, logins_player for Lvl>20) applies here too — both cohorts get joined to siteids the same way. Apply the ≥200-logins-over-window filter via an inner `HAVING` on a channel × siteid rollup to keep the dashboard clean. Use the **all-logins count** for the threshold so that channels with high non-Player traffic (e.g. heavy reinstaller siteids) are not unfairly excluded.

## Reading the dashboard — how to interpret

The dashboard structure is fixed by convention; follow this layout when rebuilding:

- **Panel I — Stacked spend by channel.** Quick "how much and where" across weeks.
- **Panel II — Two line charts side by side:** D7 Dep CVR and D7 Level > 20 %. Each channel is a colored line.
- **Panel III — Channel deep dive.** Chip-style channel selector + category dropdown (Overall/Bingo/Solitaire/GinRummy). Spend as shaded bars on left y-axis, Dep CVR and Lvl>20% as two lines on right y-axis, D7 ROAS as a third dashed line with its own (hidden) right axis.
- **Panel IV — Siteid drilldown.** Channel dropdown + metric dropdown. Only siteids with ≥200 logins across the window are shown.

### Diagnostic patterns to call out

- **Falling spend + falling quality** → scale-down was clean. Best outcome. Continued monitoring.
- **Falling spend + rising quality** → scale-down removed the worst volume first. Consider scaling back up selectively.
- **Flat spend + falling quality** → internal mix shift. The channel rerouted into worse inventory. Investigate siteid-level.
- **Rising spend + flat/falling quality** → wasted scale. Pull back.
- **Siteid volatility inside a channel** → the channel aggregate hides wildly different sub-sources. Always drill before making channel-level decisions.

### Known data quirks to annotate on every run

- **InboxDollars reporting change on 2026-03-23**: moved from single `Prodege` siteid to `vc-*` codes. Do not compare pre/post siteid-level metrics as acquisition events; this is a provider reporting change.
- **Partial week**: if the analysis includes a week that hasn't finished, either exclude it or mark it as partial. D7 windows are undefined for logins from the last 6 days.
- **User_level_up_fat duplication**: ~10x row duplication. Always pre-dedup with `SELECT DISTINCT user_id, dt, level`.

## Parameters that should be user-configurable

Whenever asked to rebuild or refresh the dashboard, confirm these choices with the user unless they carry over from context:

1. **Date range** — default last 13 full weeks, ending on the most recent completed week
2. **Channels in scope** — default all 5 incent channels; user may want to add/remove
3. **Country** — default US
4. **Level threshold** — default 21+ (i.e. `> 20`); user may want 10, 15, 30
5. **Dep window** — default D0–D7; avoid anything shorter without explicit ask
6. **ROAS flavor** — default D7 CM1 / Spend; user may prefer D7 GMV or D7 margin

## Output format

Prefer a standalone HTML dashboard (Chart.js) when the output will be shared; a structured query result when the user is iterating. For dashboards, follow the four-panel structure above and use the visual conventions encoded in `incent_dashboard_v4.html` (Fraunces + JetBrains Mono, black rule lines, subtle shaded bars for spend, dashed lines for secondary metrics). Never use the native Chart.js color defaults — use the channel palette: InboxDollars `#D64545`, MyAppFree `#E8A33D`, AdAction `#5B7FDB`, FreeCash `#4AAB7E`, KashKick `#9B59B6`.

## Common mistakes to avoid

- **Applying the Player filter to Dep CVR.** This was the original recipe, corrected 2026-05. The Player filter belongs ONLY on the Lvl>20 cohort. Putting it on Dep CVR's denominator drops "Rest" users (who can still deposit) from the bottom of the fraction, which inflates the published CVR by ~2-4 pp and pushes the platform benchmark from its true ~16-19% range up to ~19-22%, making channel-level CVRs look closer to platform than they really are.
- **Forgetting the Player filter on Lvl&gt;20.** Required on the Lvl>20 cohort. Skipping it drops the metric into the teens because non-gameplay "Rest" users flood the denominator.
- **`BETWEEN 0 AND 6` for the dep window.** Should be `BETWEEN 0 AND 7`. The level window is already through-D7; keep them consistent.
- **Using `inboxdollars` in the spend LIKE.** Campaign names use the singular `inboxdollar`. Matching on `inboxdollars` returns zero rows.
- **Joining spend by `media_source`.** `marketing_spends_fat` has no `media_source` column — infer from `campaign_name` keywords on both sides.
- **Forgetting `SELECT DISTINCT` on `user_level_up_fat`.** Numerator drifts non-deterministically across runs otherwise.
- **Dividing CM1 by spend when spend is 0.** Show "—" instead.
- **Reading the InboxDollars `vc-*` shift as an acquisition event.** It's a reporting change on Mar 23, 2026. Never compare pre/post at siteid level.
- **Using `fact_revenue_metrics_platform` for revenue here.** Stick with `d7_cm1` from `fact_login_channels_revenue` — it's already attributed to the login session.