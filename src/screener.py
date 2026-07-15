"""Screener: scan a watchlist and rank stocks by signal strength."""
from __future__ import annotations

import pandas as pd

from .data import DataProvider
from .signals import SignalResult, generate


def scan(
    provider: DataProvider,
    symbols: list[str],
    interval: str = "FIVE_MINUTE",
    days: int = 5,
    strategy: str | None = None,
) -> list[SignalResult]:
    """Run the signal engine across all symbols. Errors are isolated per symbol."""
    results: list[SignalResult] = []
    for sym in symbols:
        try:
            bars = provider.get_historical(sym, interval=interval, days=days)
            results.append(generate(sym, bars, strategy=strategy))
        except Exception as exc:  # noqa: BLE001 — one bad symbol shouldn't kill the scan
            results.append(
                SignalResult(sym, "HOLD", 0.0, float("nan"), [f"error: {exc}"])
            )
    # Strongest conviction first (by absolute score).
    results.sort(key=lambda r: abs(r.score), reverse=True)
    return results


def to_dataframe(results: list[SignalResult]) -> pd.DataFrame:
    rows = []
    for r in results:
        rows.append(
            {
                "Symbol": r.symbol,
                "Signal": r.signal,
                "Score": r.score,
                "Price": round(r.price, 2) if r.price == r.price else None,
                "RSI": r.metrics.get("rsi"),
                "VWAP": r.metrics.get("vwap"),
                "RVOL": r.metrics.get("rvol"),
                "ATR": r.metrics.get("atr"),
            }
        )
    return pd.DataFrame(rows)
