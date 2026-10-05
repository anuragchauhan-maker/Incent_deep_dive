import json
from data import *
from collections import defaultdict
weeks=["2026-08-03","2026-08-10","2026-08-17","2026-08-24","2026-08-31","2026-09-07","2026-09-14","2026-09-21"]
P4=weeks[:4]; L4=weeks[4:]; LW=[weeks[7]]; PW=[weeks[6]]
rows=[r.split('|') for r in ch_rows.split('\n')]
C=defaultdict(lambda:[0]*7)  # spend,la,lpl,deps,l20,cm1
for ch,cat,wk,sp,la,lpl,dp,l20,cm in rows:
    for key in [(ch,'All',wk),(ch,cat,wk)]:
        v=C[key]
        for i,x in enumerate([sp,la,lpl,dp,l20,cm]): v[i]+=float(x)
def agg(ch,cat,ws):
    t=[0]*6
    for w in ws:
        v=C.get((ch,cat,w))
        if v:
            for i in range(6): t[i]+=v[i]
    return t
def m(t):
    sp,la,lpl,dp,l20,cm=t
    return dict(spend=sp,logins=la,cvr=100*dp/la if la else None,lvl=100*l20/lpl if lpl else None,roas=100*cm/sp if sp>0 else None,cpl=sp/la if la and sp>0 else None)
def pm(ws):
    la=sum(p[1] for p in plat if p[0] in ws);dp=sum(p[2] for p in plat if p[0] in ws);cm=sum(p[3] for p in plat if p[0] in ws);lpl=sum(p[4] for p in plat if p[0] in ws);l20=sum(p[5] for p in plat if p[0] in ws);sp=sum(p[6] for p in plat if p[0] in ws)
    return dict(spend=sp,logins=la,cvr=100*dp/la,lvl=100*l20/lpl,roas=100*cm/sp)
chs=["adaction5_int","inboxdollars_int","myappfre_int","freecash_int"]
out={"weeks":weeks,"channels":{},"platform":{},"site":[]}
for nm,ws in [("L4",L4),("P4",P4),("LW",LW),("PW",PW)]: out["platform"][nm]=pm(ws)
out["platform_weekly"]=[dict(wk=p[0],cvr=100*p[2]/p[1],lvl=100*p[5]/p[4],roas=100*p[3]/p[6]) for p in plat]
tot=lambda ch:None
for ch in chs+["ALL"]:
    d={}
    for cat in ["All","Bingo","Solitaire"]:
        if ch=="ALL":
            res={}
            for nm,ws in [("L4",L4),("P4",P4),("LW",LW),("PW",PW)]:
                t=[0]*6
                for c in chs[:3]:
                    a=agg(c,cat,ws)
                    for i in range(6): t[i]+=a[i]
                res[nm]=m(t)
            wk=[]
            for w in weeks:
                t=[0]*6
                for c in chs[:3]:
                    a=agg(c,cat,[w])
                    for i in range(6): t[i]+=a[i]
                wk.append(dict(wk=w,**m(t)))
        else:
            res={nm:m(agg(ch,cat,ws)) for nm,ws in [("L4",L4),("P4",P4),("LW",LW),("PW",PW)]}
            wk=[dict(wk=w,**m(agg(ch,cat,[w]))) for w in weeks]
        d[cat]=dict(periods=res,weekly=wk)
    out["channels"][ch]=d
# siteid
S=defaultdict(dict)
for r in site_rows.split('\n'):
    ch,sid,cat,b,la,dp,cm,lpl,l20=r.split('|')
    S[(ch,sid,cat)][b]=[float(la),float(dp),float(cm),float(lpl),float(l20)]
# benchmark: incent cell-level avg L4 (siteid universe)
tl=sum(v['L4'][0] for v in S.values() if 'L4' in v); td=sum(v['L4'][1] for v in S.values() if 'L4' in v); tc=sum(v['L4'][2] for v in S.values() if 'L4' in v)
tlp=sum(v['L4'][3] for v in S.values() if 'L4' in v); t2=sum(v['L4'][4] for v in S.values() if 'L4' in v)
bm=dict(cvr=100*td/tl,lvl=100*t2/tlp,cpl=tc/tl)
out["bm"]=bm
def rt(v):
    la,dp,cm,lpl,l20=v
    return dict(la=la,cvr=100*dp/la,lvl=100*l20/lpl if lpl else None,cml=cm/la)
for (ch,sid,cat),v in sorted(S.items()):
    L=rt(v['L4']) if 'L4' in v else None; P=rt(v['P4']) if 'P4' in v else None
    # score vs incent benchmark L4
    if L and L['la']>=150:
        sc=0
        sc+= 1 if L['cvr']>=bm['cvr']*1.1 else (-1 if L['cvr']<bm['cvr']*0.8 else 0)
        sc+= 1 if L['lvl']>=bm['lvl']*1.1 else (-1 if L['lvl']<bm['lvl']*0.8 else 0)
        sc+= 1 if L['cml']>=bm['cpl']*1.1 else (-1 if L['cml']<bm['cpl']*0.6 else 0)
        act="SCALE UP" if sc>=2 else ("SCALE DOWN" if sc<=-2 else "HOLD / WATCH")
    elif L:
        sc=0
        strong=L['la']>=80 and L['cvr']>=bm['cvr']*1.1 and L['lvl']>=bm['lvl']*1.1 and L['cml']>=bm['cpl']
        weak=L['cvr']<bm['cvr']*0.6 and L['lvl']<bm['lvl']*0.5
        act="SCALE UP (low vol, strong quality)" if strong else ("SCALE DOWN / PAUSE (weak, low vol)" if weak else "HOLD / WATCH (low vol)")
        if ch=='freecash_int' and cat=='Other': act="HOLD / WATCH (1-wk artifact)"
    elif P: act="SCALE DOWN (no L4 volume)" if False else "INACTIVE (no L4 volume)"; sc=0
    else: continue
    if ch=="freecash_int" and cat=="Other": act="HOLD / WATCH (1-wk artifact)"
    out["site"].append(dict(ch=ch,sid=sid,cat=cat,L4=L,P4=P,score=sc,action=act))
json.dump(out,open('out.json','w'),indent=1)
print(bm)
for s in out["site"]:
    f=lambda x:'-' if x is None else f"{x['cvr']:.1f}/{x['lvl'] or 0:.1f}/{x['cml']:.2f}/{x['la']:.0f}"
    print(s['ch'][:6],s['sid'],s['cat'][:4],f(s['L4']),f(s['P4']),s['action'])
for ch in chs+["ALL"]:
    for cat in ["All"]:
        p=out["channels"][ch][cat]["periods"]
        print(ch,{k:{a:(round(b,1) if b is not None else None) for a,b in v.items()} for k,v in p.items()})
print(out["platform"])
