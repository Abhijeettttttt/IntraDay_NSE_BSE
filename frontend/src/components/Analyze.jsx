import { useEffect, useState } from "react";
import { api } from "../api";
import PriceChart from "./PriceChart";

export default function Analyze({ symbols, symbol, setSymbol, interval, days, strategy }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!symbol) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .analyze(symbol, interval, days, strategy)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [symbol, interval, days, strategy]);

  const sig = data?.signal;

  return (
    <div>
      <div className="panel">
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
      </div>

      {loading && <p className="muted">Loading...</p>}
      {error && <p className="error">Error: {error}</p>}

      {sig && (
        <>
          <div className="panel">
            <div className="metrics">
              <div className="metric">
                <div className="k">Signal</div>
                <div className="v">
                  <span className={`pill ${sig.signal}`}>{sig.signal}</span>
                </div>
              </div>
              <div className="metric">
                <div className="k">Score</div>
                <div className="v">{sig.score > 0 ? `+${sig.score}` : sig.score}</div>
              </div>
              <div className="metric">
                <div className="k">Last price</div>
                <div className="v">₹{sig.price.toFixed(2)}</div>
              </div>
              <div className="metric">
                <div className="k">RSI</div>
                <div className="v">{sig.metrics.rsi}</div>
              </div>
              <div className="metric">
                <div className="k">RVOL</div>
                <div className="v">{sig.metrics.rvol}x</div>
              </div>
              <div className="metric">
                <div className="k">ATR</div>
                <div className="v">{sig.metrics.atr}</div>
              </div>
            </div>
          </div>

          <div className="row">
            <div className="panel">
              <h3 style={{ marginTop: 0 }}>Why this signal?</h3>
              <ul className="reasons">
                {sig.reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
            <div className="panel">
              <h3 style={{ marginTop: 0 }}>Key levels</h3>
              <table>
                <tbody>
                  {sig.metrics.or_high !== undefined ? (
                    <>
                      <tr><td>Opening-range high</td><td>{sig.metrics.or_high ?? "-"}</td></tr>
                      <tr><td>Opening-range low</td><td>{sig.metrics.or_low ?? "-"}</td></tr>
                      <tr><td>VWAP</td><td>{sig.metrics.vwap}</td></tr>
                    </>
                  ) : (
                    <>
                      <tr><td>R2</td><td>{sig.metrics.r2}</td></tr>
                      <tr><td>R1</td><td>{sig.metrics.r1}</td></tr>
                      <tr><td><strong>Pivot</strong></td><td><strong>{sig.metrics.pivot}</strong></td></tr>
                      <tr><td>S1</td><td>{sig.metrics.s1}</td></tr>
                      <tr><td>S2</td><td>{sig.metrics.s2}</td></tr>
                    </>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="panel">
            <h3 style={{ marginTop: 0 }}>
              {symbol} — price, VWAP (orange), EMA9 (blue), EMA20 (purple)
            </h3>
            <PriceChart candles={data.candles} overlays={data.overlays} />
          </div>
        </>
      )}
    </div>
  );
}
