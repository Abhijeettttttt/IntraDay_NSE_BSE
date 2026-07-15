"""Intraday Signals — Streamlit dashboard.

Run:  streamlit run app.py

Works out of the box on synthetic (mock) data. Set DATA_PROVIDER=angelone
with credentials in .env to use live Angel One SmartAPI data.

DISCLAIMER: Educational tool only. Not investment advice. Signals are
rule-based and may be wrong. Trade at your own risk.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from config import settings
from src import backtest as bt
from src import indicators as ind
from src import screener
from src.data import get_provider
from src.signals import generate

st.set_page_config(page_title="Intraday Signals", page_icon="📈", layout="wide")

INTERVALS = [
    "ONE_MINUTE",
    "THREE_MINUTE",
    "FIVE_MINUTE",
    "TEN_MINUTE",
    "FIFTEEN_MINUTE",
    "THIRTY_MINUTE",
    "ONE_HOUR",
]

_SIGNAL_COLOR = {"BUY": "#16a34a", "SELL": "#dc2626", "HOLD": "#6b7280"}


@st.cache_resource
def _provider():
    return get_provider()


@st.cache_data(ttl=60)
def _load_bars(symbol: str, interval: str, days: int) -> pd.DataFrame:
    return _provider().get_historical(symbol, interval=interval, days=days)


def _sidebar():
    st.sidebar.title("📈 Intraday Signals")
    active = settings.data_provider
    badge = "🟢 Angel One (live)" if active == "angelone" else "🟡 Mock data"
    st.sidebar.caption(f"Data source: **{badge}**")
    if active == "mock":
        st.sidebar.info(
            "Running on synthetic data. Add Angel One credentials to `.env` "
            "and set `DATA_PROVIDER=angelone` for live data.",
            icon="ℹ️",
        )

    interval = st.sidebar.selectbox("Interval", INTERVALS, index=2)
    days = st.sidebar.slider("History (trading days)", 2, 15, 5)

    wl_text = st.sidebar.text_area(
        "Watchlist (one symbol per line)",
        value="\n".join(settings.watchlist),
        height=180,
    )
    watchlist = [s.strip().upper() for s in wl_text.splitlines() if s.strip()]
    return interval, days, watchlist


def page_screener(interval: str, days: int, watchlist: list[str]):
    st.subheader("🔎 Screener")
    st.caption("Ranked by conviction (absolute signal score).")

    if st.button("Run scan", type="primary") or "scan_df" not in st.session_state:
        with st.spinner("Scanning watchlist..."):
            results = screener.scan(_provider(), watchlist, interval, days)
            st.session_state["scan_df"] = screener.to_dataframe(results)

    df = st.session_state.get("scan_df")
    if df is None or df.empty:
        st.info("No results yet.")
        return

    buys = int((df["Signal"] == "BUY").sum())
    sells = int((df["Signal"] == "SELL").sum())
    holds = int((df["Signal"] == "HOLD").sum())
    c1, c2, c3 = st.columns(3)
    c1.metric("BUY", buys)
    c2.metric("SELL", sells)
    c3.metric("HOLD", holds)

    def _color(val):
        return f"color: {_SIGNAL_COLOR.get(val, '#000')}; font-weight: 600"

    styled = df.style.map(_color, subset=["Signal"])
    st.dataframe(styled, use_container_width=True, hide_index=True)


def _price_chart(symbol: str, df: pd.DataFrame) -> go.Figure:
    e = ind.enrich(df)
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.55, 0.2, 0.25],
        vertical_spacing=0.03,
        subplot_titles=(f"{symbol} price", "Volume", "RSI"),
    )
    fig.add_trace(
        go.Candlestick(
            x=e.index,
            open=e["open"],
            high=e["high"],
            low=e["low"],
            close=e["close"],
            name="Price",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=e.index, y=e["vwap"], name="VWAP", line=dict(color="orange")),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=e.index, y=e["ema9"], name="EMA9", line=dict(color="#3b82f6")),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=e.index, y=e["ema20"], name="EMA20", line=dict(color="#a855f7")),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(x=e.index, y=e["volume"], name="Volume", marker_color="#94a3b8"),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=e.index, y=e["rsi"], name="RSI", line=dict(color="#0ea5e9")),
        row=3,
        col=1,
    )
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)
    fig.update_layout(
        height=700,
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def page_analyze(interval: str, days: int, watchlist: list[str]):
    st.subheader("📊 Analyze a stock")
    symbol = st.selectbox("Symbol", watchlist)
    if not symbol:
        return
    df = _load_bars(symbol, interval, days)
    if df.empty:
        st.warning("No data returned for this symbol.")
        return

    res = generate(symbol, df)
    color = _SIGNAL_COLOR.get(res.signal, "#000")
    c1, c2, c3 = st.columns([1, 1, 2])
    c1.markdown(
        f"### <span style='color:{color}'>{res.signal}</span>",
        unsafe_allow_html=True,
    )
    c2.metric("Score", f"{res.score:+.0f}")
    c3.metric("Last price", f"₹{res.price:,.2f}")

    with st.expander("Why this signal?", expanded=True):
        for r in res.reasons:
            st.write(f"• {r}")
        st.json(res.metrics)

    st.plotly_chart(_price_chart(symbol, df), use_container_width=True)


def page_backtest(interval: str, days: int, watchlist: list[str]):
    st.subheader("🧪 Backtest")
    st.caption(
        "Long-only intraday simulation with end-of-day square-off. "
        "Rough validation, not a promise of future results."
    )
    symbol = st.selectbox("Symbol", watchlist, key="bt_symbol")
    cost = st.slider("Round-trip cost (%)", 0.0, 0.5, 0.05, 0.01)

    if st.button("Run backtest", type="primary"):
        df = _load_bars(symbol, interval, days)
        if df.empty:
            st.warning("No data.")
            return
        with st.spinner("Backtesting..."):
            result = bt.run(symbol, df, cost_pct=cost)

        c1, c2, c3 = st.columns(3)
        c1.metric("Total return", f"{result.total_return_pct:+.2f}%")
        c2.metric("Win rate", f"{result.win_rate:.0f}%")
        c3.metric("Trades", result.num_trades)

        if not result.equity_curve.empty:
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=result.equity_curve.index,
                    y=(result.equity_curve - 1) * 100,
                    name="Equity (%)",
                    line=dict(color="#16a34a"),
                )
            )
            fig.update_layout(
                height=350,
                title="Equity curve (% return)",
                margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(fig, use_container_width=True)

        if result.trades:
            trades_df = pd.DataFrame(
                [
                    {
                        "Entry": t.entry_time,
                        "Exit": t.exit_time,
                        "Entry ₹": round(t.entry_price, 2),
                        "Exit ₹": round(t.exit_price, 2),
                        "PnL %": round(t.pnl_pct, 2),
                    }
                    for t in result.trades
                ]
            )
            st.dataframe(trades_df, use_container_width=True, hide_index=True)


def main():
    interval, days, watchlist = _sidebar()
    if not watchlist:
        st.warning("Add at least one symbol to the watchlist.")
        return

    tab1, tab2, tab3 = st.tabs(["🔎 Screener", "📊 Analyze", "🧪 Backtest"])
    with tab1:
        page_screener(interval, days, watchlist)
    with tab2:
        page_analyze(interval, days, watchlist)
    with tab3:
        page_backtest(interval, days, watchlist)

    st.divider()
    st.caption(
        "⚠️ Educational tool only. Not investment advice. Intraday trading is "
        "high-risk. Validate every signal independently and use stop-losses."
    )


if __name__ == "__main__":
    main()
