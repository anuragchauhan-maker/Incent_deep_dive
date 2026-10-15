#!/usr/bin/env python3
"""Choices beta metrics dashboard: render SQL, then turn BigQuery results into the artifact's database documents.

  python3 build.py render RUN_DIR CUTOFF     # CUTOFF = 'YYYY-MM-DD HH:MM:SS' in IST; writes RUN_DIR/sql/*.sql
  python3 build.py build  RUN_DIR            # reads RUN_DIR/results/*.md and RUN_DIR/versions/*.txt; writes RUN_DIR/out/batch_*.json

results/<id>.md   = the bq_run_query tool output pasted verbatim (markdown table + "Job ID: `...`").
versions/<c>.txt  = the ArtifactData "list" output for collection <c> (lines like '- "m01"  1434 bytes  version 11 ...').
"""
import datetime as dt, glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
QUERIES = ['q13', 'q7', 'q14', 'q15', 'q5', 'q10', 'qc1', 'qc2']
FIRST_DAY = dt.date(2026, 10, 8)

# SQL tab cards: static text only (numbers live in the result rows)
CARDS = {
  'q13': dict(order=1, title='Q13 · Daily L0, all columns and filters',
    feeds='Daily L0: every column, the chart, and the Launch config and Energy filters (Energy spent on All x All comes from Q7)',
    note='One query for every Daily L0 column and filter. Filter segments match the Cohorts tab: launch config from bp_tutorial_start (installs from 13 Oct onwards); Energy = ever ran out by the cut-off. Filtered Energy spent counts spends credited to a device, so segments can add up to slightly less than the All total. The last day is partial.'),
  'q7': dict(order=2, title='Q7 · Energy spent (L0)', feeds='Daily L0: Energy spent (Android), All x All row',
    note='Spends by accounts never seen in Android app events (likely iOS) are excluded and shown in excluded_other.'),
  'q14': dict(order=3, title='Q14 · Story table: players making N choices',
    feeds="Funnels › Story funnel table (dates across, metrics down) and its 'All days' column",
    note="Counts players, not plays. Choices are added up across a player's visits to the story that day, so a resume doesn't restart the count."),
  'q15': dict(order=4, title='Q15 · Retention by first story', feeds='Funnels › Retention by first story',
    note="No AppsFlyer needed: the first story is the device's earliest bp_match_start. The page counts a player in D1, D3 or D7 only once that day has finished."),
  'q5': dict(order=5, title='Q5 · After an ending', feeds='Funnels › After an ending',
    note='An ending counts only once its whole 24h or 72h follow-up window has closed.'),
  'q10': dict(order=6, title='Q10 · Onboarding and first 24 hours', feeds='Funnels › Onboarding and First 24 hours (home-first and story-first)',
    note='Installs from bp_install with a launch config. Recent installs have not had a full 24 hours yet.'),
  'qc1': dict(order=7, title='QC1 · Install cohorts by day (Cohorts tab)', feeds='Cohorts tab: D0–D14 table (every metric in the dropdown) and every filter',
    note='AppsFlyer installs only (reinstalls excluded). The 9 and 10 Oct installs never sent an app event, so their rows stay at zero.'),
  'qc2': dict(order=8, title='QC2 · Cohort activation (Cohorts tab)', feeds='Cohorts tab: Activation table',
    note='Cohort, filters and Energy crediting exactly as QC1. Medians are exact.'),
}

D = dt.date.fromisoformat
def ist_label(cutoff): return dt.datetime.fromisoformat(cutoff).strftime('%-d %b %H:%M')

# ---------- render ----------
def render(run, cutoff):
    today = cutoff[:10]
    os.makedirs(f'{run}/sql', exist_ok=True); os.makedirs(f'{run}/results', exist_ok=True); os.makedirs(f'{run}/versions', exist_ok=True)
    t = D(today)
    frm = max(FIRST_DAY, t - dt.timedelta(days=14)).isoformat()        # Daily L0 / story table / Energy: last 14 days (older days are stored)
    cohort_frm = (t - dt.timedelta(days=14)).isoformat()                # cohorts still inside their D0..D14 window
    for q in QUERIES:
        s = (open(f'{HERE}/sql/{q}.sql').read().replace('{{CUTOFF}}', cutoff).replace('{{TODAY}}', today)
             .replace('{{COHORT_FROM}}', cohort_frm).replace('{{FROM}}', frm))
        assert '{{' not in s, (q, 'unfilled placeholder')
        open(f'{run}/sql/{q}.sql', 'w').write(s)
    json.dump({'cutoff': cutoff, 'today': today}, open(f'{run}/run.json', 'w'))
    print('rendered', len(QUERIES), 'queries for cut-off', cutoff, 'IST into', run + '/sql')

# ---------- parse ----------
def cell(c):
    c = c.strip()
    if c in ('NULL', 'None', ''): return None
    if c in ('true', 'True'): return True
    if c in ('false', 'False'): return False
    if re.fullmatch(r'-?\d+', c): return int(c)
    if re.fullmatch(r'-?\d+\.\d+(e-?\d+)?', c): return float(c)
    return c

def parse_md(path):
    txt = open(path).read()
    if '\\n' in txt and '\n|' not in txt:  # pasted as a JSON string
        try: txt = json.loads(txt)['result']
        except Exception: txt = txt.encode().decode('unicode_escape')
    job = re.search(r'Job ID: `([^`]+)`', txt)
    lines = [l for l in txt.split('\n') if l.strip().startswith('|')]
    if 'Query returned no rows' in txt or not lines:
        return {'job_id': job.group(1) if job else None, 'columns': [], 'rows': []}
    cols = [c.strip() for c in lines[0].strip().strip('|').split('|')]
    rows = [[cell(c) for c in l.strip().strip('|').split('|')] for l in lines[2:]]
    for r in rows: assert len(r) == len(cols), (path, r)
    return {'job_id': job.group(1) if job else None, 'columns': cols, 'rows': rows}

def recs(res): return [dict(zip(res['columns'], r)) for r in res['rows']]

def versions(run):
    v = {}
    if os.path.exists(f'{run}/versions.json'): v.update(json.load(open(f'{run}/versions.json')))
    for f in glob.glob(f'{run}/versions/*.txt'):
        coll = os.path.basename(f)[:-4]
        for m in re.finditer(r'- "([^"]+)"\s+\d+ bytes\s+version (\d+)', open(f).read()):
            v[f'{coll}/{m.group(1)}'] = int(m.group(2))
    return v

# ---------- build ----------
def build(run):
    meta = json.load(open(f'{run}/run.json')); cutoff, today = meta['cutoff'], D(meta['today'])
    last_full = today - dt.timedelta(days=1)
    R = {q: parse_md(f'{run}/results/{q}.md') for q in QUERIES}
    docs = {}  # 'collection/doc_id' -> data

    def status(idate, n):
        t = D(idate) + dt.timedelta(days=n)
        return 'complete' if t <= last_full else ('so_far' if t == today else 'not_yet')

    # Daily L0
    q7 = {r['date']: r['energy_spent'] for r in recs(R['q7'])}
    first_backend = min((d for d, v in q7.items() if v is not None), default=None)
    l0 = {}
    for x in recs(R['q13']):
        d = x['date']
        doc = l0.setdefault(d, {'date': d, 'cuts': {}})
        c = {k: x[k] for k in ['dau', 'new_dau', 'returning_dau', 'wau', 'sdau', 'cdau', 'choices', 'branches', 'sessions', 'story_starts',
                               'story_completions', 'watch_min', 'energy_spent', 'exhausted_users', 'p75_latency_ms', 'p75_seam_ms', 'rebuffer_pct']}
        inst = x['installs']; s1, s7 = status(d, 1), status(d, 7)
        c.update(installs=inst, d1_status=s1, d7_status=s7,
                 d1_ret=round(100 * x['d1_launch'] / inst, 2) if inst and s1 != 'not_yet' else None,
                 d1_cdau_ret=round(100 * x['d1_choice'] / inst, 2) if inst and s1 != 'not_yet' else None,
                 d7_ret=round(100 * x['d7_launch'] / inst, 2) if inst and s7 != 'not_yet' else None)
        if first_backend is None or d < first_backend: c['energy_spent'] = None; c['exhausted_users'] = None
        if x['cfg'] == 'all' and x['energy'] == 'all': c['energy_spent'] = q7.get(d)
        doc['cuts'].setdefault(x['cfg'], {})[x['energy']] = c
    for d, doc in l0.items():
        if D(d) == today: doc.update(partial=True, partial_note='Events up to ' + cutoff[11:16] + ' IST')
        else: doc['partial'] = False
        docs[f'l0_daily/{d}'] = doc

    # Cohorts
    act = {}
    for a in recs(R['qc2']):
        act[(a['install_date'], a['launch_config'], a['energy_filter'], a['campaign'])] = {k: a[k] for k in [
            'installs', 'story_start_users', 'first_choice_users', 'exhausted_d0_users', 'median_min_to_choice', 'median_d0_choices',
            'median_first_session_choices', 'median_first_session_min']}
    coh = {}
    dk = ['dau', 'sdau', 'cdau', 'choices', 'energy', 'stories_started', 'stories_completed', 'watch_min', 'exhausted', 'ever_exhausted']
    for r in recs(R['qc1']):
        key = (r['install_date'], r['launch_config'], r['energy_filter'], r['campaign'])
        doc = coh.setdefault(r['install_date'], {'install_date': r['install_date'], 'cuts': {}})
        cut = doc['cuts'].setdefault(key[1], {}).setdefault(key[2], {}).setdefault(key[3], {'days': [], 'activation': act.get(key)})
        for arr in json.loads(r['days']):  # one row per cohort x filter; days packed as [day_n, *dk]
            arr = [int(v) if float(v).is_integer() else v for v in arr]
            n = arr[0]
            while len(cut['days']) <= n: cut['days'].append(None)
            cut['days'][n] = dict(zip(dk, arr[1:]))
    for idate, doc in coh.items():
        doc['age_days'] = (today - D(idate)).days
        doc['partial'] = doc['age_days'] <= 14
        docs[f'cohorts/{idate}'] = doc

    # Funnels
    onb = {'home': {'steps': ['Home shown', 'Story started', 'First choice made'], 'rows': []},
           'story': {'steps': ['Story start', 'First choice made'], 'rows': []}}
    a24 = {c: {'steps': ['Story start', 'First clip played', 'First choice shown', 'First choice made', 'Ran out of Energy'], 'rows': []} for c in ('home', 'story')}
    for r in recs(R['q10']):
        if r['cfg'] not in onb: continue
        onb[r['cfg']]['rows'].append({'date': r['install_date'], 'installs': r['installs'],
            'steps': ([r['home_shown']] if r['cfg'] == 'home' else []) + [r['story_started'], r['first_choice_made']]})
        a24[r['cfg']]['rows'].append({'date': r['install_date'], 'installs': r['installs'],
            'steps': [r['story_started'], r['first_clip_played'], r['first_choice_shown'], r['first_choice_made'], r['ran_out_of_energy']]})
    st = {}
    for r in recs(R['q14']):
        st.setdefault(r['story'], []).append({'date': r['date'], 'play_starts': r['play_starts'], 'new_starts': r['new_starts'], 'players': r['players'],
            'at_least': [r[f'c{i}'] for i in range(1, 9)], 'at_least_10': r['c10'], 'complete': r['complete_players']})
    ae = recs(R['q5'])[0]
    first_72 = None
    aed = {'complete_players': ae['complete_players_24h_eligible'], 'next_story_24h': ae['next_story_24h'],
           'incomplete_players': ae['incomplete_players'], 'tree_open_24h': ae['tree_open_24h']}
    if 'next_story_72h' in ae and ae['complete_players_72h_eligible']:
        aed['next_story_72h'] = ae['next_story_72h']; aed['complete_players_72h'] = ae['complete_players_72h_eligible']
    else:
        aed['next_story_72h'] = None
        aed['complete_note'] = 'Within 72h: no complete ending is 72h old yet.'
    docs['funnels/last_14d'] = {
        'window_label': f"Live data, Android only, events up to {ist_label(cutoff)} IST (the last day is partial). Onboarding and first 24 hours: devices with the SDK install event (bp_install) and a launch config (installs from 13 Oct). Story table: players (devices) who started that story that day. 'Login success' is left out until it is defined.",
        'onboarding_daily': onb, 'activation_daily': a24,
        'story_table': [{'story': k, 'rows': v} for k, v in sorted(st.items())],
        'stories': [{'story': k, 'abandoned_by_choice': [], 'abandoned_at_zero_energy': []} for k in sorted(st)],
        'after_ending': aed,
        'story_retention': {'last_full_day': last_full.isoformat(), 'rows': recs(R['q15'])},
        'catalogue_daily': [],
    }

    # Meta
    docs['meta/status'] = {'is_demo': False, 'last_refreshed': cutoff.replace(' ', 'T') + '+05:30', 'latest_date': today.isoformat(),
        'refresh_note': f'Events up to {ist_label(cutoff)} IST (the last day is partial). App metrics are Android only.',
        'refresh_status': 'ok', 'source': 'BigQuery raw_events, refreshed by the daily scheduled task (see the SQL tab)',
        'tracker_checked': '14 Oct 2026, against app build 3 and 4 data from 8–14 Oct'}

    # SQL tab cards
    for q in QUERIES:
        c = CARDS[q]
        docs[f'queries/{q}'] = dict(id=q, kind='metric', used_on_page=True, order=c['order'], title=c['title'], feeds=c['feeds'], note=c['note'],
            sql=open(f'{run}/sql/{q}.sql').read(), job_id=R[q]['job_id'], ran_at=f'{ist_label(cutoff)} IST cut-off',
            columns=R[q]['columns'], rows=R[q]['rows'])

    # Sanity checks: refuse to write an obviously broken refresh
    assert any(d == last_full.isoformat() for d in l0), 'no Daily L0 row for yesterday'
    assert l0[last_full.isoformat()]['cuts']['all']['all']['dau'] > 0, 'yesterday has 0 DAU'
    assert st, 'story table is empty'

    # Batches (pinned to the versions just listed; new docs unpinned)
    ver = versions(run)
    os.makedirs(f'{run}/out', exist_ok=True)
    for f in glob.glob(f'{run}/out/*'): os.remove(f)
    writes = []
    for key, data in docs.items():
        coll, doc_id = key.split('/')
        p = os.path.abspath(f'{run}/out/{coll}__{doc_id}.json'); json.dump(data, open(p, 'w'))
        w = {'op': 'set', 'collection': coll, 'doc_id': doc_id, 'file_path': p}
        if key in ver: w['if_version'] = ver[key]
        writes.append(w)
    batches = [writes[i:i + 45] for i in range(0, len(writes), 45)]
    for i, b in enumerate(batches, 1): json.dump(b, open(f'{run}/out/batch_{i}.json', 'w'), indent=1)
    y = l0[last_full.isoformat()]['cuts']['all']['all']
    print(f'{len(writes)} writes in {len(batches)} batch(es) -> {run}/out/batch_*.json')
    print(f"yesterday ({last_full}): DAU {y['dau']} (new {y['new_dau']}), choices {y['choices']}, story starts {y['story_starts']}, D1 so far for {last_full}: {y['d1_ret']}")
    missing = [k for k in docs if k not in ver and not k.startswith(('l0_daily/', 'cohorts/'))]
    if missing: print('WARNING: no listed version for', missing, '- list those collections again if the batch is refused')

if __name__ == '__main__':
    if sys.argv[1] == 'render': render(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == 'build': build(sys.argv[2])
    else: sys.exit(__doc__)
