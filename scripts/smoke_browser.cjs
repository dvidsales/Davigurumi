// Optional browser test: requires Playwright, Chromium and a local development server.
const { chromium } = require('playwright');
const { spawnSync } = require('node:child_process');
const path = require('node:path');
(async () => {
 const username='browser_'+Date.now();
 const browser = await chromium.launch({executablePath:process.env.CHROMIUM_PATH || '/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 try {
 const page = await browser.newPage({viewport:{width:1440,height:1000}});
 const errors=[]; page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8000/conta/criar/');
 await page.getByLabel('Primeiro nome').fill('Teste visual');
 await page.getByLabel('Usuário').fill(username);
 await page.locator('#id_email').fill(username+'@example.test');
 await page.locator('#id_password1').fill('Browser-Synthetic-Password-89!');
 await page.getByLabel('Confirmação de senha').fill('Browser-Synthetic-Password-89!');
 await page.getByRole('button',{name:'Começar',exact:true}).click();
 await page.waitForURL('http://127.0.0.1:8000/');
 await page.getByRole('link',{name:'+ Novo material',exact:true}).click();
 await page.locator('#id_name').fill('Fio de teste visual');
 await page.locator('#id_kind').selectOption('yarn');
 await page.getByLabel('Unidade de estoque').selectOption('g');
 await page.getByLabel('Quantidade que você já possui').fill('508');
 await page.getByLabel('Custo por g, m ou unidade').fill('0.10');
 await page.getByRole('button',{name:'Cadastrar material',exact:true}).click();
 await page.waitForURL(/materiais\/[a-f0-9-]+\//);
 if (!(await page.locator('main').innerText()).includes('508')) throw new Error('opening stock missing');
 await page.getByRole('link',{name:'Calculadora de preços',exact:true}).click();
 await page.getByLabel('Materiais (R$)').fill('100');
 await page.getByRole('button',{name:'Calcular preço',exact:true}).click();
 if (!(await page.locator('main').innerText()).includes('150,00')) throw new Error('pricing mismatch');
 await page.getByRole('link',{name:'Visão geral',exact:true}).click();
 await page.screenshot({path:'/tmp/davigurumi-desktop.png',fullPage:true});
 await page.setViewportSize({width:360,height:800});
 const routes=['/','/materiais/','/materiais/novo/','/precificacao/'];
 for (const route of routes) {
  await page.goto('http://127.0.0.1:8000'+route);
  const overflow = await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth);
  if (overflow) throw new Error('mobile overflow: '+route);
 }
 await page.goto('http://127.0.0.1:8000/');
 await page.screenshot({path:'/tmp/davigurumi-mobile.png',fullPage:true});
 await page.getByRole('button',{name:'Sair da conta'}).click();
 await page.waitForURL(/conta\/entrar\//);
 if (errors.length) throw new Error(errors.join('; '));
 console.log(JSON.stringify({signup:true,openingStock:508,markupPrice:'150.00',mobileWidth:360,routesWithoutOverflow:routes,logout:true,browserErrors:errors,syntheticUser:username}));
 } finally {
  await browser.close();
  const cleanup = spawnSync(process.env.DAVIGURUMI_PYTHON || 'python', ['manage.py','shell','-c',
   'import os; from accounts.models import User; from materials.models import Material, StockMovement; username=os.environ["DAVIGURUMI_SMOKE_USERNAME"]; users=User.objects.filter(username=username, email=username+"@example.test", first_name="Teste visual"); materials=Material.objects.filter(owner__in=users); StockMovement.objects.filter(material__in=materials).delete(); materials.delete(); users.delete()'],
   {cwd:path.resolve(__dirname,'..'),env:{...process.env,DAVIGURUMI_SMOKE_USERNAME:username},encoding:'utf8'});
  if (cleanup.status !== 0) throw new Error('Could not remove synthetic browser account: '+cleanup.stderr);
 }
})().catch(e=>{console.error(e);process.exit(1)});
