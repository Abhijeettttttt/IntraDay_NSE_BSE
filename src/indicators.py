"""Technical indicators used by the signal engine.

All functions take/return pandas objects and are vectorised. Input
DataFrames must have columns: open, high, low, close, volume.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(50)


def macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.DataFrame:
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return pd.DataFrame(
        {"macd": macd_line, "signal": signal_line, "hist": hist}
    )


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def vwap(df: pd.DataFrame) -> pd.Series:
    """Session VWAP. Resets each trading day."""
    typical = (df["high"] + df["low"] + df["close"]) / 3
    tpv = typical * df["volume"]
    day = df.index.normalize()
    cum_tpv = tpv.groupby(day).cumsum()
    cum_vol = df["volume"].groupby(day).cumsum().replace(0, np.nan)
    return (cum_tpv / cum_vol).ffill()


def relative_volume(df: pd.DataFrame, lookback_days: int = 5) -> float:
    """Today's cumulative volume vs. average of prior days at same time."""
    day = df.index.normalize()
    daily_vol = df["volume"].groupby(day).sum()
    if len(daily_vol) < 2:
        return 1.0
    today = daily_vol.iloc[-1]
    hist_avg = daily_vol.iloc[-(lookback_days + 1):-1].mean()
    if not hist_avg or np.isnan(hist_avg):
        return 1.0
    return float(today / hist_avg)


def relative_volume_series(df: pd.DataFrame, lookback_days: int = 5) -> pd.Series:
    """Causal, per-bar relative volume.

    For each bar: (cumulative volume so far *today*) / (average FULL daily
    volume of the previous `lookback_days` trading days). This matches, bar
    by bar, what relative_volume() returns when applied to the window up to
    that bar — but computed once in O(n) instead of O(n^2).

    First trading day (no prior history) defaults to 1.0.
    """
    day = df.index.normalize()
    cum_today = df["volume"].groupby(day).cumsum()
    full_daily = df["volume"].groupby(day).sum()

    ordered_days = list(full_daily.index)
    # Average of prior `lookback_days` full days, per day.
    hist_avg = {}
    for k, d in enumerate(ordered_days):
        if k == 0:
            hist_avg[d] = None
        else:
            start = max(0, k - lookback_days)
            prior = full_daily.iloc[start:k]
            hist_avg[d] = prior.mean() if len(prior) else None

    avg_for_bar = day.map(hist_avg)
    rvol = cum_today.to_numpy() / np.where(
        pd.isna(avg_for_bar) | (avg_for_bar == 0), np.nan, avg_for_bar
    )
    out = pd.Series(rvol, index=df.index).fillna(1.0)
    return out


def pivot_points(df: pd.DataFrame) -> dict:
    """Classic pivot points from the previous trading day."""
    day = df.index.normalize()
    daily = df.groupby(day).agg(
        high=("high", "max"), low=("low", "min"), close=("close", "last")
    )
    if len(daily) < 2:
        prev = daily.iloc[-1]
    else:
        prev = daily.iloc[-2]
    p = (prev["high"] + prev["low"] + prev["close"]) / 3
    r1 = 2 * p - prev["low"]
    s1 = 2 * p - prev["high"]
    r2 = p + (prev["high"] - prev["low"])
    s2 = p - (prev["high"] - prev["low"])
    return {
        "pivot": float(p),
        "r1": float(r1),
        "r2": float(r2),
        "s1": float(s1),
        "s2": float(s2),
    }


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Attach all indicator columns to a copy of the bars DataFrame."""
    out = df.copy()
    out["ema9"] = ema(out["close"], 9)
    out["ema20"] = ema(out["close"], 20)
    out["rsi"] = rsi(out["close"])
    m = macd(out["close"])
    out["macd"] = m["macd"]
    out["macd_signal"] = m["signal"]
    out["macd_hist"] = m["hist"]
    out["atr"] = atr(out)
    out["vwap"] = vwap(out)
    return out
