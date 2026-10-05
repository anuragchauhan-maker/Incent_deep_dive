import json
d=json.load(open('out.json'))
html='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Incent Channel Deep Dive</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root{--bg:#fafaf7;--fg:#111;--mut:#666;--card:#fff;--line:#111;--g:#e6f4ea;--r:#fde8e8;--y:#fff6dd}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#15161a;--fg:#eee;--mut:#9a9a9a;--card:#1d1f24;--line:#eee;--g:#183a24;--r:#4a1d1d;--y:#4a3f16}}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif}
.w{max-width:1200px;margin:0 auto;padding:16px}
h1{font-family:Georgia,serif;font-size:28px;margin:8px 0}h2{font-family:Georgia,serif;border-top:2px solid var(--line);padding-top:10px;margin-top:32px}
.mut{color:var(--mut)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:16px}
.card{background:var(--card);border:1px solid #8884;border-radius:8px;padding:12px}
table{border-collapse:collapse;width:100%;font-size:12.5px}th,td{padding:5px 7px;border-bottom:1px solid #8883;text-align:right;white-space:nowrap}th:first-child,td:first-child,td.l,th.l{text-align:left}
.sc{overflow-x:auto}.up{background:var(--g)}.dn{background:var(--r)}.hd{background:var(--y)}
select,button{font:inherit;padding:4px 8px;margin:2px;background:var(--card);color:var(--fg);border:1px solid #8886;border-radius:6px}button.on{background:var(--fg);color:var(--bg)}
.pos{color:#1a8f4c}.neg{color:#d64545}canvas{max-height:300px}
</style></head><body><div class="w">
<h1>Incent Channel Deep Dive — US</h1>
<div class="mut">Cohort weeks (Mon start) with D7 matured. Last 4 matured (L4): Aug 31 – Sep 27 · Prior 4 (P4): Aug 3 – Aug 30 · Latest matured week (LW): Sep 21–27 · Previous week (PW): Sep 14–20. Data as of 5 Oct 2026. Week of Sep 28 excluded (D7 not matured).</div>
<div class="card" style="margin-top:10px"><b>Data notes.</b> (1) FreeCash has logins but <b>no spend mapped</b> in marketing_spends_fat (no campaign names match "freecash") → ROAS/CAC shown "—"; FreeCash logins only appear from Aug 31 (new volume). (2) Spend isn't available at siteid level, so siteid verdicts use D7 Dep CVR, Lvl&gt;20 % and D7 CM1 per login, not ROAS. (3) InboxDollars vc-* siteids are a provider reporting change from 23 Mar 2026 (not an acquisition event). (4) Platform benchmark = all US channels incl. organic; ROAS = D7 CM1 / total US marketing spend.</div>
<h2>I. Executive summary</h2><div id="exec"></div>
<h2>II. Period comparison by channel</h2><div class="sc"><div id="t_period"></div></div>
<h2>III. Weekly trends</h2><div class="grid"><div class="card"><b>Spend by channel ($)</b><canvas id="c1"></canvas></div><div class="card"><b>D7 Dep CVR %</b><canvas id="c2"></canvas></div><div class="card"><b>D7 Level&gt;20 %</b><canvas id="c3"></canvas></div><div class="card"><b>D7 ROAS % (CM1/spend)</b><canvas id="c4"></canvas></div></div>
<h2>IV. Channel deep dive</h2><div class="card"><div id="chips"></div> Category: <select id="cat"><option>All</option><option>Bingo</option><option>Solitaire</option></select><canvas id="c5"></canvas><div class="sc" id="t_ch"></div></div>
<h2>V. SiteID verdicts (L4 vs P4)</h2><div class="card"><div class="mut">Benchmark = incent siteid-universe L4: Dep CVR <span id="b1"></span>%, Lvl&gt;20 <span id="b2"></span>%, D7 CM1/login $<span id="b3"></span>. Filter: <select id="fa"><option value="">All actions</option><option>SCALE UP</option><option>SCALE DOWN</option><option>HOLD</option><option>INACTIVE</option></select> <select id="fc"><option value="">All channels</option></select></div><div class="sc"><div id="t_site"></div></div></div>
<h2>VI. Campaign-level actions</h2><div class="sc"><div id="t_camp"></div></div>
</div><script>
if(typeof Chart==='undefined'){window.Chart=function(){this.destroy=()=>{}}}
const D=__DATA__;
const COL={adaction5_int:'#5B7FDB',inboxdollars_int:'#D64545',myappfre_int:'#E8A33D',freecash_int:'#4AAB7E',ALL:'#444'};
const NM={adaction5_int:'AdAction',inboxdollars_int:'InboxDollars',myappfre_int:'MyAppFree',freecash_int:'FreeCash',ALL:'Incent total (ex-FreeCash spend)'};
const f=(x,n=1,p='')=>x==null?'—':x.toFixed(n)+p, $=x=>x==null?'—':'$'+Math.round(x).toLocaleString();
const chs=['adaction5_int','inboxdollars_int','myappfre_int','freecash_int'];
const fmtd=w=>w.slice(5);
function delta(a,b,inv){if(a==null||b==null)return '';const d=a-b;const good=inv?d<0:d>0;return `<span class="${Math.abs(d)<0.05?'':good?'pos':'neg'}">${d>0?'▲':'▼'}${Math.abs(d).toFixed(1)}</span>`}
// exec
const P=D.platform;let ex='<ul>';
const A=D.channels.ALL.All.periods;
ex+=`<li><b>Incent (ex-FreeCash spend):</b> spend ${$(A.L4.spend)} L4 vs ${$(A.P4.spend)} P4 (${f(100*(A.L4.spend/A.P4.spend-1),0)}%); D7 ROAS ${f(A.L4.roas)}% vs ${f(A.P4.roas)}%; Dep CVR ${f(A.L4.cvr)}% vs ${f(A.P4.cvr)}%; Lvl&gt;20 ${f(A.L4.lvl)}% vs ${f(A.P4.lvl)}%. Platform L4: Dep CVR ${f(P.L4.cvr)}%, Lvl&gt;20 ${f(P.L4.lvl)}%, ROAS ${f(P.L4.roas)}%. Incent still runs far below platform quality/ROAS.</li>`;
ex+=`<li><b>Latest matured week (Sep 21) vs prior:</b> incent Lvl&gt;20 ${f(A.LW.lvl)}% vs ${f(A.PW.lvl)}%, Dep CVR ${f(A.LW.cvr)}% vs ${f(A.PW.cvr)}%, ROAS ${f(A.LW.roas)}% vs ${f(A.PW.roas)}%.</li>`;
const C=D.channels;
ex+=`<li><b>MyAppFree</b> – spend cut ${f(100*(1-C.myappfre_int.All.periods.L4.spend/C.myappfre_int.All.periods.P4.spend),0)}% and quality rose (Dep CVR ${f(C.myappfre_int.All.periods.L4.cvr)}% vs ${f(C.myappfre_int.All.periods.P4.cvr)}%, Lvl&gt;20 ${f(C.myappfre_int.All.periods.L4.lvl)}% vs ${f(C.myappfre_int.All.periods.P4.lvl)}%, ROAS ${f(C.myappfre_int.All.periods.L4.roas)}% vs ${f(C.myappfre_int.All.periods.P4.roas)}%) → cut removed worst sites (1318/1573/3950). Best-quality channel; spend rebounding in latest week ($19.9K vs $15.7K).</li>`;
ex+=`<li><b>InboxDollars</b> – spend up ${f(100*(C.inboxdollars_int.All.periods.L4.spend/C.inboxdollars_int.All.periods.P4.spend-1),0)}% with falling quality (Lvl&gt;20 ${f(C.inboxdollars_int.All.periods.L4.lvl)}% vs ${f(C.inboxdollars_int.All.periods.P4.lvl)}%; LW ${f(C.inboxdollars_int.All.periods.LW.lvl)}%) → wasted scale; Bingo Lvl&gt;20 fell to 5.0% in LW.</li>`;
ex+=`<li><b>AdAction</b> – spend cut ${f(100*(1-C.adaction5_int.All.periods.L4.spend/C.adaction5_int.All.periods.P4.spend),0)}% (halved from Sep 14); ROAS improved ${f(C.adaction5_int.All.periods.L4.roas)}% vs ${f(C.adaction5_int.All.periods.P4.roas)}% but volume fell sharply; quality flat-to-lower → shift remaining spend to the best siteids.</li>`;
ex+=`<li><b>FreeCash</b> – ${Math.round(C.freecash_int.All.periods.L4.logins).toLocaleString()} logins in L4 (new, ~1.2K/wk), Dep CVR ${f(C.freecash_int.All.periods.L4.cvr)}% but Lvl&gt;20 only ${f(C.freecash_int.All.periods.L4.lvl)}% (weakest); spend untracked → cannot judge ROAS.</li></ul>`;
document.getElementById('exec').innerHTML=ex;
// period table
function ptable(){let h='<table><tr><th class="l">Channel</th><th>Metric</th><th>L4</th><th>P4</th><th>Δ</th><th>LW</th><th>PW</th><th>Δ</th></tr>';
 const rows=[...chs,'ALL'];
 for(const ch of rows){const p=C[ch].All.periods;
  [['Spend','spend',$,0,1],['Logins','logins',x=>Math.round(x).toLocaleString(),0,0],['Dep CVR %','cvr',x=>f(x),1,0],['Lvl>20 %','lvl',x=>f(x),1,0],['D7 ROAS %','roas',x=>f(x),1,0]].forEach(([lab,k,fm,isd,inv],i)=>{
   const dd=(a,b)=>isd?delta(a,b,inv):(a==null||b==null||!b?'':`<span>${(100*(a/b-1)).toFixed(0)}%</span>`);
   h+=`<tr><td class="l">${i==0?'<b style="color:'+COL[ch]+'">'+NM[ch]+'</b>':''}</td><td class="l">${lab}</td><td>${fm(p.L4[k])}</td><td>${fm(p.P4[k])}</td><td>${dd(p.L4[k],p.P4[k])}</td><td>${fm(p.LW[k])}</td><td>${fm(p.PW[k])}</td><td>${dd(p.LW[k],p.PW[k])}</td></tr>`})}
 const pp=D.platform;h+=`<tr><td class="l"><b>Platform (all US)</b></td><td class="l">Dep CVR / Lvl>20 / ROAS %</td><td>${f(pp.L4.cvr)} / ${f(pp.L4.lvl)} / ${f(pp.L4.roas)}</td><td>${f(pp.P4.cvr)} / ${f(pp.P4.lvl)} / ${f(pp.P4.roas)}</td><td></td><td>${f(pp.LW.cvr)} / ${f(pp.LW.lvl)} / ${f(pp.LW.roas)}</td><td>${f(pp.PW.cvr)} / ${f(pp.PW.lvl)} / ${f(pp.PW.roas)}</td><td></td></tr></table>`;
 document.getElementById('t_period').innerHTML=h}
ptable();
// charts
const cfg=(id,type,ds,extra={})=>new Chart(document.getElementById(id),{type,data:{labels:D.weeks.map(fmtd),datasets:ds},options:Object.assign({responsive:true,interaction:{mode:'index',intersect:false}},extra)});
const lineDS=(k,withP)=>{const a=chs.map(ch=>({label:NM[ch],data:C[ch].All.weekly.map(w=>w[k]),borderColor:COL[ch],backgroundColor:COL[ch],tension:.25,spanGaps:false}));if(withP)a.push({label:'Platform',data:D.platform_weekly.map(w=>w[withP]),borderColor:'#888',borderDash:[5,4],pointRadius:0});return a};
cfg('c1','bar',chs.slice(0,3).map(ch=>({label:NM[ch],data:C[ch].All.weekly.map(w=>w.spend),backgroundColor:COL[ch]})),{scales:{x:{stacked:true},y:{stacked:true}}});
cfg('c2','line',lineDS('cvr','cvr'));cfg('c3','line',lineDS('lvl','lvl'));cfg('c4','line',lineDS('roas','roas'));
// deep dive
let sel='myappfre_int',chart5;
document.getElementById('chips').innerHTML=chs.map(c=>`<button data-c="${c}">${NM[c]}</button>`).join('');
function dd(){document.querySelectorAll('#chips button').forEach(b=>b.classList.toggle('on',b.dataset.c==sel));const cat=document.getElementById('cat').value;const w=C[sel][cat].weekly;
 if(chart5)chart5.destroy();
 chart5=new Chart(document.getElementById('c5'),{data:{labels:D.weeks.map(fmtd),datasets:[{type:'bar',label:'Spend $',data:w.map(x=>x.spend),backgroundColor:COL[sel]+'55',yAxisID:'y'},{type:'line',label:'Dep CVR %',data:w.map(x=>x.cvr),borderColor:COL[sel],yAxisID:'y1'},{type:'line',label:'Lvl>20 %',data:w.map(x=>x.lvl),borderColor:'#111',yAxisID:'y1'},{type:'line',label:'D7 ROAS %',data:w.map(x=>x.roas),borderColor:'#999',borderDash:[6,4],yAxisID:'y1'}]},options:{responsive:true,scales:{y:{position:'left'},y1:{position:'right',grid:{drawOnChartArea:false}}}}});
 document.getElementById('t_ch').innerHTML='<table><tr><th class="l">Week</th><th>Spend</th><th>Logins</th><th>Dep CVR</th><th>Lvl>20</th><th>ROAS</th></tr>'+w.map(x=>`<tr><td class="l">${x.wk}</td><td>${$(x.spend)}</td><td>${Math.round(x.logins)}</td><td>${f(x.cvr)}</td><td>${f(x.lvl)}</td><td>${f(x.roas)}</td></tr>`).join('')+'</table>'}
document.getElementById('chips').onclick=e=>{if(e.target.dataset.c){sel=e.target.dataset.c;dd()}};document.getElementById('cat').onchange=dd;dd();
// siteid
document.getElementById('b1').textContent=f(D.bm.cvr);document.getElementById('b2').textContent=f(D.bm.lvl);document.getElementById('b3').textContent=D.bm.cpl.toFixed(2);
const fc=document.getElementById('fc');chs.forEach(c=>fc.innerHTML+=`<option value="${c}">${NM[c]}</option>`);
const cls=a=>a.startsWith('SCALE UP')?'up':a.startsWith('SCALE DOWN')?'dn':'hd';
function st(){const fa=document.getElementById('fa').value,fch=fc.value;
 const rows=D.site.filter(s=>(!fa||s.action.startsWith(fa))&&(!fch||s.ch==fch)).sort((a,b)=>b.score-a.score);
 let h='<table><tr><th class="l">Channel</th><th class="l">SiteID</th><th class="l">Campaign</th><th>Logins L4</th><th>CVR L4</th><th>CVR P4</th><th>Lvl20 L4</th><th>Lvl20 P4</th><th>CM1/login L4</th><th>CM1/login P4</th><th class="l">Action</th></tr>';
 for(const s of rows){const L=s.L4||{},P=s.P4||{};h+=`<tr class="${cls(s.action)}"><td class="l">${NM[s.ch]}</td><td class="l">${s.sid}</td><td class="l">${s.cat}</td><td>${L.la?Math.round(L.la):'—'}</td><td>${f(L.cvr)}</td><td>${f(P.cvr)}</td><td>${f(L.lvl)}</td><td>${f(P.lvl)}</td><td>${L.cml!=null?'$'+L.cml.toFixed(2):'—'}</td><td>${P.cml!=null?'$'+P.cml.toFixed(2):'—'}</td><td class="l"><b>${s.action}</b></td></tr>`}
 document.getElementById('t_site').innerHTML=h+'</table>'}
document.getElementById('fa').onchange=st;fc.onchange=st;st();
// campaign
const m={};D.site.forEach(s=>{const k=NM[s.ch]+' · '+s.cat;(m[k]=m[k]||{up:[],dn:[]});if(s.action.startsWith('SCALE UP'))m[k].up.push(s.sid);else if(s.action.startsWith('SCALE DOWN')||s.action.startsWith('INACTIVE'))m[k].dn.push(s.sid)});
let h='<table><tr><th class="l">Campaign (channel · category)</th><th class="l">Scale UP siteIDs</th><th class="l">Scale DOWN / pause siteIDs</th></tr>';
for(const k of Object.keys(m).sort()){if(m[k].up.length||m[k].dn.length)h+=`<tr><td class="l">${k}</td><td class="l up">${m[k].up.join(', ')||'—'}</td><td class="l dn">${m[k].dn.join(', ')||'—'}</td></tr>`}
document.getElementById('t_camp').innerHTML=h+'</table><div class="mut">Scale-down list includes siteIDs with zero L4 volume (already switched off – keep off).</div>';
</script></body></html>'''
open('incent_deep_dive_dashboard.html','w').write(html.replace('__DATA__',json.dumps(d)))
