"""Event-driven backtester + validation metrics for the signal engine.

Walks bar-by-bar, generates a signal using ONLY data up to that bar (no
look-ahead), and simulates a long-only intraday strategy:
  - Enter long on BUY (score >= BUY_THRESHOLD).
  - Exit on SELL (score <= SELL_THRESHOLD) or end-of-day square-off.

On top of the raw simulation it computes risk-adjusted metrics
(Sharpe, max drawdown, profit factor, expectancy) and a buy-and-hold
benchmark, plus a walk-forward (train/test) split helper.

NOTE: On synthetic/mock data these numbers are meaningless — random data
has no edge to find. They only become informative on real historical data.
This module is the measurement framework; the data is what makes it real.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .signals import BUY_THRESHOLD, SELL_THRESHOLD, score_series


@dataclass
class Trade:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    pnl_pct: float
    bars_held: int = 0


@dataclass
class BacktestResult:
    symbol: str
    trades: list[Trade]
    equity_curve: pd.Series
    # headline
    total_return_pct: float = 0.0
    num_trades: int = 0
    win_rate: float = 0.0
    # risk-adjusted
    sharpe: float = 0.0
    max_drawdown_pct: float = 0.0
    profit_factor: float = 0.0
    expectancy_pct: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    avg_bars_held: float = 0.0
    # benchmark
    benchmark_return_pct: float = 0.0
    alpha_pct: float = 0.0  # strategy return - benchmark return
    metrics: dict = field(default_factory=dict)


def _max_drawdown(equity: pd.Series) -> float:
    """Worst peak-to-trough decline of the equity curve, in percent."""
    if equity.empty:
        return 0.0
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max
    return float(drawdown.min() * 100)


def _sharpe(trade_returns: list[float]) -> float:
    """Sharpe on per-trade returns (risk-free = 0). Not annualised — a
    comparative figure. Higher = better return per unit of risk."""
    if len(trade_returns) < 2:
        return 0.0
    r = np.array(trade_returns) / 100.0
    sd = r.std(ddof=1)
    if sd == 0:
        return 0.0
    return float(r.mean() / sd * math.sqrt(len(r)))


def _benchmark_return(bars: pd.DataFrame, warmup: int, cost_pct: float) -> float:
    """Buy-and-hold from first post-warmup close to last close, minus one
    round-trip cost. The baseline every strategy must beat."""
    if len(bars) <= warmup + 1:
        return 0.0
    entry = float(bars["close"].iloc[warmup])
    exit_ = float(bars["close"].iloc[-1])
    return round((exit_ - entry) / entry * 100 - cost_pct, 2)


def run(
    symbol: str,
    bars: pd.DataFrame,
    warmup: int = 30,
    cost_pct: float = 0.05,
    step: int = 1,
    strategy: str | None = None,
) -> BacktestResult:
    """Backtest the signal engine on one symbol's bars.

    cost_pct: round-trip transaction cost as a percent (brokerage+slippage).
    step: evaluate every Nth bar (speed vs. granularity trade-off).
    strategy: strategy key ("confluence" | "orb"); None = default.
    """
    trades: list[Trade] = []
    in_pos = False
    entry_price = 0.0
    entry_time = None
    entry_i = 0
    equity = 1.0
    curve: dict = {}

    idx = bars.index
    close = bars["close"].to_numpy()
    # Precompute all signal scores once (O(n)) — no per-bar re-enrichment.
    scores = score_series(bars, strategy=strategy).to_numpy()

    for i in range(warmup, len(bars), step):
        now = idx[i]
        price = float(close[i])
        score = float(scores[i])

        is_last_of_day = i + 1 >= len(bars) or idx[i + 1].date() != now.date()

        if not in_pos:
            if score >= BUY_THRESHOLD:
                in_pos = True
                entry_price = price
                entry_time = now
                entry_i = i
        else:
            if score <= SELL_THRESHOLD or is_last_of_day:
                gross = (price - entry_price) / entry_price * 100
                net = gross - cost_pct
                trades.append(
                    Trade(entry_time, now, entry_price, price, net, i - entry_i)
                )
                equity *= 1 + net / 100
                in_pos = False
        curve[now] = equity

    equity_curve = pd.Series(curve, name="equity")
    pnls = [t.pnl_pct for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (
        float("inf") if gross_profit > 0 else 0.0
    )

    total_return = (equity - 1) * 100
    win_rate = (len(wins) / len(trades) * 100) if trades else 0.0
    avg_win = (sum(wins) / len(wins)) if wins else 0.0
    avg_loss = (sum(losses) / len(losses)) if losses else 0.0
    # Expectancy: average expected % gain per trade.
    p_win = (len(wins) / len(trades)) if trades else 0.0
    expectancy = p_win * avg_win + (1 - p_win) * avg_loss
    benchmark = _benchmark_return(bars, warmup, cost_pct)

    return BacktestResult(
        symbol=symbol,
        trades=trades,
        equity_curve=equity_curve,
        total_return_pct=round(total_return, 2),
        num_trades=len(trades),
        win_rate=round(win_rate, 1),
        sharpe=round(_sharpe(pnls), 2),
        max_drawdown_pct=round(_max_drawdown(equity_curve), 2),
        profit_factor=round(profit_factor, 2) if math.isfinite(profit_factor) else 999.0,
        expectancy_pct=round(expectancy, 3),
        avg_win_pct=round(avg_win, 2),
        avg_loss_pct=round(avg_loss, 2),
        avg_bars_held=round(np.mean([t.bars_held for t in trades]), 1) if trades else 0.0,
        benchmark_return_pct=benchmark,
        alpha_pct=round(total_return - benchmark, 2),
    )


def walk_forward(
    symbol: str,
    bars: pd.DataFrame,
    train_frac: float = 0.7,
    warmup: int = 30,
    cost_pct: float = 0.05,
    strategy: str | None = None,
) -> dict:
    """Out-of-sample validation: backtest separately on an in-sample
    (train) slice and an out-of-sample (test) slice.

    If test performance collapses versus train, the strategy is overfit.
    Returns both results plus a simple 'holds_up' verdict.
    """
    n = len(bars)
    split = int(n * train_frac)
    if split <= warmup + 5 or (n - split) <= warmup + 5:
        raise ValueError("Not enough bars for a meaningful train/test split.")

    train_bars = bars.iloc[:split]
    test_bars = bars.iloc[split:]

    train = run(symbol, train_bars, warmup=warmup, cost_pct=cost_pct, strategy=strategy)
    test = run(symbol, test_bars, warmup=warmup, cost_pct=cost_pct, strategy=strategy)

    # Verdict: out-of-sample should stay positive and not be a fraction of
    # in-sample. Rough heuristic, not a substitute for judgement.
    holds_up = (
        test.total_return_pct > 0
        and test.sharpe > 0
        and test.total_return_pct >= 0.3 * max(train.total_return_pct, 0.01)
    )
    return {"train": train, "test": test, "holds_up": bool(holds_up)}


def run_batch(
    provider,
    symbols: list[str],
    interval: str = "FIVE_MINUTE",
    days: int = 5,
    cost_pct: float = 0.05,
    strategy: str | None = None,
) -> dict:
    """Backtest every symbol and aggregate portfolio-level stats.

    Averaging across symbols approximates trading the whole watchlist with
    equal weight — a broader validation than a single stock.
    """
    per_symbol: list[BacktestResult] = []
    for sym in symbols:
        try:
            bars = provider.get_historical(sym, interval=interval, days=days)
            per_symbol.append(run(sym, bars, cost_pct=cost_pct, strategy=strategy))
        except Exception:  # noqa: BLE001 — skip bad symbols
            continue

    if not per_symbol:
        return {"per_symbol": [], "aggregate": {}}

    returns = [r.total_return_pct for r in per_symbol]
    benches = [r.benchmark_return_pct for r in per_symbol]
    aggregate = {
        "symbols_tested": len(per_symbol),
        "avg_return_pct": round(float(np.mean(returns)), 2),
        "avg_benchmark_pct": round(float(np.mean(benches)), 2),
        "avg_alpha_pct": round(float(np.mean(returns) - np.mean(benches)), 2),
        "avg_sharpe": round(float(np.mean([r.sharpe for r in per_symbol])), 2),
        "avg_max_drawdown_pct": round(
            float(np.mean([r.max_drawdown_pct for r in per_symbol])), 2
        ),
        "pct_symbols_profitable": round(
            sum(1 for r in returns if r > 0) / len(returns) * 100, 1
        ),
        "total_trades": sum(r.num_trades for r in per_symbol),
    }
    return {"per_symbol": per_symbol, "aggregate": aggregate}
