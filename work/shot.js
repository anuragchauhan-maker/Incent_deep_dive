const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium'});const p=await b.newPage({viewport:{width:1200,height:900}});
const errs=[];p.on('pageerror',e=>errs.push(e.message));p.on('console',m=>m.type()=='error'&&errs.push(m.text()));
await p.goto('file://'+process.cwd()+'/incent_dashboard.html');await p.waitForTimeout(2500);
console.log('errors',errs);console.log(await p.evaluate(()=>[document.querySelectorAll('canvas').length,typeof Chart]));
await p.screenshot({path:'shot.png',fullPage:true});await b.close()})();
