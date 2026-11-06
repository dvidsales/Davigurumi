"use strict";
const { performance } = require("node:perf_hooks");
const TARGET = "https://davigurumi-carga.onrender.com";
function validateTarget(value, local = false) {
  const url = new URL(value);
  if (
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    url.pathname !== "/"
  )
    throw Error("INVALID_TARGET");
  if (local) {
    if (
      url.protocol !== "http:" ||
      !["127.0.0.1", "localhost", "[::1]"].includes(url.hostname)
    )
      throw Error("INVALID_LOCAL_TARGET");
  } else if (url.origin !== TARGET) throw Error("ONLY_ISOLATED_TARGET_ALLOWED");
  return url.origin;
}
function percentile(values, proportion) {
  if (!values.length) return null;
  const ordered = [...values].sort((a, b) => a - b);
  return (
    Math.round(
      ordered[Math.max(0, Math.ceil(ordered.length * proportion) - 1)] * 100,
    ) / 100
  );
}
function median(values) {
  if (!values.length) return null;
  const ordered = [...values].sort((a, b) => a - b),
    n = ordered.length;
  return (
    Math.round(
      ((ordered[Math.floor((n - 1) / 2)] + ordered[Math.floor(n / 2)]) / 2) *
        100,
    ) / 100
  );
}
function aggregate(samples) {
  const groups = new Map();
  for (const sample of samples) {
    const key = sample.phase + "|" + sample.route;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(sample);
  }
  return [...groups.values()].map((rows) => ({
    phase: rows[0].phase,
    route: rows[0].route,
    samples: rows.length,
    errors: rows.filter((r) => !r.ok).length,
    statuses: rows.reduce(
      (out, r) => ((out[r.status] = (out[r.status] || 0) + 1), out),
      {},
    ),
    median_ms: median(rows.map((r) => r.ms)),
    p95_ms: percentile(
      rows.map((r) => r.ms),
      0.95,
    ),
    max_ms: percentile(
      rows.map((r) => r.ms),
      1,
    ),
    response_bytes: rows.reduce((n, r) => n + r.bytes, 0),
  }));
}
class Pacer {
  constructor(
    rate,
    now = () => performance.now(),
    sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
  ) {
    if (!(rate > 0 && rate <= 1.5)) throw Error("INVALID_RATE");
    this.interval = 1000 / rate;
    this.now = now;
    this.sleep = sleep;
    this.next = now();
  }
  async wait() {
    // Reserve globally before await, so workers cannot each consume the full rate.
    const now = this.now();
    const slot = Math.max(now, this.next);
    this.next = slot + this.interval;
    if (slot > now) await this.sleep(slot - now);
  }
}
class Circuit {
  constructor() {
    this.recent = [];
    this.slow = 0;
    this.reason = null;
  }
  observe(sample) {
    this.recent.push(sample);
    if (this.recent.length > 20) this.recent.shift();
    this.slow = sample.ms > 10000 ? this.slow + 1 : 0;
    if (sample.failure === "UNEXPECTED_REDIRECT")
      this.reason = "AUTHENTICATION_REDIRECT";
    else if ([401, 403, 429].includes(sample.status))
      this.reason = "ACCESS_OR_RATE_LIMIT";
    else if (
      this.recent.slice(-3).length === 3 &&
      this.recent.slice(-3).every((r) => !r.ok)
    )
      this.reason = "THREE_CONSECUTIVE_ERRORS";
    else if (
      this.recent.length >= 10 &&
      this.recent.filter((r) => !r.ok).length / this.recent.length > 0.1
    )
      this.reason = "ERROR_RATE_OVER_TEN_PERCENT";
    else if (this.slow >= 3) this.reason = "THREE_RESPONSES_OVER_TEN_SECONDS";
    return this.reason;
  }
}
function safeLocation(base, location) {
  const target = new URL(location, base);
  if (
    target.origin !== new URL(base).origin ||
    target.username ||
    target.password
  )
    throw Error("CROSS_ORIGIN_REDIRECT");
  return target.href;
}
module.exports = {
  TARGET,
  validateTarget,
  percentile,
  median,
  aggregate,
  Pacer,
  Circuit,
  safeLocation,
};
