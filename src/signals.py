"""Signal facade.

Thin layer over the strategy registry. The rest of the app calls
`generate()` and `score_series()` with an optional strategy key; the actual
scoring lives in `src/strategies/`. This keeps screener/backtest/API
strategy-agnostic.

Educational tool, NOT financial advice.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .strategies import DEFAULT, get_strategy

BUY_THRESHOLD = 35
SELL_THRESHOLD = -35
MIN_BARS = 30


@dataclass
class SignalResult:
    symbol: str
    signal: str  # "BUY" | "SELL" | "HOLD"
    score: float  # -100 .. +100 (negative = bearish)
    price: float
    reasons: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    strategy: str = DEFAULT


def _label(score: float) -> str:
    if score >= BUY_THRESHOLD:
        return "BUY"
    if score <= SELL_THRESHOLD:
        return "SELL"
    return "HOLD"


def score_series(bars: pd.DataFrame, strategy: str | None = None) -> pd.Series:
    """Causal per-bar score for the chosen strategy."""
    return get_strategy(strategy).score_series(bars)


def generate(
    symbol: str, bars: pd.DataFrame, strategy: str | None = None
) -> SignalResult:
    """Produce a signal for one symbol using the chosen strategy."""
    strat = get_strategy(strategy)
    if bars is None or len(bars) < MIN_BARS:
        return SignalResult(
            symbol, "HOLD", 0.0, float("nan"), ["insufficient data"], {}, strat.key
        )

    scores = strat.score_series(bars)
    score = float(scores.iloc[-1])
    reasons, metrics = strat.explain(bars)
    price = float(bars["close"].iloc[-1])

    return SignalResult(
        symbol=symbol,
        signal=_label(score),
        score=round(score, 1),
        price=price,
        reasons=reasons,
        metrics=metrics,
        strategy=strat.key,
    )
