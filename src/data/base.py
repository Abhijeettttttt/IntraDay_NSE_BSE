"""Abstract data provider interface.

Any provider (mock, Angel One, or future ones) implements this contract.
The rest of the app depends only on this interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class DataProvider(ABC):
    """Contract for market-data sources.

    A historical bars DataFrame must have a DatetimeIndex and the columns:
    ["open", "high", "low", "close", "volume"].
    """

    name: str = "base"

    @abstractmethod
    def get_historical(
        self,
        symbol: str,
        interval: str = "FIVE_MINUTE",
        days: int = 5,
    ) -> pd.DataFrame:
        """Return intraday OHLCV bars for a symbol."""
        raise NotImplementedError

    @abstractmethod
    def get_ltp(self, symbol: str) -> float:
        """Return the last traded price for a symbol."""
        raise NotImplementedError

    def get_quote(self, symbol: str) -> dict:
        """Return a lightweight snapshot. Default derives from latest bar."""
        df = self.get_historical(symbol, days=1)
        last = df.iloc[-1]
        return {
            "symbol": symbol,
            "ltp": float(last["close"]),
            "open": float(last["open"]),
            "high": float(df["high"].max()),
            "low": float(df["low"].min()),
            "volume": int(df["volume"].sum()),
        }
