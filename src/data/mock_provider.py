"""Mock data provider.

Generates realistic-looking intraday OHLCV using a random walk with
intraday volatility patterns. Lets the whole app run and be tested
without any broker credentials. Deterministic per-symbol per-day so
results are stable within a session.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta

import numpy as np
import pandas as pd

from .base import DataProvider

# Interval label -> minutes per bar
_INTERVAL_MINUTES = {
    "ONE_MINUTE": 1,
    "THREE_MINUTE": 3,
    "FIVE_MINUTE": 5,
    "TEN_MINUTE": 10,
    "FIFTEEN_MINUTE": 15,
    "THIRTY_MINUTE": 30,
    "ONE_HOUR": 60,
}

# Rough starting prices so different symbols look distinct.
_BASE_PRICES = {
    "RELIANCE": 2900,
    "TCS": 3900,
    "HDFCBANK": 1650,
    "INFY": 1550,
    "ICICIBANK": 1150,
    "SBIN": 820,
    "TATAMOTORS": 980,
    "AXISBANK": 1120,
    "ITC": 440,
    "WIPRO": 540,
}


class MockDataProvider(DataProvider):
    name = "mock"

    def _seed_for(self, symbol: str, day: datetime) -> int:
        return abs(hash((symbol, day.strftime("%Y-%m-%d")))) % (2**32)

    def _base_price(self, symbol: str) -> float:
        if symbol in _BASE_PRICES:
            return float(_BASE_PRICES[symbol])
        # Deterministic pseudo price for unknown symbols.
        return 100.0 + (abs(hash(symbol)) % 3000)

    def _one_day(self, symbol: str, day: datetime, minutes: int) -> pd.DataFrame:
        rng = np.random.default_rng(self._seed_for(symbol, day))
        session_start = datetime.combine(day.date(), time(9, 15))
        session_end = datetime.combine(day.date(), time(15, 30))
        n_bars = int((session_end - session_start).total_seconds() // 60 // minutes)
        if n_bars <= 0:
            n_bars = 1

        base = self._base_price(symbol)
        # Daily drift + intraday volatility.
        drift = rng.normal(0, 0.004)
        vol = base * rng.uniform(0.0008, 0.0025)

        # Volatility is higher near open/close (U-shape).
        x = np.linspace(0, 1, n_bars)
        u_shape = 1.0 + 1.2 * (np.abs(x - 0.5) * 2) ** 2

        returns = rng.normal(drift / n_bars, vol, n_bars) * u_shape
        close = base * np.cumprod(1 + returns / base)

        # Build OHLC around the close path.
        open_ = np.empty(n_bars)
        open_[0] = base
        open_[1:] = close[:-1]
        spread = np.abs(rng.normal(0, vol, n_bars)) * u_shape
        high = np.maximum(open_, close) + spread
        low = np.minimum(open_, close) - spread

        # Volume: higher at open/close, random spikes.
        base_vol = rng.uniform(50_000, 250_000)
        volume = (base_vol * u_shape * rng.uniform(0.5, 1.5, n_bars)).astype(int)

        idx = pd.date_range(session_start, periods=n_bars, freq=f"{minutes}min")
        return pd.DataFrame(
            {
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            },
            index=idx,
        )

    def get_historical(
        self,
        symbol: str,
        interval: str = "FIVE_MINUTE",
        days: int = 5,
    ) -> pd.DataFrame:
        minutes = _INTERVAL_MINUTES.get(interval, 5)
        today = datetime.now()
        frames = []
        collected = 0
        offset = 0
        # Walk back skipping weekends until we have `days` trading days.
        while collected < days and offset < days + 10:
            day = today - timedelta(days=offset)
            offset += 1
            if day.weekday() >= 5:  # Sat/Sun
                continue
            frames.append(self._one_day(symbol, day, minutes))
            collected += 1
        df = pd.concat(sorted(frames, key=lambda f: f.index[0]))
        return df

    def get_ltp(self, symbol: str) -> float:
        df = self.get_historical(symbol, days=1)
        return float(df["close"].iloc[-1])
