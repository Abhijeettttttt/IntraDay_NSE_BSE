"""Flask REST API for the intraday signals engine.

Reuses the same engine in `src/` that powered the Streamlit prototype:
data layer (mock / Angel One), indicators, signals, screener, backtest.

Run (from project root):
    python -m backend.app
or:
    flask --app backend.app run --port 5000

Endpoints:
    GET  /api/health
    GET  /api/config
    GET  /api/signals?symbols=A,B&interval=FIVE_MINUTE&days=5
    GET  /api/analyze/<symbol>?interval=FIVE_MINUTE&days=5
    POST /api/backtest   {symbol, interval, days, cost_pct}
"""
from __future__ import annotations

import os
import sys

# Make the project root importable so `config` and `src` resolve when this
# module is run in different ways.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import asdict

import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS

from config import settings
from src import backtest as bt
from src import indicators as ind
from src import screener
from src.data import get_provider
from src.signals import generate
from src.strategies import list_strategies

app = Flask(__name__)
CORS(app)  # dev: allow the Vite dev server origin

INTERVALS = [
    "ONE_MINUTE",
    "THREE_MINUTE",
    "FIVE_MINUTE",
    "TEN_MINUTE",
    "FIFTEEN_MINUTE",
    "THIRTY_MINUTE",
    "ONE_HOUR",
]

# One shared provider instance (login/session reuse for Angel One).
_provider = None


def provider():
    global _provider
    if _provider is None:
        _provider = get_provider()
    return _provider


def _result_summary(r) -> dict:
    """Serialise a BacktestResult's headline + risk metrics (no curve/trades)."""
    return {
        "symbol": r.symbol,
        "total_return_pct": r.total_return_pct,
        "benchmark_return_pct": r.benchmark_return_pct,
        "alpha_pct": r.alpha_pct,
        "num_trades": r.num_trades,
        "win_rate": r.win_rate,
        "sharpe": r.sharpe,
        "max_drawdown_pct": r.max_drawdown_pct,
        "profit_factor": r.profit_factor,
        "expectancy_pct": r.expectancy_pct,
        "avg_win_pct": r.avg_win_pct,
        "avg_loss_pct": r.avg_loss_pct,
        "avg_bars_held": r.avg_bars_held,
    }


def _parse_params():
    interval = request.args.get("interval", "FIVE_MINUTE")
    if interval not in INTERVALS:
        interval = "FIVE_MINUTE"
    try:
        days = int(request.args.get("days", 5))
    except ValueError:
        days = 5
    days = max(2, min(days, 15))
    strategy = request.args.get("strategy") or None
    return interval, days, strategy


# ---------------------------------------------------------------- endpoints
@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "provider": provider().name})


@app.get("/api/config")
def get_config():
    return jsonify(
        {
            "provider": settings.data_provider,
            "angelone_ready": settings.angelone_ready,
            "intervals": INTERVALS,
            "watchlist": settings.watchlist,
            "strategies": list_strategies(),
        }
    )


@app.get("/api/strategies")
def strategies():
    return jsonify({"strategies": list_strategies()})


@app.get("/api/signals")
def signals():
    interval, days, strategy = _parse_params()
    symbols_arg = request.args.get("symbols", "")
    symbols = [s.strip().upper() for s in symbols_arg.split(",") if s.strip()]
    if not symbols:
        symbols = settings.watchlist

    results = screener.scan(provider(), symbols, interval, days, strategy=strategy)
    return jsonify(
        {
            "interval": interval,
            "days": days,
            "strategy": strategy,
            "results": [asdict(r) for r in results],
        }
    )


@app.get("/api/analyze/<symbol>")
def analyze(symbol: str):
    interval, days, strategy = _parse_params()
    symbol = symbol.upper()
    try:
        bars = provider().get_historical(symbol, interval=interval, days=days)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 400
    if bars is None or bars.empty:
        return jsonify({"error": "no data for symbol"}), 404

    res = generate(symbol, bars, strategy=strategy)
    enriched = ind.enrich(bars)

    def _series(col):
        return [None if pd.isna(v) else round(float(v), 4) for v in enriched[col]]

    candles = [
        {
            "time": ts.isoformat(),
            "open": round(float(row["open"]), 2),
            "high": round(float(row["high"]), 2),
            "low": round(float(row["low"]), 2),
            "close": round(float(row["close"]), 2),
            "volume": int(row["volume"]),
        }
        for ts, row in bars.iterrows()
    ]

    return jsonify(
        {
            "signal": asdict(res),
            "candles": candles,
            "overlays": {
                "time": [ts.isoformat() for ts in enriched.index],
                "vwap": _series("vwap"),
                "ema9": _series("ema9"),
                "ema20": _series("ema20"),
                "rsi": _series("rsi"),
            },
        }
    )


@app.post("/api/backtest")
def backtest():
    body = request.get_json(silent=True) or {}
    symbol = str(body.get("symbol", "")).upper()
    interval = body.get("interval", "FIVE_MINUTE")
    if interval not in INTERVALS:
        interval = "FIVE_MINUTE"
    days = int(body.get("days", 5))
    days = max(2, min(days, 15))
    cost_pct = float(body.get("cost_pct", 0.05))
    strategy = body.get("strategy") or None

    if not symbol:
        return jsonify({"error": "symbol required"}), 400
    try:
        bars = provider().get_historical(symbol, interval=interval, days=days)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 400
    if bars is None or bars.empty:
        return jsonify({"error": "no data for symbol"}), 404

    result = bt.run(symbol, bars, cost_pct=cost_pct, strategy=strategy)

    # Optional walk-forward (out-of-sample) validation.
    walk = None
    if bool(body.get("walk_forward", False)):
        try:
            wf = bt.walk_forward(symbol, bars, cost_pct=cost_pct, strategy=strategy)
            walk = {
                "holds_up": wf["holds_up"],
                "train": _result_summary(wf["train"]),
                "test": _result_summary(wf["test"]),
            }
        except ValueError as exc:
            walk = {"error": str(exc)}

    return jsonify(
        {
            **_result_summary(result),
            "equity_curve": [
                {"time": ts.isoformat(), "equity_pct": round((v - 1) * 100, 3)}
                for ts, v in result.equity_curve.items()
            ],
            "trades": [
                {
                    "entry_time": t.entry_time.isoformat(),
                    "exit_time": t.exit_time.isoformat(),
                    "entry_price": round(t.entry_price, 2),
                    "exit_price": round(t.exit_price, 2),
                    "pnl_pct": round(t.pnl_pct, 2),
                    "bars_held": t.bars_held,
                }
                for t in result.trades
            ],
            "walk_forward": walk,
        }
    )


@app.post("/api/backtest/batch")
def backtest_batch():
    """Backtest the whole watchlist and return portfolio-level aggregates."""
    body = request.get_json(silent=True) or {}
    symbols = [s.strip().upper() for s in body.get("symbols", []) if s.strip()]
    if not symbols:
        symbols = settings.watchlist
    interval = body.get("interval", "FIVE_MINUTE")
    if interval not in INTERVALS:
        interval = "FIVE_MINUTE"
    days = max(2, min(int(body.get("days", 5)), 15))
    cost_pct = float(body.get("cost_pct", 0.05))
    strategy = body.get("strategy") or None

    out = bt.run_batch(provider(), symbols, interval, days, cost_pct, strategy=strategy)
    return jsonify(
        {
            "aggregate": out["aggregate"],
            "per_symbol": [_result_summary(r) for r in out["per_symbol"]],
        }
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
