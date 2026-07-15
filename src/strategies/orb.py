"""Opening Range Breakout (ORB) strategy.

The most widely-documented intraday strategy. Logic:
  1. Define the "opening range" = high & low of the first N minutes after
     the open (default 15 min).
  2. Go LONG when price breaks above the opening-range high.
     Go SHORT/exit-long when price breaks below the opening-range low.
  3. Confirm with VWAP (only long above VWAP, only short below) and relative
     volume, to filter false breakouts.

Score:
  +70 base on a confirmed bullish breakout, -70 on bearish, plus up to +30
  for strong relative volume, scaled by how decisively price cleared the
  range. Neutral (0) before the opening range completes or inside the range.

Causal: each bar's opening range uses only that day's already-formed bars.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import indicators as ind
from .base import Strategy

OPENING_RANGE_MINUTES = 15
_BASE = 70.0
_VOL_BONUS = 30.0


def _infer_minutes(bars: pd.DataFrame) -> int:
    if len(bars) < 3:
        return 5
    gap = bars.index.to_series().diff().median()
    return max(1, int(gap.total_seconds() // 60)) if pd.notna(gap) else 5


class ORBStrategy(Strategy):
    key = "orb"
    name = "Opening Range Breakout"
    description = (
        "Trades breakouts of the first 15-minute high/low, confirmed by VWAP "
        "and relative volume. The classic, well-researched intraday setup."
    )

    def _compute(self, bars: pd.DataFrame):
        """Return (score array, or_high series, or_low series, vwap, rvol)."""
        df = ind.enrich(bars)
        minutes = _infer_minutes(bars)
        bars_in_range = max(1, OPENING_RANGE_MINUTES // minutes)

        vwap = df["vwap"].to_numpy()
        close = df["close"].to_numpy()
        high = df["high"].to_numpy()
        low = df["low"].to_numpy()
        rvol = ind.relative_volume_series(df).to_numpy()

        day = df.index.normalize()
        score = np.zeros(len(df))
        or_high_arr = np.full(len(df), np.nan)
        or_low_arr = np.full(len(df), np.nan)

        # Process each day independently.
        for _, day_idx in pd.Series(range(len(df)), index=day).groupby(level=0):
            positions = day_idx.to_numpy()
            if len(positions) <= bars_in_range:
                continue
            or_slice = positions[:bars_in_range]
            or_high = high[or_slice].max()
            or_low = low[or_slice].min()
            rng = max(or_high - or_low, 1e-9)

            for p in positions[bars_in_range:]:
                or_high_arr[p] = or_high
                or_low_arr[p] = or_low
                c = close[p]
                if c > or_high and c > vwap[p]:
                    # How decisively above the range (capped).
                    strength = min((c - or_high) / rng, 1.0)
                    sc = _BASE + strength * 15
                    if rvol[p] >= 1.5:
                        sc += _VOL_BONUS * min(rvol[p] - 1.0, 1.0)
                    score[p] = min(sc, 100.0)
                elif c < or_low and c < vwap[p]:
                    strength = min((or_low - c) / rng, 1.0)
                    sc = _BASE + strength * 15
                    if rvol[p] >= 1.5:
                        sc += _VOL_BONUS * min(rvol[p] - 1.0, 1.0)
                    score[p] = -min(sc, 100.0)
                # else: inside range -> 0 (no signal)

        return score, or_high_arr, or_low_arr, vwap, rvol, df

    def score_series(self, bars: pd.DataFrame) -> pd.Series:
        score, *_ = self._compute(bars)
        return pd.Series(score, index=bars.index)

    def explain(self, bars: pd.DataFrame) -> tuple[list[str], dict]:
        score, or_high, or_low, vwap, rvol, df = self._compute(bars)
        i = -1
        last = df.iloc[i]
        c = float(last["close"])
        oh = or_high[i]
        ol = or_low[i]

        reasons = []
        if np.isnan(oh):
            reasons.append("Opening range not yet formed (no signal)")
        else:
            reasons.append(f"Opening range: {ol:.2f} – {oh:.2f}")
            if c > oh:
                reasons.append("Price broke ABOVE opening-range high (bullish)")
            elif c < ol:
                reasons.append("Price broke BELOW opening-range low (bearish)")
            else:
                reasons.append("Price inside opening range (waiting)")
            reasons.append(
                "Above VWAP (long confirmed)" if c > float(last["vwap"])
                else "Below VWAP (short confirmed)"
            )
            reasons.append(
                f"High relative volume ({rvol[i]:.2f}x)" if rvol[i] >= 1.5
                else f"Normal volume ({rvol[i]:.2f}x)"
            )

        metrics = {
            "or_high": None if np.isnan(oh) else round(float(oh), 2),
            "or_low": None if np.isnan(ol) else round(float(ol), 2),
            "vwap": round(float(last["vwap"]), 2),
            "rsi": round(float(last["rsi"]), 1),
            "atr": round(float(last["atr"]), 2),
            "rvol": round(float(rvol[i]), 2),
        }
        return reasons, metrics
