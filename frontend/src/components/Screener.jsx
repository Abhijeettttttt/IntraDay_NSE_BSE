import { useState } from "react";
import { api } from "../api";

export default function Screener({ symbols, interval, days, strategy, onPick }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.signals(symbols, interval, days, strategy);
      setRows(data.results);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const counts = rows.reduce(
    (acc, r) => ({ ...acc, [r.signal]: (acc[r.signal] || 0) + 1 }),
    {}
  );

  return (
    <div>
      <div className="panel">
        <button onClick={run} disabled={loading}>
          {loading ? "Scanning..." : "Run scan"}
        </button>
        {error && <p className="error">Error: {error}</p>}
        {rows.length > 0 && (
          <div className="metrics" style={{ marginTop: 16 }}>
            <div className="metric">
              <div className="k">BUY</div>
              <div className="v" style={{ color: "#4ade80" }}>
                {counts.BUY || 0}
              </div>
            </div>
            <div className="metric">
              <div className="k">SELL</div>
              <div className="v" style={{ color: "#f87171" }}>
                {counts.SELL || 0}
              </div>
            </div>
            <div className="metric">
              <div className="k">HOLD</div>
              <div className="v">{counts.HOLD || 0}</div>
            </div>
          </div>
        )}
      </div>

      {rows.length > 0 && (
        <div className="panel">
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Signal</th>
                <th>Score</th>
                <th>Price</th>
                <th>RSI</th>
                <th>VWAP</th>
                <th>RVOL</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.symbol} onClick={() => onPick(r.symbol)}>
                  <td>
                    <strong>{r.symbol}</strong>
                  </td>
                  <td>
                    <span className={`pill ${r.signal}`}>{r.signal}</span>
                  </td>
                  <td>{r.score > 0 ? `+${r.score}` : r.score}</td>
                  <td>{Number.isFinite(r.price) ? `₹${r.price.toFixed(2)}` : "-"}</td>
                  <td>{r.metrics?.rsi ?? "-"}</td>
                  <td>{r.metrics?.vwap ?? "-"}</td>
                  <td>{r.metrics?.rvol ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted" style={{ marginTop: 10, fontSize: 12 }}>
            Click a row to open it in the Analyze tab.
          </p>
        </div>
      )}
    </div>
  );
}
