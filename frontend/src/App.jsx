import { useEffect, useState } from "react";
import { api } from "./api";
import Screener from "./components/Screener";
import Analyze from "./components/Analyze";
import Backtest from "./components/Backtest";

const TABS = ["Screener", "Analyze", "Backtest"];

export default function App() {
  const [cfg, setCfg] = useState(null);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState("Screener");

  const [interval, setInterval] = useState("FIVE_MINUTE");
  const [days, setDays] = useState(5);
  const [watchlistText, setWatchlistText] = useState("");
  const [symbol, setSymbol] = useState("");
  const [strategy, setStrategy] = useState("confluence");

  useEffect(() => {
    api
      .config()
      .then((c) => {
        setCfg(c);
        setWatchlistText(c.watchlist.join("\n"));
        setSymbol(c.watchlist[0] || "");
      })
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div className="app">
        <p className="error">
          Cannot reach the API: {error}. Is the Flask backend running on port
          5000?
        </p>
      </div>
    );
  }

  if (!cfg) {
    return (
      <div className="app">
        <p className="muted">Loading...</p>
      </div>
    );
  }

  const symbols = watchlistText
    .split("\n")
    .map((s) => s.trim().toUpperCase())
    .filter(Boolean);

  const live = cfg.provider === "angelone";
  const strategies = cfg.strategies || [];
  const activeStrategy = strategies.find((s) => s.key === strategy);

  const pickSymbol = (s) => {
    setSymbol(s);
    setTab("Analyze");
  };

  return (
    <div className="app">
      <header>
        <h1>📈 Intraday Signals</h1>
        <span className={`badge ${live ? "live" : "mock"}`}>
          {live ? "🟢 Angel One (live)" : "🟡 Mock data"}
        </span>
      </header>

      <div className="controls">
        <label>
          Strategy
          <select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
            {strategies.map((s) => (
              <option key={s.key} value={s.key}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Interval
          <select value={interval} onChange={(e) => setInterval(e.target.value)}>
            {cfg.intervals.map((i) => (
              <option key={i} value={i}>
                {i}
              </option>
            ))}
          </select>
        </label>
        <label>
          History (days)
          <input
            type="number"
            min="2"
            max="15"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          />
        </label>
        <label style={{ flex: 1, minWidth: 240 }}>
          Watchlist (comma or newline separated)
          <input
            type="text"
            value={watchlistText.replace(/\n/g, ", ")}
            onChange={(e) => setWatchlistText(e.target.value.replace(/,/g, "\n"))}
          />
        </label>
      </div>

      {activeStrategy && (
        <p className="muted" style={{ fontSize: 13, marginTop: -4 }}>
          <strong>{activeStrategy.name}:</strong> {activeStrategy.description}
        </p>
      )}

      <div className="tabs">
        {TABS.map((t) => (
          <button
            key={t}
            className={tab === t ? "active" : ""}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Screener" && (
        <Screener
          symbols={symbols}
          interval={interval}
          days={days}
          strategy={strategy}
          onPick={pickSymbol}
        />
      )}
      {tab === "Analyze" && (
        <Analyze
          symbols={symbols}
          symbol={symbol}
          setSymbol={setSymbol}
          interval={interval}
          days={days}
          strategy={strategy}
        />
      )}
      {tab === "Backtest" && (
        <Backtest
          symbols={symbols}
          interval={interval}
          days={days}
          strategy={strategy}
        />
      )}

      <p className="disclaimer">
        ⚠️ Educational tool only. Not investment advice. Intraday trading is
        high-risk. Signals are rule-based and can be wrong. Validate
        independently and always use stop-losses. {!live && "Currently showing synthetic data."}
      </p>
    </div>
  );
}
