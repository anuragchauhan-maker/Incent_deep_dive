import sys; sys.path.insert(0,'.')
from sites import *
CHROAS={}
def chan_roas(ch,weeks): return met(agg([r for r in CH if r[1]==ch],weeks))['roas']
def verdict(cvr,lvl,roas,logins,ch_roas,campaign=False):
    if logins<100: return 'WATCH'
    if cvr is None: return 'WATCH'
    if (roas>=10 and cvr>=15 and lvl>=12) or (cvr>=20 and lvl>=13 and roas>=ch_roas): return 'SCALE UP'
    if (cvr<12 and lvl<8) or (lvl<=6.5 and roas<5.5) or roas<2.5: return 'SCALE DOWN'
    if campaign and cvr<12 and lvl<8.5 and roas<4: return 'SCALE DOWN'
    return 'HOLD'
def campaign_rows():
    res=[]
    for ch,site,cp,d in S:
        items=[(ch,site,cp,d)]
        L=sagg(items,SL4,ch);P=sagg(items,SP4,ch);LA=sagg(items,SLAST,ch);PV=sagg(items,SPREV,ch)
        if L['logins']+P['logins']<50: continue
        res.append(dict(channel=ch,site=site,camp=CAMP[cp],cat=CAT[cp],L4=L,P4=P,LAST=LA,PREV=PV,
          verdict=verdict(L['cvr'],L['lvl'],L['roas'] or 0,L['logins'],chan_roas(ch,L4),True)))
    return res
if __name__=='__main__':
    for r in build():
        r['verdict']=verdict(r['L4']['cvr'],r['L4']['lvl'],r['L4']['roas'] or 0,r['L4']['logins'],chan_roas(r['channel'],L4))
        print(r['channel'],r['site'],r['L4']['logins'],r['verdict'])
    print()
    for r in campaign_rows():
        if r['L4']['logins']>=40:
            f=lambda m:f"n={m['logins']} cvr={m['cvr'] and round(m['cvr'],1)} lvl={m['lvl'] and round(m['lvl'],1)} roas={m['roas'] and round(m['roas'],1)}"
            print(r['channel'],r['site'],r['camp'][:48],r['verdict'],'|',f(r['L4']))
