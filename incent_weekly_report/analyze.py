import sys, json
sys.path.insert(0,'.')
from chan_data import W, CH, PLAT
from site_data import S, CAMP
from collections import defaultdict
WI={w:i for i,w in enumerate(W)}
L4=['09-14','09-21','09-28','10-05']; P4=['08-17','08-24','08-31','09-07']
LAST='10-05'; PREV='09-28'
def agg(rows,weeks):
    t=dict(spend=0,la=0,lp=0,rein=0,deps=0,lvl=0,cm1=0)
    for r in rows:
        if r[0] in weeks:
            for k,v in zip(t,r[3:]): t[k]+=v
    return t
def met(t):
    d=lambda a,b: (100*a/b) if b else None
    return dict(spend=t['spend'],logins=t['la'],cvr=d(t['deps'],t['la']),lvl=d(t['lvl'],t['lp']),roas=d(t['cm1'],t['spend']) if t['spend'] else None,cm1=t['cm1'],
                cpl=(t['spend']/t['la'] if t['la'] else None),rein=d(t['rein'],t['la']))
def platm(weeks):
    t=[p for p in PLAT if p[0] in weeks]
    la=sum(p[1] for p in t);lp=sum(p[2] for p in t);dp=sum(p[3] for p in t);lv=sum(p[4] for p in t);cm=sum(p[5] for p in t);sp=sum(p[6] for p in t)
    return dict(spend=sp,logins=la,cvr=100*dp/la,lvl=100*lv/lp,roas=100*cm/sp)
if __name__=='__main__':
    for nm,wk in [('P5-8',P4),('L4',L4),('PREV',[PREV]),('LAST',[LAST])]:
        print(nm,{k:round(v,1) for k,v in platm(wk).items()})
    chs=sorted({r[1] for r in CH})
    for c in chs:
        rows=[r for r in CH if r[1]==c]
        for nm,wk in [('P5-8',P4),('L4',L4),('PREV',[PREV]),('LAST',[LAST])]:
            m=met(agg(rows,wk)); print(c,nm,{k:(round(v,1) if v is not None else None) for k,v in m.items()})
        for cat in ['Bingo','Solitaire']:
            rr=[r for r in rows if r[2]==cat]
            if not rr: continue
            for nm,wk in [('P5-8',P4),('L4',L4)]:
                m=met(agg(rr,wk)); print('  ',cat,nm,{k:(round(v,1) if v is not None else None) for k,v in m.items()})
