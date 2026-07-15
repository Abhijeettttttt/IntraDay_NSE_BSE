"""Strategy interface.

A strategy turns OHLCV bars into a per-bar signal score in [-100, +100]
(negative = bearish, positive = bullish). The score is causal: the value
at bar i must depend only on data up to and including bar i.

Keeping strategies behind one interface lets the screener, analyzer, and
backtester stay strategy-agnostic — you just pass a strategy key.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Strategy(ABC):
    key: str = "base"
    name: str = "Base"
    description: str = ""

    @abstractmethod
    def score_series(self, bars: pd.DataFrame) -> pd.Series:
        """Causal per-bar score in [-100, +100]."""
        raise NotImplementedError

    @abstractmethod
    def explain(self, bars: pd.DataFrame) -> tuple[list[str], dict]:
        """Human-readable reasons + metrics dict for the LATEST bar."""
        raise NotImplementedError
