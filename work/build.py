import json, re, collections
W=['2026-08-03','2026-08-10','2026-08-17','2026-08-24','2026-08-31','2026-09-07','2026-09-14','2026-09-21']
CH=['adaction5_int','freecash_int','inboxdollars_int','myappfre_int']
NAME={'adaction5_int':'AdAction','freecash_int':'FreeCash (Almedia)','inboxdollars_int':'InboxDollars','myappfre_int':'MyAppFree'}
# channel x week: spend la lp deps l20 cm1
chan_raw="""PLATFORM_OTHER|29112|5684|4606|1249|1590|16131.22
PLATFORM_OTHER|30738|5881|4767|1247|1533|17507.47
PLATFORM_OTHER|30519|7041|5509|1280|1611|20022.99
PLATFORM_OTHER|30194|7605|6063|1331|1521|16034.58
PLATFORM_OTHER|23518|6258|5066|1284|1437|14457.16
PLATFORM_OTHER|23467|6088|4896|1156|1375|19815.06
PLATFORM_OTHER|22242|5475|4419|1095|1255|13582.11
PLATFORM_OTHER|23744|5529|4453|1162|1243|12047.44
adaction5_int|14054|786|691|124|101|214.94
adaction5_int|14149|921|802|146|130|901.45
adaction5_int|16190|957|827|161|128|1029.85
adaction5_int|16675|981|830|143|105|908.66
adaction5_int|15153|999|795|150|130|2152.35
adaction5_int|16519|1293|917|128|95|1016.85
adaction5_int|9078|432|364|53|44|253.88
adaction5_int|8366|496|429|66|46|994.54
freecash_int|0|1|1|0|1|-0.08
freecash_int|0|2|2|1|1|1.46
freecash_int|0|1|0|0|0|0
freecash_int|0|2|1|0|0|-0.77
freecash_int|6843|635|583|100|73|553.34
freecash_int|10745|1371|1270|158|88|587.57
freecash_int|10214|1214|1113|149|75|541.18
freecash_int|10134|1274|1158|129|66|541.87
inboxdollars_int|11692|813|723|115|82|721.92
inboxdollars_int|13796|904|810|158|116|932.29
inboxdollars_int|18247|1335|1215|174|127|1169.62
inboxdollars_int|17691|1268|1140|164|110|1663.44
inboxdollars_int|17712|1253|1119|174|129|1937.96
inboxdollars_int|17649|1259|1145|194|130|1216.78
inboxdollars_int|18652|1346|1212|161|103|1193.66
inboxdollars_int|16558|1321|1158|146|76|735.9
myappfre_int|37536|1501|1304|169|117|376.1
myappfre_int|31740|1259|1091|189|123|627.48
myappfre_int|28589|1177|990|193|128|635.34
myappfre_int|23118|990|822|206|131|733.17
myappfre_int|20706|952|781|228|146|1556.11
myappfre_int|16181|758|624|161|96|606.5
myappfre_int|15732|718|602|145|88|503.4
myappfre_int|19887|870|728|175|100|564.18"""
chan=collections.defaultdict(lambda:[None]*8)
cnt=collections.Counter()
for line in chan_raw.split('\n'):
    p=line.split('|'); ms=p[0]; i=cnt[ms]; cnt[ms]+=1
    chan[ms][i]=dict(spend=float(p[1]),la=int(p[2]),lp=int(p[3]),deps=int(p[4]),l20=int(p[5]),cm1=float(p[6]))
# freecash early weeks are noise (no spend): null them
for i in range(4): chan['freecash_int'][i]=dict(spend=0,la=0,lp=0,deps=0,l20=0,cm1=0)
plat=[]
for i in range(8):
    d={k:sum(chan[m][i][k] for m in chan) for k in ['spend','la','lp','deps','l20','cm1']}
    plat.append(d)
# campaign spend & total logins
CSP={'AAS':[10666,11225,12482,12570,11306,12844,6047,5875],'AAB':[3388,2924,3708,4105,3847,3675,3031,2491],
'FCB':[0,0,0,0,6843,10745,10214,10134],'IDS':[4247,4207,6285,6061,6464,6560,6755,6255],
'IDA':[3289,5154,2912,943,345,165,0,0],'IDB':[4156,4435,9050,10687,10903,10924,11897,10303],
'MFB':[9522,8556,7475,6854,5589,3772,1978,3312],'MFS':[28014,23184,21114,16264,15117,12409,13754,16575]}
CLA={'AAS':[538,691,662,670,733,1002,297,353],'AAB':[248,230,295,311,266,291,135,143],
'FCB':[0,0,0,0,351,1368,1212,1273],'IDS':[332,328,478,489,484,449,495,518],
'IDA':[201,263,138,0,0,0,0,0],'IDB':[280,313,719,778,769,810,851,803],
'MFB':[392,334,318,288,240,164,88,134],'MFS':[1107,925,859,702,712,594,630,736]}
CATN={'AAS':'Solitaire','AAB':'Bingo','FCB':'Bingo','IDS':'Solitaire','IDA':'Bingo','IDB':'Bingo','MFB':'Bingo','MFS':'Solitaire'}
CAMPN={'AAS':'Adaction_Solitaire_IOS_29102025','AAB':'AdAction_Bingo_IOS_26052025','FCB':'Almedia_Bingo_iOS_200826','IDS':'Inboxdollar_Solitaire_IOS_04112025','IDA':'Inboxdollar_Bingo_AOS_18112025','IDB':'Inboxdollar_Bingo_IOS_23062025','MFB':'myappfree_MPL_Bingo_iOS','MFS':'myappfree_MPL_Solitaire_iOS'}
# cells
cells=collections.defaultdict(lambda:[dict(la=0,lp=0,deps=0,l20=0,cm1=0.0,spend=0.0) for _ in range(8)])
for line in open('/home/user/Incent_deep_dive/work/sid_data.txt'):
    if line.startswith('#') or not line.strip(): continue
    ms,c,sid,rest=line.strip().split('|')
    for tok in rest.split():
        w,v=tok.split(':'); w=int(w); la,lp,de,l2,cm=v.split('/')
        x=cells[(ms,sid,c)][w]
        x['la']+=int(la);x['lp']+=int(lp);x['deps']+=int(de);x['l20']+=int(l2);x['cm1']+=float(cm)
for (ms,sid,c),arr in cells.items():
    for w in range(8):
        if CLA[c][w]>0: arr[w]['spend']=arr[w]['la']*CSP[c][w]/CLA[c][w]
def agg(rows):
    o=dict(la=0,lp=0,deps=0,l20=0,cm1=0.0,spend=0.0)
    for r in rows:
        for k in o:o[k]+=r[k]
    return o
def met(a):
    return dict(la=a['la'],spend=round(a['spend']),cvr=100*a['deps']/a['la'] if a['la'] else None,
      l20=100*a['l20']/a['lp'] if a['lp'] else None,roas=100*a['cm1']/a['spend'] if a['spend']>0 else None)
R=range(4,8);P=range(0,4)
def per(arr,rng): return agg([arr[w] for w in rng])
def periods(arr):
    return {'R':met(per(arr,R)),'P':met(per(arr,P)),'L':met(per(arr,[7])),'PW':met(per(arr,[6]))}
# portfolio (siteid-covered) for benchmark
allcells=list(cells.items())
port={k:met(agg([cells_arr[w] for _,cells_arr in allcells for w in rng])) for k,rng in [('R',R),('P',P),('L',[7]),('PW',[6])]}
platP={k:met(agg([plat[w] for w in rng])) for k,rng in [('R',R),('P',P),('L',[7]),('PW',[6])]}
# coverage
cov=sum(agg([a[w] for _,a in allcells for w in range(4,8)])['la'] for _ in [0])/sum(chan[m][w]['la'] for m in CH for w in range(4,8))
def flag(m,pm,minla,arr=None):
    if m['R']['la']<minla: return ('LOW VOLUME','Hold – insufficient volume')
    if m['L']['la']+m['PW']['la']<60: return ('DORMANT','Dormant – no current volume')
    wk_ok=None
    if arr is not None:
        ws=[w for w in range(4,8) if arr[w]['la']>=20 and arr[w]['spend']>0]
        wk_ok=sum(1 for w in ws if arr[w]['cm1']/arr[w]['spend']*100>=pm['R']['roas'])>=max(2,len(ws)//2+ (len(ws)%2))
    r=m['R']['roas']; 
    if r is None: return ('NA','Hold')
    pr=pm['R']['roas']; pc=pm['R']['cvr']; pl=pm['R']['l20']
    c=m['R']['cvr']; l=m['R']['l20']
    better=(c>=pc)+(l>=pl)
    worse=(c<0.85*pc)+(l<0.85*pl)
    lr=m['L']['roas']
    if r>=1.25*pr and better>=1 and (wk_ok is not False) and (lr is None or m['L']['la']<30 or lr>=0.75*pr): return ('SCALE UP','Scale up')
    if r<=0.6*pr or (r<pr and worse==2): return ('SCALE DOWN','Scale down')
    if r<pr and worse>=1 and m['L']['la']>=30 and lr is not None and lr<0.6*pr: return ('SCALE DOWN','Scale down')
    return ('HOLD','Hold / monitor')
# siteid level
sids=collections.defaultdict(lambda:[dict(la=0,lp=0,deps=0,l20=0,cm1=0.0,spend=0.0) for _ in range(8)])
for (ms,sid,c),arr in cells.items():
    for w in range(8):
        for k in arr[w]: sids[(ms,sid)][w][k]+=arr[w][k]
S=[]
for (ms,sid),arr in sorted(sids.items()):
    m=periods(arr); f=flag(m,port,150,arr)
    S.append(dict(ms=ms,ch=NAME[ms],sid=sid,m=m,flag=f[0],act=f[1],weekly=[dict(la=a['la'],lp=a['lp'],deps=a['deps'],l20=a['l20'],cm1=round(a['cm1'],1),spend=round(a['spend'])) for a in arr]))
C=[]
for (ms,sid,c),arr in sorted(cells.items()):
    m=periods(arr); f=flag(m,port,100,arr)
    C.append(dict(ms=ms,ch=NAME[ms],sid=sid,camp=c,campn=CAMPN[c],cat=CATN[c],m=m,flag=f[0]))
chanout={}
for ms in CH:
    arr=chan[ms]
    chanout[ms]=dict(name=NAME[ms],weekly=arr,per={k:met(agg([arr[w] for w in rng])) for k,rng in [('R',R),('P',P),('L',[7]),('PW',[6])]})
# category weekly per channel (siteid-covered)
catw={}
for (ms,sid,c),arr in cells.items():
    key=ms+'|'+CATN[c]
    if key not in catw: catw[key]=[dict(la=0,lp=0,deps=0,l20=0,cm1=0.0,spend=0.0) for _ in range(8)]
    for w in range(8):
        a=arr[w]; t=catw[key][w]
        for k in ['la','lp','deps','l20','cm1']: t[k]+=a[k]
        t['spend']+=CSP[c][w]  # campaign spend counted once per campaign below
# fix spend: count campaign spend once per campaign-category
for key in catw:
    for w in range(8): catw[key][w]['spend']=0
for c in CSP:
    ms={'AAS':'adaction5_int','AAB':'adaction5_int','FCB':'freecash_int','IDS':'inboxdollars_int','IDA':'inboxdollars_int','IDB':'inboxdollars_int','MFB':'myappfre_int','MFS':'myappfre_int'}[c]
    for w in range(8): catw[ms+'|'+CATN[c]][w]['spend']+=CSP[c][w]
out=dict(weeks=W,chan=chanout,plat=plat,platP=platP,port=port,S=S,C=C,cat=catw,coverage=cov,
 names=NAME)
json.dump(out,open('/home/user/Incent_deep_dive/work/data.json','w'))
def f(x,p=1,s=''): return '—' if x is None else f'{x:.{p}f}{s}'
print('coverage',round(cov,3))
print('PLAT',{k:{a:(round(b,1) if b else b) for a,b in v.items()} for k,v in platP.items()})
print('PORT',{k:{a:(round(b,1) if b else b) for a,b in v.items()} for k,v in port.items()})
for ms in CH:
    p=chanout[ms]['per']
    print(NAME[ms],{k:(p[k]['la'],p[k]['spend'],f(p[k]['cvr']),f(p[k]['l20']),f(p[k]['roas'])) for k in p})
print()
for s in S:
    m=s['m']; print(f"{s['flag']:11}{s['ch'][:9]:9} {s['sid']:11} R:{m['R']['la']:5} sp{m['R']['spend']:6} cvr{f(m['R']['cvr'])} l20 {f(m['R']['l20'])} roas {f(m['R']['roas'])} | P: {m['P']['la']:5} cvr {f(m['P']['cvr'])} l20 {f(m['P']['l20'])} roas {f(m['P']['roas'])} | L:{m['L']['la']} roas {f(m['L']['roas'])} PW:{m['PW']['la']} roas {f(m['PW']['roas'])}")
print()
for s in C:
    m=s['m']
    if s['flag'] in('SCALE UP','SCALE DOWN'): print(f"{s['flag']:11}{s['ch'][:9]:9} {s['sid']:11} {s['camp']} R:{m['R']['la']:5} cvr{f(m['R']['cvr'])} l20 {f(m['R']['l20'])} roas {f(m['R']['roas'])} L roas {f(m['L']['roas'])}")
