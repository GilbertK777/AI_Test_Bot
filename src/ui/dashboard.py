"""
Streamlit 실시간 대시보드
"""
import streamlit as st, plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh
from config.config import CFG

def run_dashboard(bot):
    st_autorefresh(interval=60_000, key="refresh")
    st.set_page_config(page_title="MTF‑XGB Futures Bot", layout="wide")
    st.title("🚀 Multi‑TF + XGB  Futures Trading Bot")

    bal = bot.order.balance
    st.sidebar.header(f"{'PAPER' if bot.order.paper else 'LIVE'} | Bal ${bal:,.0f} | {CFG.LEVERAGE}×")
    st.sidebar.info(f"Model @ {bot.model.t_last_train:%H:%M UTC, %m-%d}")

    if bot.order.pos:
        st.sidebar.success(f"OPEN {bot.order.pos['side'].upper()} @ {bot.order.pos['entry']:.1f}")
    else:
        st.sidebar.warning("No open position")

    df = bot.get_df()
    if df is not None and not df.empty:
        st.subheader("15m Candles")
        fig = go.Figure([
            go.Candlestick(x=df.index, open=df["open"], high=df["high"],
                           low=df["low"], close=df["close"]),
            go.Scatter(x=df.index, y=df["ema_fast"], name="EMA12", line=dict(color="blue")),
            go.Scatter(x=df.index, y=df["ema_slow"], name="EMA26", line=dict(color="red"))
        ])
        st.plotly_chart(fig, use_container_width=True)
        st.subheader("RSI & MACD")
        fig2 = go.Figure([
            go.Scatter(x=df.index, y=df["rsi"], name="RSI", line=dict(color="purple")),
            go.Scatter(x=df.index, y=df["macd"], name="MACD", line=dict(color="green")),
            go.Scatter(x=df.index, y=df["macd_sig"], name="Signal", line=dict(color="orange")),
        ])
        st.plotly_chart(fig2, use_container_width=True)
        st.subheader("Signals (tail 5)")
        st.dataframe(df[["close","prob_up","long","short","exit_l","exit_s"]].tail(5))

    if bot.order.trades:
        import pandas as pd
        hist = pd.DataFrame(bot.order.trades)
        st.subheader("Trades")
        st.dataframe(hist.tail(20))
        st.subheader("Balance Curve")
        fig3 = go.Figure([go.Scatter(x=hist["time"], y=hist["bal"],
                                     mode="lines+markers")])
        st.plotly_chart(fig3, use_container_width=True)
