"""Confluence strategy — the upgraded multi-indicator engine.

Combines trend (EMA), mean-reversion (RSI), momentum (MACD), an intraday
anchor (VWAP), and conviction (relative volume) into a weighted score.

Upgrades over the original version:
  1. Higher-timeframe (HTF) trend filter — resamples the same bars to a
     coarser timeframe and dampens signals that fight the larger trend.
     ("Trade with the higher-timeframe trend.")
  2. ATR volatility gate — when the stock is barely moving (very low ATR%),
     scores are dampened, because intraday setups need range to work.
  3. Whipsaw reduction — the raw score is lightly smoothed so a single noisy
     bar doesn't flip the signal.

Everything remains causal and vectorised (O(n)).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import indicators as ind
from .base import Strategy

WEIGHTS = {
    "vwap": 25,
    "ema_cross": 20,
    "rsi": 15,
    "macd": 20,
    "rvol": 20,
}

# HTF trend filter: how much to scale a score that fights the larger trend.
_HTF_DAMPEN = 0.6
# ATR gate: below this ATR% of price, dampen (too quiet to trade).
_MIN_ATR_PCT = 0.15
_ATR_DAMPEN = 0.7
# Smoothing window (bars) for whipsaw reduction.
_SMOOTH = 3


def _htf_trend(bars: pd.DataFrame, factor: int = 6) -> pd.Series:
    """+1 uptrend / -1 downtrend / 0 flat on a coarser timeframe.

    Resamples to `factor` x the base interval, takes an EMA(9/20) cross, then
    forward-fills back onto the base index. Causal: uses only closed HTF bars.
    """
    # Infer base frequency in minutes from the median gap.
    if len(bars) < 3:
        return pd.Series(0, index=bars.index)
    gap = bars.index.to_series().diff().median()
    minutes = max(1, int(gap.total_seconds() // 60)) if pd.notna(gap) else 5
    htf_rule = f"{minutes * factor}min"

    htf = bars["close"].resample(htf_rule).last().dropna()
    if len(htf) < 20:
        return pd.Series(0, index=bars.index)
    ema_f = htf.ewm(span=9, adjust=False).mean()
    ema_s = htf.ewm(span=20, adjust=False).mean()
    trend = np.sign(ema_f - ema_s)
    # Shift by 1 HTF bar so we only use completed HTF candles (no look-ahead).
    trend = trend.shift(1).fillna(0)
    return trend.reindex(bars.index, method="ffill").fillna(0)


class ConfluenceStrategy(Strategy):
    key = "confluence"
    name = "Confluence (multi-indicator)"
    description = (
        "Weighted blend of VWAP, EMA9/20 trend, RSI, MACD and relative "
        "volume, filtered by higher-timeframe trend and volatility."
    )

    def score_series(self, bars: pd.DataFrame) -> pd.Series:
        df = ind.enrich(bars)
        rvol = ind.relative_volume_series(df).to_numpy()

        close = df["close"].to_numpy()
        vwap = df["vwap"].to_numpy()
        ema9 = df["ema9"].to_numpy()
        ema20 = df["ema20"].to_numpy()
        rsi = df["rsi"].to_numpy()
        hist = df["macd_hist"].to_numpy()
        macd_l = df["macd"].to_numpy()
        macd_s = df["macd_signal"].to_numpy()
        atr = df["atr"].to_numpy()

        vwap_vote = np.where(close > vwap, WEIGHTS["vwap"], -WEIGHTS["vwap"])
        ema_vote = np.where(ema9 > ema20, WEIGHTS["ema_cross"], -WEIGHTS["ema_cross"])
        rsi_vote = np.where(
            rsi < 30,
            WEIGHTS["rsi"],
            np.where(rsi > 70, -WEIGHTS["rsi"], WEIGHTS["rsi"] * ((rsi - 50) / 50) * 0.5),
        )
        macd_vote = np.where(
            (hist > 0) & (macd_l > macd_s),
            WEIGHTS["macd"],
            np.where((hist < 0) & (macd_l < macd_s), -WEIGHTS["macd"], 0.0),
        )
        base = vwap_vote + ema_vote + rsi_vote + macd_vote

        boost = np.where(rvol >= 1.5, WEIGHTS["rvol"] * np.clip(rvol - 1.0, 0.0, 1.0), 0.0)
        rvol_vote = np.where(base >= 0, boost, -boost)
        score = base + rvol_vote

        # --- Upgrade 1: higher-timeframe trend filter --------------------
        htf = _htf_trend(bars).to_numpy()
        # Dampen scores that oppose the HTF trend.
        against = ((score > 0) & (htf < 0)) | ((score < 0) & (htf > 0))
        score = np.where(against, score * _HTF_DAMPEN, score)

        # --- Upgrade 2: ATR volatility gate ------------------------------
        atr_pct = np.divide(atr, close, out=np.zeros_like(atr), where=close != 0) * 100
        quiet = atr_pct < _MIN_ATR_PCT
        score = np.where(quiet, score * _ATR_DAMPEN, score)

        score = np.clip(score, -100.0, 100.0)
        score[:30] = 0.0

        s = pd.Series(score, index=df.index)
        # --- Upgrade 3: whipsaw smoothing --------------------------------
        s = s.rolling(_SMOOTH, min_periods=1).mean()
        return s

    def explain(self, bars: pd.DataFrame) -> tuple[list[str], dict]:
        df = ind.enrich(bars)
        last = df.iloc[-1]
        rvol = float(ind.relative_volume_series(df).iloc[-1])
        htf = float(_htf_trend(bars).iloc[-1])
        atr_pct = float(last["atr"]) / float(last["close"]) * 100 if last["close"] else 0

        reasons = []
        reasons.append(
            "Price above VWAP (bullish)" if last["close"] > last["vwap"]
            else "Price below VWAP (bearish)"
        )
        reasons.append(
            "EMA9 > EMA20 (uptrend)" if last["ema9"] > last["ema20"]
            else "EMA9 < EMA20 (downtrend)"
        )
        r = float(last["rsi"])
        reasons.append(
            f"RSI oversold ({r:.0f})" if r < 30
            else f"RSI overbought ({r:.0f})" if r > 70
            else f"RSI neutral ({r:.0f})"
        )
        if last["macd_hist"] > 0 and last["macd"] > last["macd_signal"]:
            reasons.append("MACD bullish")
        elif last["macd_hist"] < 0 and last["macd"] < last["macd_signal"]:
            reasons.append("MACD bearish")
        reasons.append(
            f"High relative volume ({rvol:.2f}x)" if rvol >= 1.5
            else f"Normal volume ({rvol:.2f}x)"
        )
        reasons.append(
            "HTF trend up" if htf > 0 else "HTF trend down" if htf < 0 else "HTF trend flat"
        )
        if atr_pct < _MIN_ATR_PCT:
            reasons.append(f"Low volatility (ATR {atr_pct:.2f}% — signals dampened)")

        pivots = ind.pivot_points(df)
        metrics = {
            "vwap": round(float(last["vwap"]), 2),
            "ema9": round(float(last["ema9"]), 2),
            "ema20": round(float(last["ema20"]), 2),
            "rsi": round(r, 1),
            "macd_hist": round(float(last["macd_hist"]), 3),
            "atr": round(float(last["atr"]), 2),
            "atr_pct": round(atr_pct, 2),
            "rvol": round(rvol, 2),
            "htf_trend": int(htf),
            **{k: round(v, 2) for k, v in pivots.items()},
        }
        return reasons, metrics
