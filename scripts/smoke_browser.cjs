// Run ONLY against a server connected to a disposable, isolated test database.
// Synthetic records remain there for backup/restore verification; nothing is deleted here.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const base=process.env.DAVIGURUMI_SMOKE_URL||'http://127.0.0.1:8100';
if(process.env.DAVIGURUMI_SMOKE_ISOLATED!=='1')throw new Error('Set DAVIGURUMI_SMOKE_ISOLATED=1 only for a disposable test database.');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const errors=[];const failures=[];const accessibility=[];
 const axeSource=process.env.DAVIGURUMI_AXE_PATH?require("node:fs").readFileSync(process.env.DAVIGURUMI_AXE_PATH,"utf8"):null;
 const context=await browser.newContext({viewport:{width:1440,height:1000}});const page=await context.newPage();page.setDefaultTimeout(15000);
 page.on('pageerror',error=>errors.push(error.message));page.on('response',response=>{if(response.status()>=500)failures.push(response.status());});
 const username='browser_'+Date.now();const password='Browser-Synthetic-Password-89!';
 const go=async route=>{const response=await page.goto(base+route);assert.equal(response.status(),200,route);};
 const submit=async()=>{await page.getByRole('button',{name:/^(Salvar e continuar|Confirmar recebimento|Confirmar registro)$/}).click();};
 try{
  await go('/conta/criar/');await page.getByLabel('Primeiro nome').fill('Teste visual');await page.getByLabel('Usuário').fill(username);await page.locator('#id_email').fill(username+'@example.test');await page.locator('#id_password1').fill(password);await page.locator('#id_password2').fill(password);await page.getByRole('button',{name:'Começar',exact:true}).click();await page.waitForURL(base+'/');
  await go('/materiais/novo/');await page.locator('#id_name').fill('Fio visual privado');await page.locator('#id_kind').selectOption('yarn');await page.locator('#id_unit').selectOption('g');await page.locator('#id_initial_quantity').fill('508');await page.locator('#id_initial_unit_cost').fill('.10');await page.locator('details').first().evaluate(el=>el.open=true);await page.locator('#id_composition').fill('Algodão');await page.locator('#id_thickness').fill('Médio');await page.locator('#id_recommended_hook').fill('2,5 mm');await page.locator('#id_minimum_stock').fill('500');await page.getByRole('button',{name:'Cadastrar material',exact:true}).click();await page.waitForURL(/\/materiais\/[a-f0-9-]+\/$/);
  const materialPath=new URL(page.url()).pathname;const materialId=materialPath.split('/')[2];assert((await page.locator('main').innerText()).includes('508'));
  await go('/projetos/novo/');await page.locator('#id_name').fill('Boneco visual');await page.locator('#id_hours').fill('1');await page.locator('#id_hourly_rate').fill('30');await submit();await page.waitForURL(/\/projetos\/[a-f0-9-]+\/$/);const projectPath=new URL(page.url()).pathname;const projectId=projectPath.split('/')[2];
  await page.getByRole('link',{name:'+ Material da ficha'}).click();await page.locator('#id_material').selectOption(materialId);await page.locator('#id_quantity').fill('120');await submit();await page.waitForURL(base+projectPath);
  await go('/orcamentos/novo/');await page.locator('#id_terms').fill('Retirada combinada após produção.');await submit();await page.waitForURL(/\/orcamentos\/[a-f0-9-]+\/$/);const quotePath=new URL(page.url()).pathname;
  await page.getByRole('link',{name:'Adicionar primeira peça'}).click();await page.locator('#id_project').selectOption(projectId);await page.locator('#id_quantity').fill('1');await page.getByRole('button',{name:/Adicionar|Salvar/}).last().click();await page.waitForURL(base+quotePath);
  // Private file has an independently authorized image endpoint; chosen image is public.
  await page.getByRole('link',{name:'Adicionar imagem interna ou para cliente'}).click();await page.locator('#id_upload').setInputFiles({name:'peca.png',mimeType:'image/png',buffer:require('node:fs').readFileSync(require('node:path').join(__dirname,'../static/icons/icon-192.png'))});await page.locator('#id_label').fill('Imagem visual');await page.locator('#id_is_public').check();await submit();await page.waitForURL(base+quotePath);
  await page.getByRole('link',{name:'Revisar e publicar',exact:true}).click();await page.getByRole('button',{name:'Publicar esta versão'}).click();await page.locator('#share-link').waitFor();const portal=await page.locator('#share-link').inputValue();
  const visitorContext=await browser.newContext();const visitor=await visitorContext.newPage();await visitor.goto(portal);let publicText=await visitor.locator('body').innerText();assert(!publicText.includes('Fio visual privado'));assert(publicText.includes('63,00'));
  await visitor.locator('#id_declaration').check();await visitor.getByRole('button',{name:'Confirmar decisão'}).click();assert((await visitor.locator('body').innerText()).includes('Aprovada'));await visitorContext.close();
  await go(quotePath);await page.getByRole('link',{name:'Registrar sinal/recebimento'}).click();await page.locator('#id_amount').fill('20');await submit();await page.waitForURL(base+quotePath);
  await page.getByRole('button',{name:'Criar / abrir pedido desta aprovação'}).click();await page.waitForURL(/\/pedidos\/[a-f0-9-]+\/$/);const orderPath=new URL(page.url()).pathname;
  assert((await page.locator('main').innerText()).includes('43,00'));
  await page.getByRole('button',{name:'Reservar necessidade restante'}).click();await page.waitForURL(base+orderPath);
  await page.getByRole('button',{name:'Iniciar / retomar'}).click();await page.waitForURL(base+orderPath);await page.waitForLoadState('load');await page.reload();assert(await page.getByRole('heading',{name:'Sessão ativa'}).isVisible());await page.getByRole('button',{name:'Pausar / encerrar sessão'}).click();
  await page.getByRole('link',{name:'Registrar consumo',exact:true}).click();await page.locator('#id_material').selectOption(materialId);const reserve=await page.locator('#id_reservation option').nth(1).getAttribute('value');await page.locator('#id_reservation').selectOption(reserve);await page.locator('#id_quantity').fill('50');await submit();await page.waitForURL(base+orderPath);
  await page.getByRole('link',{name:'Quantidade produzida'}).click();await page.locator('#id_quantity').fill('1');await submit();await page.waitForURL(base+orderPath);
  await page.getByRole('button',{name:'Concluir apenas a produção já registrada',exact:true}).click();await page.waitForURL(base+orderPath);
  await page.getByRole('link',{name:'Entregar',exact:true}).click();await page.locator('#id_quantity').fill('1');await submit();await page.waitForURL(base+orderPath);
  await page.getByRole('link',{name:'Registrar recebimento',exact:true}).click();await page.locator('#id_amount').fill('43');await submit();await page.waitForURL(base+orderPath);
  let orderText=await page.locator('main').innerText();assert(orderText.includes('Concluída')&&orderText.includes('Entregue')&&orderText.includes('Quitado'));
  await go(materialPath);let stockText=await page.locator('main').innerText();assert(stockText.includes('458'));assert(!stockText.includes('70 g'));
  // Record and reverse an actual expense without changing customer receipts.
  await go(orderPath);await page.getByRole('link',{name:'Registrar despesa ou reversão'}).click();const expensePath=new URL(page.url()).pathname;await page.locator('#id_amount').fill('5');await page.locator('#id_description').fill('Envio sintético');await submit();await page.waitForURL(base+orderPath);
  await go(expensePath);await page.locator('#id_reverses').selectOption(await page.locator('#id_reverses option').nth(1).getAttribute('value'));await page.locator('#id_amount').fill('5');await page.locator('#id_description').fill('Despesa duplicada revertida');await submit();await page.waitForURL(base+orderPath);
  await page.getByRole('link',{name:'Recuperar sobra física',exact:true}).click();const recoverPath=new URL(page.url()).pathname;await page.locator('#id_quantity').fill('10');await page.locator('#id_reason').fill('Sobra devolvida fisicamente');await submit();await page.waitForURL(base+orderPath);
  await go(materialPath);assert((await page.locator('main').innerText()).includes('468'));
  await page.locator('#archive-reason').fill('Fora do catálogo');await page.getByRole('button',{name:'Arquivar cadastro',exact:true}).click();await page.waitForURL(base+materialPath);assert((await page.locator('main').innerText()).includes('Material arquivado'));
  await go('/materiais/');assert(!(await page.locator('main').innerText()).includes('Fio visual privado'));
  await go(materialPath);await page.locator('#archive-reason').fill('Catálogo reativado');await page.getByRole('button',{name:'Reativar cadastro',exact:true}).click();await page.waitForURL(base+materialPath);
  await go(orderPath+'configuracao/');await page.locator('#id_planned_start').fill('2026-10-07');await page.locator('#id_production_due').fill('2026-10-09');await submit();await page.waitForURL(base+orderPath);
  await go('/pedidos/calendario/');assert((await page.locator('main').innerText()).includes('Início planejado'));
  const comparePath=quotePath+'comparar/';await go(comparePath);assert((await page.locator('main').innerText()).includes('Preservado'));
  // CSV preview and POST confirmation, using default column mapping and explicit text locale.
  await go('/dados/');await page.locator('#id_upload').setInputFiles({name:'materials.csv',mimeType:'text/csv',buffer:Buffer.from('nome;tipo;unidade;quantidade;custo_unitario\nBotão importado;acessorio;un;4;\n')});await page.getByRole('button',{name:'Gerar prévia'}).click();await page.getByRole('button',{name:'Confirmar todas as linhas'}).click();assert((await page.locator('main').innerText()).includes('Aplicada em'));
  // Purchase confirmation freezes manual allocation without receiving stock.
  await go('/compras/nova/');await page.locator('#id_freight').fill('7');await submit();await page.waitForURL(/\/compras\/[a-f0-9-]+\/$/);const purchasePath=new URL(page.url()).pathname;
  await page.getByRole('link',{name:'+ Adicionar item'}).click();await page.locator('#id_material').selectOption(materialId);await page.locator('#id_quantity').fill('10');await page.locator('#id_unit_price').fill('0');await submit();await page.waitForURL(base+purchasePath);
  await page.getByRole('link',{name:'Revisar rateio e confirmar'}).click();const allocationPath=new URL(page.url()).pathname;await page.setViewportSize({width:360,height:800});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth),false,'allocation mobile overflow');await page.locator('#id_mode').selectOption('manual');await page.locator('input[id^="id_cost_"]').fill('7');await submit();await page.waitForURL(base+purchasePath);assert((await page.locator('main').innerText()).includes('Manual'));
  await go(materialPath);assert((await page.locator('main').innerText()).includes('468'));
  await go('/');assert((await page.locator('main').innerText()).includes('Estoque abaixo do mínimo'));
  await go('/notificacoes/relatorios/');await page.locator('#id_project').selectOption(projectId);await page.locator('#id_status').selectOption('completed');const downloaded=page.waitForEvent('download');await page.getByRole('button',{name:'Exportar pedidos XLSX'}).click();const report=await downloaded;assert.equal(report.suggestedFilename(),'pedidos.xlsx');await report.saveAs('/tmp/davigurumi-browser-orders.xlsx');
  const routes=['/','/materiais/','/materiais/novo/',materialPath,'/precificacao/','/compras/','/compras/nova/','/compras/fornecedores/','/projetos/',projectPath,'/projetos/'+projectId+'/editar/','/clientes/','/orcamentos/',quotePath,'/pedidos/',orderPath,'/financeiro/','/notificacoes/','/notificacoes/relatorios/','/dados/','/dados/completo/','/demo/',materialPath+'editar/',purchasePath,expensePath,recoverPath,'/pedidos/calendario/',comparePath,'/notificacoes/relatorios/materiais/','/conta/seguranca/','/conta/senha/'];
  await page.setViewportSize({width:1440,height:1000});await go('/');await page.screenshot({path:'/tmp/davigurumi-desktop.png',fullPage:true});await page.setViewportSize({width:360,height:800});
  for(const route of routes){
   await go(route);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth),false,'mobile overflow '+route);
   if(axeSource){await page.evaluate(axeSource);const result=await page.evaluate(async()=>{const result=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}});return result.violations.map(v=>({id:v.id,impact:v.impact,targets:v.nodes.map(n=>n.target)}));});accessibility.push({route,violations:result});}
  }
  for(const width of [768,1024]){await page.setViewportSize({width,height:1024});for(const route of ['/',materialPath,orderPath,'/dados/','/notificacoes/relatorios/']){await go(route);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth),false,'tablet overflow '+route);}}
  await page.setViewportSize({width:360,height:800});
  if(axeSource){require('node:fs').writeFileSync('/tmp/davigurumi-accessibility.json',JSON.stringify(accessibility,null,2));assert.equal(accessibility.reduce((total,row)=>total+row.violations.length,0),0,'WCAG automated violations; inspect /tmp/davigurumi-accessibility.json');}
  await go('/');await page.screenshot({path:'/tmp/davigurumi-mobile.png',fullPage:true});
  // Service worker cache must contain only the explicit static allowlist, no private response.
  await page.evaluate(async()=>{await navigator.serviceWorker.ready;});
  const cached=await page.evaluate(async()=>{let result=[];for(const key of await caches.keys())for(const request of await (await caches.open(key)).keys())result.push(new URL(request.url).pathname);return result;});assert(cached.every(path=>path.startsWith('/static/')),JSON.stringify(cached));
  await context.setOffline(true);await page.evaluate(()=>window.dispatchEvent(new Event('offline')));assert.equal(await page.locator('#connection-status').isVisible(),true);await context.setOffline(false);
  const otherContext=await browser.newContext();const other=await otherContext.newPage();await other.goto(base+'/conta/criar/');await other.locator('#id_first_name').fill('Outro teste');await other.locator('#id_username').fill(username+'_other');await other.locator('#id_email').fill(username+'_other@example.test');await other.locator('#id_password1').fill(password);await other.locator('#id_password2').fill(password);await other.getByRole('button',{name:'Começar',exact:true}).click();await other.waitForURL(base+'/');
  for(const route of [materialPath,projectPath,quotePath,orderPath])assert.equal((await other.goto(base+route)).status(),404,'owner isolation');await otherContext.close();
  await go('/demo/');await page.getByRole('button',{name:'Entrar na demonstração'}).click();await page.waitForURL(base+'/');assert((await page.locator('main').innerText()).includes('DEMONSTRAÇÃO'));
  await go('/materiais/');assert((await page.locator('main').innerText()).includes('Fio de demonstração'));assert(!(await page.locator('main').innerText()).includes('Fio visual privado'));
  await go('/demo/');await page.getByRole('button',{name:'Voltar à conta real'}).click();await page.waitForURL(base+'/');assert(!(await page.locator('main').innerText()).includes('DEMONSTRAÇÃO'));
  await go('/materiais/');assert((await page.locator('main').innerText()).includes('Fio visual privado'));
  let load=null;
  if(process.env.DAVIGURUMI_SMOKE_LOAD==='1'){
   const pending=Array.from({length:48},(_,i)=>['/','/materiais/','/projetos/','/orcamentos/','/pedidos/','/notificacoes/relatorios/'][i%6]);const times=[];let cursor=0;
   await Promise.all(Array.from({length:4},async()=>{while(cursor<pending.length){const route=pending[cursor++];const started=performance.now();const response=await context.request.get(base+route);assert.equal(response.status(),200,'isolated load '+route);times.push(performance.now()-started);await response.dispose();}}));
   times.sort((a,b)=>a-b);load={requests:times.length,concurrency:4,p50Milliseconds:Math.round(times[Math.floor(times.length*.5)]),p95Milliseconds:Math.round(times[Math.floor(times.length*.95)]),failures:0};
  }
  assert.deepEqual(errors,[]);assert.deepEqual(failures,[]);
  console.log(JSON.stringify({signup:true,quoteApproval:true,depositTransferredOnce:20,orderTotal:63,remainingPayment:43,stockAfterConsumption:458,productionCompleted:true,delivered:true,paid:true,importPreviewAndConfirmation:true,manualPurchaseAllocation:true,expenseAndReversal:true,stockAfterRecovery:468,archiveAndRestore:true,calendar:true,versionComparison:true,xlsxFilteredReport:true,minimumStockVisible:true,materialTechnicalMetadata:true,ownerIsolation:true,staticOnlyCache:true,offlineBanner:true,demoIsolationAndSwitch:true,mobileWidth:360,routesWithoutOverflow:routes.length,browserErrors:errors,tabletWidths:[768,1024],load,accessibilityViolations:accessibility.reduce((total,row)=>total+row.violations.length,0)}));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1)});
