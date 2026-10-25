import sys, json; sys.path.insert(0,'.')
from verdict import *
SHORT={'A1':'Solitaire iOS · 29102025'}
def lab(c):
    n=c
    return n
def r1(x): return None if x is None else round(x,2)
def mm(m): return {k:r1(v) for k,v in m.items()}
chs=['InboxDollars','MyAppFree','AdAction','FreeCash']
D={'weeks':W,'siteweeks':SW,'chan':{},'plat':[],'periods':{}}
for p in PLAT:
    D['plat'].append(dict(wk=p[0],cvr=r1(100*p[3]/p[1]),lvl=r1(100*p[4]/p[2]),roas=r1(100*p[5]/p[6]),spend=p[6]))
for nm,wk in [('P4',P4),('L4',L4),('PREV',[PREV]),('LAST',[LAST])]: D['periods'][nm]=mm(platm(wk))
for c in chs:
    rows=[r for r in CH if r[1]==c]
    d={'cat':{},'weekly':[]}
    for cat in ['Overall','Bingo','Solitaire']:
        rr=rows if cat=='Overall' else [r for r in rows if r[2]==cat]
        if not rr: continue
        wk=[]
        for w in W:
            m=met(agg(rr,[w])); wk.append(dict(wk=w,**mm(m)))
        d['cat'][cat]=wk
    d['periods']={nm:mm(met(agg(rows,wk))) for nm,wk in [('P4',P4),('L4',L4),('PREV',[PREV]),('LAST',[LAST])]}
    D['chan'][c]=d
# siteids
chroas={c:chan_roas(c,L4) for c in chs}
sites=[]
for r in build():
    r['verdict']=verdict(r['L4']['cvr'],r['L4']['lvl'],r['L4']['roas'] or 0,r['L4']['logins'],chroas[r['channel']])
    r['active']=r['L4']['logins']>=20
    if r['L4']['logins']<20 and r['verdict']=='WATCH': r['verdict']='DORMANT'
    sites.append(dict(channel=r['channel'],site=r['site'],verdict=r['verdict'],
        L4=mm(r['L4']),P4=mm(r['P4']),LAST=mm(r['LAST']),PREV=mm(r['PREV']),weekly=[mm(w) for w in r['weekly']]))
D['sites']=sites
sv={(s['channel'],s['site']):s['verdict'] for s in sites}
camps=[]
for c in campaign_rows():
    if c['L4']['logins']<40: continue
    sver=sv[(c['channel'],c['site'])]; cv=c['verdict']
    if sver=='SCALE DOWN': act='SCALE DOWN' if (cv=='SCALE DOWN' or (c['L4']['roas'] or 0)<5.5) else 'HOLD'
    elif sver=='SCALE UP': act='SCALE UP' if cv=='SCALE UP' else 'HOLD'
    else: act='SCALE DOWN' if cv=='SCALE DOWN' else 'HOLD'
    camps.append(dict(channel=c['channel'],site=c['site'],camp=c['camp'],cat=c['cat'],action=act,site_verdict=sver,L4=mm(c['L4']),P4=mm(c['P4']),LAST=mm(c['LAST']),PREV=mm(c['PREV'])))
D['camps']=camps
json.dump(D,open('data.json','w'))
for c in camps:
    if c['action']!='HOLD': print(c['action'],c['channel'],c['site'],c['camp'][:45],c['L4']['logins'])
