"""Quick end-to-end sanity check on mock data (no Streamlit, no credentials)."""
from src import backtest as bt
from src import screener
from src.data import get_provider
from src.signals import generate

p = get_provider()
print(f"Provider: {p.name}")

# 1) Historical bars
df = p.get_historical("RELIANCE", interval="FIVE_MINUTE", days=5)
print(f"Bars: {len(df)} rows, cols={list(df.columns)}")
assert not df.empty
assert list(df.columns) == ["open", "high", "low", "close", "volume"]

# 2) Single signal
res = generate("RELIANCE", df)
print(f"Signal: {res.symbol} -> {res.signal} (score {res.score}) @ {res.price:.2f}")
assert res.signal in {"BUY", "SELL", "HOLD"}
assert res.metrics

# 3) Screener across watchlist
results = screener.scan(p, ["RELIANCE", "TCS", "INFY", "SBIN"], "FIVE_MINUTE", 5)
sdf = screener.to_dataframe(results)
print("\nScreener:")
print(sdf.to_string(index=False))
assert len(results) == 4

# 4) Backtest
r = bt.run("RELIANCE", df)
print(
    f"\nBacktest RELIANCE: return={r.total_return_pct}% "
    f"win_rate={r.win_rate}% trades={r.num_trades}"
)
assert r.num_trades >= 0

print("\nAll smoke tests passed.")
