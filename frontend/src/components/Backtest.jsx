import { useEffect, useRef, useState } from "react";
import { createChart } from "lightweight-charts";
import { api } from "../api";

function EquityChart({ curve }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!ref.current || !curve?.length) return;
    const chart = createChart(ref.current, {
      layout: { background: { color: "#1e293b" }, textColor: "#e2e8f0" },
      grid: {
        vertLines: { color: "#334155" },
        horzLines: { color: "#334155" },
      },
      timeScale: { timeVisible: true, secondsVisible: false },
      autoSize: true,
    });
    const s = chart.addAreaSeries({
      lineColor: "#16a34a",
      topColor: "rgba(22,163,74,0.4)",
      bottomColor: "rgba(22,163,74,0.02)",
    });
    s.setData(
      curve.map((p) => ({
        time: Math.floor(new Date(p.time).getTime() / 1000),
        value: p.equity_pct,
      }))
    );
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [curve]);
  return <div ref={ref} className="chart" style={{ height: 320 }} />;
}

function Metric({ label, value, good, hint }) {
  const color =
    good === undefined ? undefined : good ? "#4ade80" : "#f87171";
  return (
    <div className="metric" title={hint || ""}>
      <div className="k">{label}</div>
      <div className="v" style={{ color }}>
        {value}
      </div>
    </div>
  );
}

// Renders the full metric grid for one backtest summary.
function MetricGrid({ r }) {
  return (
    <div className="metrics">
      <Metric
        label="Strategy return"
        value={`${r.total_return_pct > 0 ? "+" : ""}${r.total_return_pct}%`}
        good={r.total_return_pct >= 0}
        hint="Total % return over the tested period"
      />
      <Metric
        label="Buy & hold"
        value={`${r.benchmark_return_pct > 0 ? "+" : ""}${r.benchmark_return_pct}%`}
        hint="Baseline: just holding the stock. Strategy must beat this."
      />
      <Metric
        label="Alpha"
        value={`${r.alpha_pct > 0 ? "+" : ""}${r.alpha_pct}%`}
        good={r.alpha_pct >= 0}
        hint="Strategy return minus buy & hold. Positive = added value."
      />
      <Metric
        label="Sharpe"
        value={r.sharpe}
        good={r.sharpe >= 1}
        hint="Return per unit of risk. >1 good, >2 very good."
      />
      <Metric
        label="Max drawdown"
        value={`${r.max_drawdown_pct}%`}
        good={r.max_drawdown_pct > -10}
        hint="Worst peak-to-trough drop. Closer to 0 is better."
      />
      <Metric
        label="Profit factor"
        value={r.profit_factor}
        good={r.profit_factor >= 1.5}
        hint="Gross profit / gross loss. >1.5 is decent."
      />
      <Metric
        label="Win rate"
        value={`${r.win_rate}%`}
        hint="Share of trades that were profitable"
      />
      <Metric
        label="Expectancy"
        value={`${r.expectancy_pct}%`}
        good={r.expectancy_pct >= 0}
        hint="Average expected % gain per trade"
      />
      <Metric label="Trades" value={r.num_trades} />
    </div>
  );
}

export default function Backtest({ symbols, interval, days, strategy }) {
  const [mode, setMode] = useState("single"); // "single" | "portfolio"
  const [symbol, setSymbol] = useState(symbols[0] || "");
  const [cost, setCost] = useState(0.05);
  const [walk, setWalk] = useState(true);
  const [result, setResult] = useState(null);
  const [batch, setBatch] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!symbol && symbols.length) setSymbol(symbols[0]);
  }, [symbols]);

  const runSingle = async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await api.backtest({
        symbol,
        interval,
        days,
        cost_pct: Number(cost),
        walk_forward: walk,
        strategy,
      });
      setResult(d);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const runPortfolio = async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await api.backtestBatch({
        symbols,
        interval,
        days,
        cost_pct: Number(cost),
        strategy,
      });
      setBatch(d);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const wf = result?.walk_forward;

  return (
    <div>
      <div className="panel">
        <div className="tabs" style={{ margin: "0 0 12px" }}>
          <button
            className={mode === "single" ? "active" : ""}
            onClick={() => setMode("single")}
          >
            Single stock
          </button>
          <button
            className={mode === "portfolio" ? "active" : ""}
            onClick={() => setMode("portfolio")}
          >
            Portfolio (whole watchlist)
          </button>
        </div>

        <div className="controls">
          {mode === "single" && (
            <label>
              Symbol
              <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
                {symbols.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label>
            Round-trip cost %
            <input
              type="number"
              step="0.01"
              min="0"
              max="1"
              value={cost}
              onChange={(e) => setCost(e.target.value)}
            />
          </label>
          {mode === "single" && (
            <label style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
              <input
                type="checkbox"
                checked={walk}
                onChange={(e) => setWalk(e.target.checked)}
              />
              Walk-forward (out-of-sample) test
            </label>
          )}
          <button
            onClick={mode === "single" ? runSingle : runPortfolio}
            disabled={loading}
          >
            {loading ? "Running..." : "Run backtest"}
          </button>
        </div>
        {error && <p className="error">Error: {error}</p>}
        <p className="muted" style={{ fontSize: 12 }}>
          Long-only intraday sim with end-of-day square-off, no look-ahead.
          Metrics are only meaningful on live/historical data — on mock data
          they're noise.
        </p>
      </div>

      {mode === "single" && result && (
        <>
          <div className="panel">
            <h3 style={{ marginTop: 0 }}>{result.symbol} — full-period metrics</h3>
            <MetricGrid r={result} />
          </div>

          {wf && !wf.error && (
            <div className="panel">
              <h3 style={{ marginTop: 0 }}>
                Walk-forward validation{" "}
                <span
                  className={`pill ${wf.holds_up ? "BUY" : "SELL"}`}
                  style={{ fontSize: 12 }}
                >
                  {wf.holds_up ? "HOLDS UP" : "OVERFIT RISK"}
                </span>
              </h3>
              <p className="muted" style={{ fontSize: 13 }}>
                Trained on the first 70% of data, tested on the unseen last 30%.
                If the test result collapses versus training, the strategy is
                likely overfit.
              </p>
              <div className="row">
                <div>
                  <h4 className="muted">In-sample (train)</h4>
                  <MetricGrid r={wf.train} />
                </div>
                <div>
                  <h4 className="muted">Out-of-sample (test)</h4>
                  <MetricGrid r={wf.test} />
                </div>
              </div>
            </div>
          )}
          {wf?.error && (
            <div className="panel">
              <p className="muted">Walk-forward: {wf.error}</p>
            </div>
          )}

          {result.equity_curve.length > 0 && (
            <div className="panel">
              <h3 style={{ marginTop: 0 }}>Equity curve (% return)</h3>
              <EquityChart curve={result.equity_curve} />
            </div>
          )}

          {result.trades.length > 0 && (
            <div className="panel">
              <table>
                <thead>
                  <tr>
                    <th>Entry</th>
                    <th>Exit</th>
                    <th>Entry ₹</th>
                    <th>Exit ₹</th>
                    <th>Bars</th>
                    <th>PnL %</th>
                  </tr>
                </thead>
                <tbody>
                  {result.trades.map((t, i) => (
                    <tr key={i}>
                      <td>{new Date(t.entry_time).toLocaleString()}</td>
                      <td>{new Date(t.exit_time).toLocaleString()}</td>
                      <td>{t.entry_price}</td>
                      <td>{t.exit_price}</td>
                      <td>{t.bars_held}</td>
                      <td style={{ color: t.pnl_pct >= 0 ? "#4ade80" : "#f87171" }}>
                        {t.pnl_pct > 0 ? "+" : ""}
                        {t.pnl_pct}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {mode === "portfolio" && batch && (
        <>
          <div className="panel">
            <h3 style={{ marginTop: 0 }}>
              Portfolio aggregate ({batch.aggregate.symbols_tested} symbols)
            </h3>
            <div className="metrics">
              <Metric
                label="Avg return"
                value={`${batch.aggregate.avg_return_pct}%`}
                good={batch.aggregate.avg_return_pct >= 0}
              />
              <Metric
                label="Avg buy & hold"
                value={`${batch.aggregate.avg_benchmark_pct}%`}
              />
              <Metric
                label="Avg alpha"
                value={`${batch.aggregate.avg_alpha_pct}%`}
                good={batch.aggregate.avg_alpha_pct >= 0}
              />
              <Metric
                label="Avg Sharpe"
                value={batch.aggregate.avg_sharpe}
                good={batch.aggregate.avg_sharpe >= 1}
              />
              <Metric
                label="Avg max DD"
                value={`${batch.aggregate.avg_max_drawdown_pct}%`}
              />
              <Metric
                label="% profitable"
                value={`${batch.aggregate.pct_symbols_profitable}%`}
                good={batch.aggregate.pct_symbols_profitable >= 50}
              />
              <Metric label="Total trades" value={batch.aggregate.total_trades} />
            </div>
          </div>

          <div className="panel">
            <table>
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Return</th>
                  <th>Buy & hold</th>
                  <th>Alpha</th>
                  <th>Sharpe</th>
                  <th>Max DD</th>
                  <th>Trades</th>
                </tr>
              </thead>
              <tbody>
                {batch.per_symbol.map((r) => (
                  <tr key={r.symbol}>
                    <td>
                      <strong>{r.symbol}</strong>
                    </td>
                    <td style={{ color: r.total_return_pct >= 0 ? "#4ade80" : "#f87171" }}>
                      {r.total_return_pct}%
                    </td>
                    <td>{r.benchmark_return_pct}%</td>
                    <td style={{ color: r.alpha_pct >= 0 ? "#4ade80" : "#f87171" }}>
                      {r.alpha_pct}%
                    </td>
                    <td>{r.sharpe}</td>
                    <td>{r.max_drawdown_pct}%</td>
                    <td>{r.num_trades}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
