// Thin API client. All requests go through the Vite proxy to Flask.
const BASE = "/api";

async function get(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `HTTP ${res.status}`);
  }
  return res.json();
}

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const b = await res.json().catch(() => ({}));
    throw new Error(b.error || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  config: () => get("/config"),
  signals: (symbols, interval, days, strategy) =>
    get(
      `/signals?symbols=${encodeURIComponent(symbols.join(","))}` +
        `&interval=${interval}&days=${days}&strategy=${strategy || ""}`
    ),
  analyze: (symbol, interval, days, strategy) =>
    get(
      `/analyze/${encodeURIComponent(symbol)}?interval=${interval}` +
        `&days=${days}&strategy=${strategy || ""}`
    ),
  backtest: (payload) => post("/backtest", payload),
  backtestBatch: (payload) => post("/backtest/batch", payload),
};
