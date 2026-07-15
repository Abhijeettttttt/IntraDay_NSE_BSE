# Intraday Signals (Indian Stocks)

An educational intraday screener + signal engine for NSE stocks, with a
**Flask REST API backend** and a **React (Vite) frontend**. Runs on synthetic
data out of the box, and swaps to live **Angel One SmartAPI** data by changing
one env var — no code changes.

> ⚠️ **Disclaimer:** Educational tool only. **Not investment advice.** Intraday
> trading is high-risk and most beginners lose money. Signals are rule-based
> and can be wrong. Validate independently and always use stop-losses. Publicly
> distributing buy/sell recommendations in India may require SEBI registration.

## Features
- **Screener** — scan a watchlist, rank stocks by signal conviction.
- **Analyze** — per-stock candlestick chart with VWAP, EMA9/20, volume, RSI.
- **Signal engine** — transparent weighted rules (VWAP, EMA cross, RSI, MACD, RVOL).
- **Backtester** — long-only intraday simulation with end-of-day square-off.
- **Pluggable data layer** — `mock` (default) or `angelone`.

## Quick start (mock data, no credentials)

Two processes: the Flask API and the React dev server.

**Terminal 1 — backend (port 5000):**
```bash
pip install -r requirements.txt
python -m backend.app
```

**Terminal 2 — frontend (port 5173):**
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173  (the Vite dev server proxies `/api` to Flask).

## Verify the engine (no UI)
```bash
python smoke_test.py
```

## Production build of the frontend
```bash
cd frontend
npm run build      # outputs static files to frontend/dist
```
Serve `frontend/dist` behind any static host / reverse proxy, and run Flask
with a WSGI server (e.g. `waitress-serve --port=5000 backend.app:app`).

## API endpoints
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | liveness + active provider |
| GET | `/api/config` | provider, intervals, watchlist |
| GET | `/api/signals?symbols=A,B&interval=&days=` | screener scan |
| GET | `/api/analyze/<symbol>?interval=&days=` | signal + candles + overlays |
| POST | `/api/backtest` | `{symbol, interval, days, cost_pct}` |

## Switch to live Angel One data
1. Get SmartAPI credentials from https://smartapi.angelbroking.com
2. Install broker packages:
   ```bash
   pip install smartapi-python pyotp websocket-client
   ```
3. Copy `.env.example` to `.env` and fill in:
   ```
   ANGELONE_API_KEY=...
   ANGELONE_CLIENT_CODE=...
   ANGELONE_MPIN=...
   ANGELONE_TOTP_SECRET=...      # base32 secret from the authenticator setup
   DATA_PROVIDER=angelone
   ```
4. Restart the app. The sidebar badge turns 🟢 **Angel One (live)**.

## Project structure
```
config.py                  # settings + credentials (from .env)
smoke_test.py              # end-to-end sanity check on mock data
app.py                     # legacy Streamlit UI (optional; not required)

backend/
  app.py                   # Flask REST API (reuses src/ engine)

frontend/                  # React + Vite single-page app
  index.html
  vite.config.js           # dev proxy /api -> Flask :5000
  src/
    main.jsx, App.jsx
    api.js                 # fetch client
    components/
      Screener.jsx, Analyze.jsx, Backtest.jsx, PriceChart.jsx

src/                       # shared engine (used by both Flask and Streamlit)
  data/
    base.py                # DataProvider interface
    mock_provider.py       # synthetic OHLCV generator
    angelone_provider.py   # SmartAPI implementation (login, candles, LTP)
    __init__.py            # provider factory (mock <-> angelone)
  indicators.py            # VWAP, RSI, MACD, EMA, ATR, RVOL(+series), pivots
  strategies/
    base.py                # Strategy interface
    confluence.py          # multi-indicator strategy (+HTF/ATR/smoothing)
    orb.py                 # Opening Range Breakout strategy
    __init__.py            # strategy registry
  signals.py               # facade: generate()/score_series() over strategies
  screener.py              # watchlist scan + ranking
  backtest.py              # intraday backtester + validation metrics
```

## Strategies

Pick a strategy from the dropdown in the header. Each produces a causal
per-bar score in [-100, +100]; `≥ +35 → BUY`, `≤ -35 → SELL`, else `HOLD`.
Strategies live in `src/strategies/` — add one and it appears everywhere
(screener, analyze, backtest) automatically via the registry.

### 1. Confluence (multi-indicator) — the default
Weighted blend of five signals, then filtered:

| Rule | Weight | Bullish when |
|------|--------|--------------|
| Price vs VWAP | 25 | price above VWAP |
| EMA 9/20 cross | 20 | EMA9 above EMA20 |
| RSI | 15 | oversold (<30) |
| MACD | 20 | histogram > 0 and MACD > signal |
| Relative volume | 20 | RVOL ≥ 1.5x (reinforces direction) |

Plus three upgrades (in `src/strategies/confluence.py`):
- **Higher-timeframe trend filter** — resamples the same bars to ~6x the
  interval; scores that fight the larger trend are dampened.
- **ATR volatility gate** — when the stock is barely moving (low ATR%),
  scores are dampened (intraday setups need range).
- **Whipsaw smoothing** — the raw score is lightly smoothed so a single
  noisy bar doesn't flip the signal.

### 2. Opening Range Breakout (ORB)
The most widely-documented intraday strategy (`src/strategies/orb.py`):
- Defines the **opening range** = high/low of the first 15 minutes.
- **Long** on a break above the range high, **short** below the range low.
- Confirms with **VWAP** (long only above, short only below) and relative
  volume, to filter false breakouts.
- Neutral before the opening range forms or while price is inside it.

## Validating the model

The **Backtest** tab is the validation framework. It runs a no-look-ahead,
long-only intraday simulation and reports:

- **Strategy return vs Buy & Hold (benchmark) → Alpha** — did the strategy add
  value over just holding the stock?
- **Sharpe ratio** — return per unit of risk (>1 good).
- **Max drawdown** — worst peak-to-trough loss.
- **Profit factor** — gross profit / gross loss (>1.5 decent).
- **Win rate + expectancy** — quality of trades.

Two modes:
- **Single stock** — with an optional **walk-forward test**: trains on the
  first 70% of data and tests on the unseen last 30%. If test performance
  collapses vs training, the strategy is **overfit**. Verdict shown as
  HOLDS UP / OVERFIT RISK.
- **Portfolio** — runs the whole watchlist and aggregates (avg return, avg
  alpha, avg Sharpe, % of symbols profitable).

> **Important:** on the default mock data these numbers are meaningless —
> synthetic random-walk data has no real edge to find. They only become
> informative once `DATA_PROVIDER=angelone` feeds real historical bars.
> After a positive backtest, the next step is **paper trading** (live data,
> fake money) for several weeks before risking real capital.

Performance note: signal scoring is fully vectorised and causal, so a
backtest over one symbol runs in well under a second even on months of
intraday bars.

## Roadmap
- [ ] Live WebSocket ticks (SmartAPI streaming) for real-time updates
- [ ] More strategies (ORB, mean-reversion) + strategy selector
- [ ] Proper walk-forward backtest with slippage/impact modelling
- [ ] Alerts (email/Telegram) on new signals
- [ ] Auth + multi-user if productionised (plus SEBI/data-license review)
```
