'use strict';
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
if(process.env.DAVIGURUMI_SMOKE_ISOLATED!=='1') throw Error('Disposable database required.');
const base=process.env.DAVIGURUMI_SMOKE_URL||'http://127.0.0.1:8120';
if(!['127.0.0.1','localhost','[::1]'].includes(new URL(base).hostname)) throw Error('Local synthetic review only.');
const out=process.env.DAVIGURUMI_AUDIT_OUTPUT||'/tmp/davigurumi-audit-ui';
fs.mkdirSync(out,{recursive:true});
const axe=fs.readFileSync(process.env.DAVIGURUMI_AXE_PATH,'utf8');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',args:['--no-sandbox']});
 try {
  const context=await browser.newContext({viewport:{width:390,height:844},locale:'pt-BR'});
  const page=await context.newPage(); const errors=[],audits=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('response',r=>{if(r.status()>=500)errors.push(`HTTP ${r.status()} ${new URL(r.url()).pathname}`)});
  await page.goto(base+'/conta/entrar/');
  await page.locator('#id_username').fill('query-review');
  await page.locator('#id_password').fill('Synthetic-Audit-Only-2026!');
  await page.getByRole('button',{name:'Entrar',exact:true}).click();
  await page.waitForURL(base+'/');
  const cases=[['inicio','/'],['relatorios','/notificacoes/relatorios/'],['agenda','/pedidos/calendario/'],['relatorios-invalidos','/notificacoes/relatorios/?start=2026-11-05&end=2026-11-01']];
  let layouts=0;
  for(const width of [320,360,390,430,600,768,1024,1440]) {
   await page.setViewportSize({width,height:900});
   for(const [name,path]of cases){
    assert.equal((await page.goto(base+path)).status(),200);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`${name} ${width}`);layouts++;
    if(width===390||width===1440){
     await page.evaluate(axe);
     const violations=await page.evaluate(async()=>(await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}})).violations.map(v=>({id:v.id,targets:v.nodes.map(n=>n.target)})));
     audits.push({name,width,violations});assert.deepEqual(violations,[],`${name} ${width}`);
     await page.screenshot({path:`${out}/${name}-${width}.png`,fullPage:true});
    }
   }
  }
  await page.goto(base+'/notificacoes/relatorios/?status=waiting&page=2');
  assert((await page.locator('main').innerText()).includes('Página 2 de 2'));
  const previous=page.getByRole('link',{name:'Anterior',exact:true});
  assert((await previous.getAttribute('href')).includes('status=waiting'));
  // Failed navigation leaves the current, unsaved form intact; no offline writes.
  await page.goto(base+'/materiais/novo/');
  await page.locator('#id_name').fill('Rascunho sintético preservado');
  await context.setOffline(true);
  await page.evaluate(async()=>{try{await fetch('/notificacoes/relatorios/');}catch{/* expected network failure */}});
  assert.equal(await page.locator('#id_name').inputValue(),'Rascunho sintético preservado');
  await context.setOffline(false);
  assert.deepEqual(errors,[]);
  fs.writeFileSync(out+'/result.json',JSON.stringify({layouts,accessibility:audits,pagination:true,filtersPreserved:true,unsavedFormNetworkFailure:true,errors},null,2));
  console.log(JSON.stringify({layouts,axe:audits.length,errors,output:out}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
