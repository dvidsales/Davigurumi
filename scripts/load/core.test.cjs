"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const {
  validateTarget,
  percentile,
  median,
  aggregate,
  Pacer,
  Circuit,
  safeLocation,
} = require("./core.cjs");
test("target refuses production, credentials, arbitrary domains and modified paths", () => {
  assert.equal(
    validateTarget("https://davigurumi-carga.onrender.com"),
    "https://davigurumi-carga.onrender.com",
  );
  for (const url of [
    "https://davigurumi-beta.onrender.com",
    "http://davigurumi-carga.onrender.com",
    "https://u:p@davigurumi-carga.onrender.com",
    "https://davigurumi-carga.onrender.com/x",
    "https://davigurumi-carga.onrender.com?x=1",
    "https://davigurumi-carga.onrender.com.evil.test",
  ])
    assert.throws(() => validateTarget(url));
  assert.equal(
    validateTarget("http://127.0.0.1:8120", true),
    "http://127.0.0.1:8120",
  );
  assert.throws(() => validateTarget("http://example.test", true));
});
test("redirects cannot leak authenticated requests to another origin", () => {
  assert.equal(
    safeLocation("https://davigurumi-carga.onrender.com", "/materiais/"),
    "https://davigurumi-carga.onrender.com/materiais/",
  );
  for (const to of [
    "https://evil.test",
    "//evil.test",
    "http://davigurumi-carga.onrender.com",
    "https://u:p@davigurumi-carga.onrender.com",
  ])
    assert.throws(() =>
      safeLocation("https://davigurumi-carga.onrender.com", to),
    );
});
test("nearest-rank p95 and route/phase grouping have correct sample/error counts", () => {
  assert.equal(
    percentile(
      Array.from({ length: 100 }, (_, i) => i + 1),
      0.95,
    ),
    95,
  );
  assert.equal(percentile([], 0.95), null);
  assert.equal(median([10, 20]), 15);
  assert.equal(median([10, 20, 30]), 20);
  const rows = aggregate([
    { phase: "a", route: "/", status: 200, ok: true, ms: 10, bytes: 100 },
    { phase: "a", route: "/", status: 500, ok: false, ms: 20, bytes: 10 },
    { phase: "b", route: "/", status: 200, ok: true, ms: 5, bytes: 5 },
  ]);
  assert.equal(rows.length, 2);
  assert.equal(rows[0].samples, 2);
  assert.equal(rows[0].errors, 1);
  assert.equal(rows[0].p95_ms, 20);
  assert.equal(rows[0].response_bytes, 110);
});
test("global pacer shares slots across workers instead of multiplying rate", async () => {
  const waits = [];
  const pacer = new Pacer(
    1,
    () => 0,
    async (ms) => waits.push(ms),
  );
  await Promise.all([pacer.wait(), pacer.wait(), pacer.wait()]);
  assert.deepEqual(waits, [1000, 2000]);
  assert.throws(() => new Pacer(10));
});
test("circuit immediately stops on access failures and quota; does not retry", () => {
  for (const status of [401, 403, 429]) {
    const c = new Circuit();
    assert.equal(
      c.observe({ status, ok: false, ms: 1 }),
      "ACCESS_OR_RATE_LIMIT",
    );
  }
});
test("circuit stops unexpected login redirects even with HTTP 200", () => {
  const circuit = new Circuit();
  assert.equal(
    circuit.observe({
      status: 200,
      ok: false,
      ms: 100,
      failure: "UNEXPECTED_REDIRECT",
    }),
    "AUTHENTICATION_REDIRECT",
  );
});
test("circuit stops repeated failures and slow responses while accepting successes", () => {
  const errors = new Circuit();
  for (let i = 0; i < 2; i++)
    assert.equal(errors.observe({ status: 500, ok: false, ms: 1 }), null);
  assert.equal(
    errors.observe({ status: 500, ok: false, ms: 1 }),
    "THREE_CONSECUTIVE_ERRORS",
  );
  const slow = new Circuit();
  for (let i = 0; i < 2; i++)
    assert.equal(slow.observe({ status: 200, ok: true, ms: 10001 }), null);
  assert.equal(
    slow.observe({ status: 200, ok: true, ms: 10001 }),
    "THREE_RESPONSES_OVER_TEN_SECONDS",
  );
  const fast = new Circuit();
  for (let i = 0; i < 50; i++)
    assert.equal(fast.observe({ status: 200, ok: true, ms: 100 }), null);
});
