import csv, json, collections
WK=['07-27','08-03','08-10','08-17','08-24','08-31','09-07','09-14']
P4=WK[:4]; L4=WK[4:]; LAT='09-14'; PREV='09-07'
ch=list(csv.DictReader(open('channel.csv')))
for r in ch:
    for k in ['spend','la','lp','ri','dep','l20','cm1']: r[k]=float(r[k])
plat=list(csv.DictReader(open('platform.csv')))
for r in plat:
    for k in r:
        if k!='wk': r[k]=float(r[k])
sid=[]
for line in open('siteid.txt'):
    p=line.split(); sid.append(dict(wk=p[0],ch=p[1],sid=p[2],cat=p[3],la=float(p[4]),lp=float(p[5]),dep=float(p[6]),l20=float(p[7]),cm1=float(p[8])))
# channel x cat x wk totals for allocation
cc=collections.defaultdict(lambda: dict(spend=0,la=0))
for r in ch:
    cc[(r['ch'],r['cat'],r['wk'])]['spend']+=r['spend']; cc[(r['ch'],r['cat'],r['wk'])]['la']+=r['la']
for r in sid:
    c=cc[(r['ch'],r['cat'],r['wk'])]
    r['spend']= c['spend']*r['la']/c['la'] if c['la'] else 0
def agg(rows,weeks,keys=('spend','la','lp','dep','l20','cm1','ri')):
    o={k:0 for k in keys}
    for r in rows:
        if r['wk'] in weeks:
            for k in keys: o[k]+=r.get(k,0)
    return o
def met(o):
    d=lambda a,b: (100*a/b) if b else None
    return dict(spend=o['spend'],la=o['la'],dep=d(o['dep'],o['la']),l20=d(o['l20'],o['lp']),roas=d(o['cm1'],o['spend']) if o['spend'] else None,
                ri=d(o.get('ri',0),o['la']) if 'ri' in o else None,cpl=(o['spend']/o['la'] if o['la'] and o['spend'] else None),cm1pl=(o['cm1']/o['la'] if o['la'] else None))
def pm(weeks):
    o=dict(la=0,dep=0,cm1=0,lp=0,l20=0)
    for r in plat:
        if r['wk'] in weeks:
            for k in o:o[k]+=r[k]
    return dict(dep=100*o['dep']/o['la'],l20=100*o['l20']/o['lp'],cm1pl=o['cm1']/o['la'],la=o['la'])
out={}
out['platform']={n:pm(w) for n,w in [('L4',L4),('P4',P4),('LAT',[LAT]),('PREV',[PREV])]}
out['platform_weekly']=[dict(wk=r['wk'],dep=100*r['dep']/r['la'],l20=100*r['l20']/r['lp'],cm1pl=r['cm1']/r['la'],la=r['la']) for r in plat]
def f(x,n=1): return '—' if x is None else f'{x:.{n}f}'
buckets=[('L4',L4),('P4',P4),('LAT',[LAT]),('PREV',[PREV])]
# channel level
chs=sorted(set(r['ch'] for r in ch)); out['channels']={}
for c in chs+['ALL']:
    rows=[r for r in ch if ((c=='ALL' and r['ch']!='freecash') or r['ch']==c)]
    out['channels'][c]={n:met(agg(rows,w)) for n,w in buckets}
    out['channels'][c]['weekly']=[dict(wk=w,**met(agg(rows,[w]))) for w in WK]
out['channel_cat']={}
for c in chs:
    for cat in ['Bingo','Solitaire']:
        rows=[r for r in ch if r['ch']==c and r['cat']==cat]
        if rows: out['channel_cat'][f'{c}|{cat}']={n:met(agg(rows,w)) for n,w in buckets}
# siteid
keys=sorted(set((r['ch'],r['sid']) for r in sid)); out['siteids']=[]
P=out['platform']
for (c,s) in keys:
    rows=[r for r in sid if r['ch']==c and r['sid']==s]
    d=dict(ch=c,sid=s)
    for n,w in buckets: d[n]=met(agg(rows,w))
    d['weekly']=[dict(wk=w,**met(agg(rows,[w]))) for w in WK]
    d['cats']={}
    for cat in ['Bingo','Solitaire','Other']:
        cr=[r for r in rows if r['cat']==cat]
        if cr: d['cats'][cat]={n:met(agg(cr,w)) for n,w in buckets}
    out['siteids'].append(d)
# classification (relative to incent blended ROAS ex-freecash, since all incent D7 ROAS << 30% benchmark)
avg=out['channels']['ALL']['L4']['roas']; out['incent_avg_roas']=avg
pd_,pl_=P['L4']['dep'],P['L4']['l20']
CAMP={('adaction5','Bingo'):'Adaction_Bingo_IOS (26052025)',('adaction5','Solitaire'):'Adaction_Solitaire_IOS SL (29102025)',
('inboxdollars','Bingo'):'Inboxdollar_Bingo_IOS (23062025)',('inboxdollars','Solitaire'):'Inboxdollar_Solitaire_IOS SL (04112025)',
('myappfre','Bingo'):'myappfree_MPL_Bingo_iOS (30072026)',('myappfre','Solitaire'):'myappfree_MPL_Solitaire_iOS (30072026)',('freecash','Bingo'):'Freecash (no spend mapped)',('freecash','Other'):'Freecash (no spend mapped)'}
for d in out['siteids']:
    L=d['L4'];Pv=d['P4'];T=d['LAT']
    d['campaigns']=[CAMP[(d['ch'],c)] for c,x in d['cats'].items() if x['L4']['la']>=30 or x['PREV']['la']>=30 and (d['ch'],c) in CAMP]
    if d['ch']=='freecash':
        d['verdict']='HOLD';d['reason']='No spend mapped (campaign naming) so D7 ROAS is not computable. Quality is weak: Lvl20 %s%% vs platform %s%%, CM1/login $%s vs incent $0.9. Ramped from 08-31 (%d logins in L4). Do not scale until spend is mapped.'%(f(L['l20']),f(pl_),f(L['cm1pl'],2),L['la']);continue
    if (L['la']+Pv['la'])>=150 and T['la']<=5:
        better = (L['roas'] or 0)>=avg
        d['verdict']='PAUSED';d['reason']='Traffic fell to %d logins in latest week (was %d in prior wk). L4 est ROAS %s%% on %d logins, %s incent avg %s%%.'%(T['la'],d['weekly'][-2]['la'],f(L['roas'],0),L['la'],'above' if better else 'below',f(avg,1))
        d['verdict']='PAUSED – REVIVE?' if better else 'PAUSED – KEEP OFF'
        if L['la']==0: d['verdict']='INACTIVE';d['reason']='No traffic in L4. P4 est ROAS %s%% on %d logins.'%(f(Pv['roas'],0),Pv['la'])
        continue
    if L['la']<100:
        d['verdict']='LOW VOL';d['reason']='Only %d logins in L4 (too noisy to act); est ROAS %s%%.'%(L['la'],f(L['roas'],0));continue
    r=L['roas'] or 0; tr=T['roas']
    dep_ok=L['dep']>=pd_*0.95
    if r>=1.3*avg and dep_ok and (tr or 0)>=avg: v='SCALE UP'
    elif r>=0.95*avg and L['dep']>=pd_ and L['l20']>=pl_ and (Pv['roas'] or 0)<r: v='SCALE UP'
    elif r<0.75*avg: v='SCALE DOWN'
    elif r<avg and L['dep']<pd_ and L['l20']<0.8*pl_: v='SCALE DOWN'
    elif r>=1.3*avg: v='HOLD (watch)'
    else: v='HOLD'
    if L['la']<150 and v=='SCALE UP': v='TEST SCALE'
    d['verdict']=v
    d['reason']='L4 est ROAS %s%% (P4 %s%%, latest wk %s%%) vs incent avg %s%%; Dep %s%% vs plat %s%%; Lvl20 %s%% vs plat %s%%; %d logins.'%(f(L['roas'],1),f(Pv['roas'],1),f(tr,1),f(avg,1),f(L['dep']),f(pd_),f(L['l20']),f(pl_),L['la'])
json.dump(out,open('results.json','w'),indent=1)
print('PLATFORM',{k:{a:round(b,2) for a,b in v.items()} for k,v in P.items()})
print()
for c,v in out['channels'].items():
    print(c)
    for n in ['L4','P4','LAT','PREV']:
        m=v[n];print('  ',n,{k:(round(x,1) if x is not None else None) for k,x in m.items()})
print()
for k,v in out['channel_cat'].items():
    print(k,'L4',{a:(round(b,1) if b is not None else None) for a,b in v['L4'].items()},'P4 roas',v['P4']['roas'] and round(v['P4']['roas']),'LAT roas',v['LAT']['roas'] and round(v['LAT']['roas']),'spendL4/P4/LAT',round(v['L4']['spend']),round(v['P4']['spend']),round(v['LAT']['spend']))
print()
for d in out['siteids']:
    cats={c:(int(x['L4']['la']),f(x['L4']['roas'],0)) for c,x in d['cats'].items()}
    print(d['ch'],d['sid'],d['verdict'],'|',d['reason'],'|',cats,d['campaigns'])
