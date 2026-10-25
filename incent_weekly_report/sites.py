import sys; sys.path.insert(0,'.')
from analyze import *
CAT={'A1':'Solitaire','A2':'Bingo','F1':'Bingo','I1':'Solitaire','I2':'Bingo','I3':'Bingo','M1':'Bingo','M2':'Solitaire'}
SW=['08-17','08-24','08-31','09-07','09-14','09-21','09-28','10-05']
SL4=[4,5,6,7]; SP4=[0,1,2,3]; SLAST=[7]; SPREV=[6]
def cpl(ch,cat,weeks):
    rows=[r for r in CH if r[1]==ch and r[2]==cat]; t=agg(rows,weeks)
    return t['spend']/t['la'] if t['la'] else None
def sagg(items,idxs,ch):
    la=lp=dp=lv=0;cm=0;sp=0
    for (c,s,cp,d) in items:
        cat=CAT[cp]
        for i in idxs:
            if i in d:
                a,b,dd,l,m=d[i]; la+=a;lp+=b;dp+=dd;lv+=l;cm+=m
                sp+=a*(cpl(ch,cat,[SW[i]]) or 0)
    return dict(logins=la,cvr=100*dp/la if la else None,lvl=100*lv/lp if lp else None,cm1=cm,cm1_per_login=cm/la if la else None,spend_alloc=sp,roas=100*cm/sp if sp else None)
def build():
    out=[]
    for ch,site in sorted({(c,s) for c,s,_,_ in S}):
        items=[x for x in S if x[0]==ch and x[1]==site]
        rec=dict(channel=ch,site=site)
        for nm,ix in [('L4',SL4),('P4',SP4),('LAST',SLAST),('PREV',SPREV)]: rec[nm]=sagg(items,ix,ch)
        rec['weekly']=[sagg(items,[i],ch) for i in range(8)]
        out.append(rec)
    return out
if __name__=='__main__':
    for r in build():
        f=lambda m:' '.join(f"{k}={'-' if v is None else round(v,1)}" for k,v in m.items() if k in('logins','cvr','lvl','roas','cm1_per_login'))
        print(r['channel'],r['site']); print('  P4  ',f(r['P4'])); print('  L4  ',f(r['L4'])); print('  PREV',f(r['PREV'])); print('  LAST',f(r['LAST']))
