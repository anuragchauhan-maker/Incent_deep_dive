import json,csv
R=json.load(open('results.json'))
rows=list(csv.DictReader(open('channel.csv')))
for r in rows:
    for k in ['spend','la','lp','ri','dep','l20','cm1']: r[k]=float(r[k])
data=dict(R=R,rows=rows)
tpl=open('tpl.html').read()
open('incent_dashboard.html','w').write(tpl.replace('/*CHARTJS*/',open('package/dist/chart.umd.js').read()).replace('/*DATA*/',json.dumps(data)))
