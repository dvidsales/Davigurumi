#!/usr/bin/env node
"use strict";
// Credentials are read only from environment; never print responses, cookies or errors containing input values.
const { request, chromium } = require("playwright");
const fs = require("node:fs");
const path = require("node:path");
const { performance } = require("node:perf_hooks");
const {
  TARGET,
  validateTarget,
  aggregate,
  Pacer,
  Circuit,
  safeLocation,
} = require("./core.cjs");
const args = new Set(process.argv.slice(2));
const local = args.has("--local-smoke");
const out = process.env.DAVIGURUMI_LOAD_OUTPUT || "/tmp/davigurumi-load-report";
const report = {
  schema: 1,
  method:
    "HTTP completo via Playwright APIRequestContext; não mede tempo puro de servidor ou renderização",
  started_at: new Date().toISOString(),
  target: TARGET,
  mode: local ? "local-smoke" : "remote-bounded",
  release: null,
  fixture: null,
  phases: [],
  samples: [],
  aborted: null,
};
let base, deadline, browser;
const clients = [];
class Stop extends Error {}
function stop(code) {
  throw new Stop(code);
}
function budget() {
  if (report.aborted) stop(report.aborted);
  if (performance.now() > deadline) stop("TIME_BUDGET_REACHED");
}
async function makeClient() {
  const client = await request.newContext({
    ignoreHTTPSErrors: false,
    proxy:
      !local && process.env.HTTPS_PROXY
        ? { server: process.env.HTTPS_PROXY }
        : undefined,
    userAgent: "Davigurumi-Authorized-Load-Test/1.0",
  });
  clients.push(client);
  return client;
}
async function http(client, route, options = {}) {
  let url = safeLocation(base, route);
  let method = options.method || "GET";
  for (let redirect = 0; redirect < 4; redirect++) {
    budget();
    report.http_requests = (report.http_requests || 0) + 1;
    if (report.http_requests > 450) stop("HTTP_REQUEST_BUDGET_REACHED");
    const response = await client.fetch(url, {
      ...options,
      method,
      maxRedirects: 0,
      timeout: Math.min(
        options.timeout || 15000,
        Math.max(1, deadline - performance.now()),
      ),
    });
    if (response.status() >= 300 && response.status() < 400) {
      const location = response.headers().location;
      await response.dispose();
      if (!location) stop("INVALID_REDIRECT");
      url = safeLocation(base, location);
      if (method !== "GET") {
        method = "GET";
        options = {};
      }
      continue;
    }
    return response;
  }
  stop("TOO_MANY_REDIRECTS");
}
function csrf(body) {
  const input = body.match(
    /<input[^>]*name=["']csrfmiddlewaretoken["'][^>]*>/i,
  );
  const token = input && input[0].match(/value=["']([^"']+)["']/i);
  if (!token) stop("CSRF_NOT_FOUND");
  return token[1];
}
async function login(client, user, password) {
  const form = await http(client, "/conta/entrar/");
  if (form.status() !== 200) stop("LOGIN_PAGE_UNAVAILABLE");
  const token = csrf(await form.text());
  await form.dispose();
  const response = await http(client, "/conta/entrar/", {
    method: "POST",
    form: { username: user, password, csrfmiddlewaretoken: token, next: "/" },
    headers: { Referer: base + "/conta/entrar/" },
  });
  const authenticated =
    response.status() === 200 &&
    new URL(response.url()).pathname === "/" &&
    (await response.text()).includes("/conta/sair/");
  await response.dispose();
  if (!authenticated) stop("LOGIN_FAILED");
}
async function prepare(client) {
  browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
    headless: true,
    proxy:
      !local && process.env.HTTPS_PROXY
        ? { server: process.env.HTTPS_PROXY }
        : undefined,
    args: ["--no-sandbox"],
  });
  const guardedContext = async (options = {}) => {
    const context = await browser.newContext({
      ...options,
      serviceWorkers: "block",
    });
    await context.route("**/*", async (route) => {
      report.setup_requests = (report.setup_requests || 0) + 1;
      if (new URL(route.request().url()).origin !== base) {
        report.aborted = "CROSS_ORIGIN_RESOURCE";
        return route.abort();
      }
      if (report.setup_requests > 600) {
        report.aborted = "SETUP_REQUEST_BUDGET_REACHED";
        return route.abort();
      }
      if (performance.now() > deadline) {
        report.aborted = "TIME_BUDGET_REACHED";
        return route.abort();
      }
      return route.continue();
    });
    return context;
  };
  const context = await guardedContext({
    storageState: await client.storageState(),
  });
  const page = await context.newPage();
  page.setDefaultTimeout(20000);
  const marker = "AUTOCARGA-v1-finalizado";
  await page.goto(base + "/materiais/?q=" + marker);
  let reused =
    (await page.locator("table tbody a").filter({ hasText: marker }).count()) >
    0;
  const writeTimes = [];
  const step = async (fn) => {
    budget();
    const start = performance.now();
    await fn();
    writeTimes.push(Math.round(performance.now() - start));
  };
  if (!reused) {
    report.preparation_step = "synthetic_materials";
    for (let i = 1; i <= 5; i++)
      await step(async () => {
        await page.goto(base + "/materiais/novo/");
        await page.locator("#id_name").fill("AUTOCARGA-v1 Fio fictício " + i);
        await page.locator("#id_kind").selectOption("yarn");
        await page.locator("#id_unit").selectOption("g");
        await page.locator("#id_initial_quantity").fill("100");
        await page.locator("#id_initial_unit_cost").fill("0.10");
        await page
          .getByRole("button", { name: "Cadastrar material", exact: true })
          .click();
        await page.waitForURL(/\/materiais\/[a-f0-9-]+\/$/);
      });
    for (let i = 1; i <= 2; i++) {
      report.preparation_step = "synthetic_quote";
      let quotePath, orderPath;
      await step(async () => {
        await page.goto(base + "/orcamentos/novo/");
        if (!(await page.locator("#id_new_client_name").isVisible()))
          await page
            .getByText("Cadastrar novo cliente", { exact: true })
            .click();
        await page
          .locator("#id_new_client_name")
          .fill("AUTOCARGA-v1 Cliente fictício " + i);
        await page
          .locator("#id_terms")
          .fill("Dados fictícios de teste automatizado. Sem cobrança real.");
        await page
          .getByRole("button", { name: "Salvar e continuar", exact: true })
          .click();
        await page.waitForURL(/\/orcamentos\/[a-f0-9-]+\/$/);
        quotePath = new URL(page.url()).pathname;
        await page
          .getByRole("link", { name: "Adicionar primeira peça", exact: true })
          .click();
        await page
          .locator("#id_new_piece_name")
          .fill("AUTOCARGA-v1 Peça fictícia " + i);
        await page.locator("#id_quantity").fill("1");
        await page.locator("#id_manual_price").fill("25");
        await page
          .getByRole("button", { name: /Adicionar|Salvar/ })
          .last()
          .click();
        await page.waitForURL(base + quotePath);
      });
      report.preparation_step = "synthetic_approval";
      await step(async () => {
        await page
          .getByRole("link", { name: "Revisar e publicar", exact: true })
          .click();
        for (const id of ["#id_confirm_limitations", "#id_confirm_below_cost"])
          if (await page.locator(id).count()) await page.locator(id).check();
        await page
          .getByRole("button", { name: "Publicar esta versão", exact: true })
          .click();
        const portal = await page.locator("#share-link").inputValue();
        safeLocation(base, portal);
        const visitor = await guardedContext();
        try {
          const p = await visitor.newPage();
          await p.goto(portal);
          await p.locator("#id_declaration").check();
          await p
            .getByRole("button", { name: "Confirmar decisão", exact: true })
            .click();
          await p.waitForLoadState("load");
        } finally {
          await visitor.close();
        }
        await page.goto(base + quotePath);
        await page
          .getByRole("button", {
            name: "Criar / abrir pedido desta aprovação",
            exact: true,
          })
          .click();
        await page.waitForURL(/\/pedidos\/[a-f0-9-]+\/$/);
        orderPath = new URL(page.url()).pathname;
      });
      report.preparation_step = "synthetic_sessions";
      for (let session = 0; session < 5; session++)
        await step(async () => {
          await page.goto(base + orderPath);
          await page
            .getByRole("link", { name: "Tempo manual", exact: true })
            .click();
          await page.locator("#id_minutes").fill("15");
          const ended = new Intl.DateTimeFormat("sv-SE", {
            timeZone: "America/Sao_Paulo",
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
            hourCycle: "h23",
          })
            .format(
              new Date(Date.now() - (session + (i - 1) * 5 + 1) * 16 * 60000),
            )
            .replace(" ", "T");
          await page.locator("#id_ended_at").fill(ended);
          await page
            .getByRole("button", { name: "Confirmar registro", exact: true })
            .click();
          await page.waitForURL(base + orderPath);
        });
      report.preparation_step = "synthetic_planning_payment";
      await step(async () => {
        await page.goto(base + orderPath + "configuracao/");
        const day = new Date().toLocaleDateString("en-CA", {
          timeZone: "America/Sao_Paulo",
        });
        await page.locator("#id_planned_start").fill(day);
        await page.locator("#id_production_due").fill(day);
        await page
          .getByRole("button", {
            name: /^(Salvar e continuar|Confirmar recebimento)$/,
            exact: true,
          })
          .click();
        await page.waitForURL(base + orderPath);
        await page
          .getByRole("link", { name: "Registrar recebimento", exact: true })
          .click();
        await page.locator("#id_amount").fill("10");
        await page
          .getByRole("button", {
            name: /^(Salvar e continuar|Confirmar recebimento)$/,
            exact: true,
          })
          .click();
        await page.waitForURL(base + orderPath);
      });
    }
    report.preparation_step = "synthetic_marker";
    await step(async () => {
      await page.goto(base + "/materiais/novo/");
      await page.locator("#id_name").fill(marker);
      await page.locator("#id_kind").selectOption("yarn");
      await page.locator("#id_unit").selectOption("g");
      await page.locator("#id_initial_quantity").fill("0");
      await page
        .getByRole("button", { name: "Cadastrar material", exact: true })
        .click();
      await page.waitForURL(/\/materiais\/[a-f0-9-]+\/$/);
    });
  }
  await page.goto(base + "/pedidos/");
  const detail = await page
    .locator('main a[href^="/pedidos/"]')
    .evaluateAll((nodes) =>
      nodes
        .map((n) => n.getAttribute("href"))
        .find((h) => /^\/pedidos\/[a-f0-9-]+\/$/.test(h)),
    );
  if (!detail) stop("SYNTHETIC_ORDER_NOT_FOUND");
  report.fixture = {
    reused,
    version: "v1",
    created: reused
      ? null
      : {
          materials: 6,
          pieces: 2,
          approved_orders: 2,
          manual_sessions: 10,
          payments: 2,
        },
    setup_steps_ms: writeTimes,
    warning:
      "Tempos de preparo incluem navegador e não são amostras de carga HTTP. Não há exclusão automática. Repetir após preparo interrompido pode deixar dados parciais.",
  };
  await context.close();
  await browser.close();
  browser = null;
  return detail;
}
async function phase(clients, routes, users, perRoute, rate, circuit) {
  const name = users + "-sessoes";
  const pacer = new Pacer(rate);
  let cursor = 0,
    inflight = 0,
    maxInflight = 0;
  const tasks = Array.from({ length: perRoute }, () => routes).flat();
  const started = performance.now();
  await Promise.allSettled(
    clients.slice(0, users).map(async (client) => {
      try {
        while (cursor < tasks.length && !circuit.reason) {
          budget();
          const item = tasks[cursor++];
          await pacer.wait();
          if (circuit.reason) break;
          budget();
          const begin = performance.now();
          inflight++;
          maxInflight = Math.max(maxInflight, inflight);
          let sample = {
            phase: name,
            route: item.label,
            status: 0,
            ok: false,
            bytes: 0,
            ms: 0,
          };
          try {
            const response = await http(client, item.path);
            sample.status = response.status();
            sample.bytes = (await response.body()).length;
            sample.ok =
              sample.status === 200 &&
              new URL(response.url()).pathname === item.path;
            if (new URL(response.url()).pathname !== item.path)
              sample.failure = "UNEXPECTED_REDIRECT";
            await response.dispose();
          } catch (error) {
            if (error instanceof Stop) throw error;
          } finally {
            inflight--;
            sample.ms = Math.round((performance.now() - begin) * 100) / 100;
            report.samples.push(sample);
            circuit.observe(sample);
          }
        }
      } catch (error) {
        circuit.reason =
          circuit.reason ||
          (error instanceof Stop ? error.message : "WORKER_FAILED");
        throw error;
      }
    }),
  );
  report.phases.push({
    name,
    virtual_sessions: users,
    max_inflight: maxInflight,
    max_started_requests_per_second: rate,
    per_route_target: perRoute,
    completed: report.samples.filter((s) => s.phase === name).length,
    seconds: Math.round((performance.now() - started) / 10) / 100,
  });
  save();
  if (circuit.reason) stop(circuit.reason);
}
function save() {
  fs.mkdirSync(out, { recursive: true });
  report.finished_at = new Date().toISOString();
  report.summary = aggregate(report.samples);
  const markdown = [
    "# Teste automatizado — Davigurumi",
    "",
    `Início: ${report.started_at}`,
    `Destino: ${report.target}`,
    `Versão: ${report.release || "não conferida"}`,
    `Resultado: ${report.aborted || report.result || "incompleto"}`,
    "",
    report.method,
    "",
    "Primeira chamada de saúde (não comprova cold start): " +
      (report.first_health_ms ?? "não medida") +
      " ms.",
    "",
    "| Fase | Rota | Amostras | Erros | Mediana ms | p95 ms |",
    "| --- | --- | --- | --- | --- | --- |",
    ...report.summary.map(
      (r) =>
        `| ${r.phase} | ${r.route} | ${r.samples} | ${r.errors} | ${r.median_ms} | ${r.p95_ms} |`,
    ),
    "",
    "## Limites",
    "Sessões compartilham uma conta de testes. Não equivale a proprietários distintos. Taxa total limitada; consultar max_inflight para concorrência efetivamente observada. Baseline remoto mira 30 amostras por rota; fases posteriores têm seis. Não mede renderização, tempo puro de servidor, banco ou storage isoladamente. Necessário correlacionar logs do Render para atribuir causas. Não há acesso nem limpeza do beta original. Relatório não guarda credenciais, cookies, corpo HTML ou tokens.",
  ];
  fs.writeFileSync(
    path.join(out, "report.json"),
    JSON.stringify(report, null, 2),
  );
  fs.writeFileSync(path.join(out, "report.md"), markdown.join("\n") + "\n");
}

for (const signal of ["SIGTERM", "SIGINT"])
  process.on(signal, () => {
    report.aborted = "CANCELLED";
    deadline = 0;
    process.exitCode = 1;
    save();
  });

(async () => {
  deadline = performance.now() + (local ? 180000 : 1200000);
  if (process.env.DAVIGURUMI_LOAD_ISOLATED !== "1")
    stop("ISOLATION_ACK_REQUIRED");
  base = validateTarget(process.env.DAVIGURUMI_LOAD_URL || TARGET, local);
  report.target = base;
  report.preparation_step = "credentials";
  const user = process.env.DAVIGURUMI_LOAD_USERNAME,
    password = process.env.DAVIGURUMI_LOAD_PASSWORD;
  if (!user || !password) stop("TEST_CREDENTIALS_REQUIRED");
  const control = await makeClient();
  report.preparation_step = "health";
  const initial = performance.now();
  const health = await http(control, "/healthz/", { timeout: 75000 });
  report.first_health_ms = Math.round(performance.now() - initial);
  if (health.status() !== 200 || (await health.json()).status !== "ok")
    stop("HEALTH_FAILED");
  await health.dispose();
  report.preparation_step = "version";
  const version = await http(control, "/version/");
  const release = (await version.json()).release;
  await version.dispose();
  if (!/^[a-f0-9]{12}$/.test(release) && !local) stop("RELEASE_UNKNOWN");
  report.release = release;
  report.preparation_step = "login";
  await login(control, user, password);
  const detail = await prepare(control);
  const routes = [
    "/",
    "/materiais/",
    "/orcamentos/",
    "/pedidos/",
    "/pedidos/calendario/",
    "/notificacoes/relatorios/",
    "/financeiro/",
  ].map((p) => ({ path: p, label: p }));
  routes.push({ path: detail, label: "/pedidos/:pedido-sintetico/" });
  for (let i = 1; i < 5; i++) await login(await makeClient(), user, password);
  for (const item of routes) {
    const response = await http(control, item.path);
    if (response.status() !== 200) stop("WARMUP_FAILED");
    await response.dispose();
  }
  report.preparation_step = "load";
  const circuit = new Circuit();
  for (const [users, n, rate] of local
    ? [
        [1, 1, 1.5],
        [3, 1, 1.5],
        [5, 1, 1.5],
      ]
    : [
        [1, 30, 0.5],
        [3, 6, 1],
        [5, 6, 1.5],
      ])
    await phase(clients, routes, users, n, rate, circuit);
  const summary = aggregate(report.samples);
  report.result = report.samples.some((sample) => !sample.ok)
    ? "completed_with_errors"
    : summary.some((r) => r.p95_ms > 2500)
      ? "completed_with_latency_alert"
      : "completed";
  if (report.result === "completed_with_errors") process.exitCode = 1;
})()
  .catch((error) => {
    report.aborted =
      report.aborted ||
      (error instanceof Stop
        ? error.message
        : "PREPARATION_OR_EXECUTION_FAILED");
    process.exitCode = 1;
  })
  .finally(async () => {
    if (browser) await browser.close().catch(() => {});
    await Promise.allSettled(clients.map((c) => c.dispose()));
    save();
    console.log(
      JSON.stringify({
        result: report.aborted || report.result,
        requests: report.samples.length,
        output: out,
      }),
    );
  });
