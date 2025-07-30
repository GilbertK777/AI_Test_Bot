"""
Streamlit을 사용한 실시간 트레이딩 대시보드.

이 모듈은 `main.py`에서 실행되며, 봇의 현재 상태, 데이터, 거래 내역 등을
시각적으로 보여주는 웹 기반 대시보드를 생성합니다.

주요 기능:
- **자동 새로고침**: `streamlit_autorefresh`를 사용하여 주기적으로 페이지를 새로고침하여
  최신 정보를 표시합니다.
- **사이드바 정보**: 현재 트레이딩 모드(Paper/Live), 잔고, 레버리지, 모델 학습 시간,
  현재 포지션 상태 등 핵심 정보를 한눈에 볼 수 있도록 사이드바에 표시합니다.
- **데이터 시각화**: `plotly` 라이브러리를 사용하여 다음과 같은 차트를 생성합니다.
  - 15분봉 캔들스틱 차트 (EMA 포함)
  - RSI 및 MACD 지표 차트
  - 누적 잔고 변화를 보여주는 잔고 곡선(Balance Curve)
- **테이블 표시**: `pandas` 데이터프레임을 사용하여 다음 정보를 테이블 형태로 보여줍니다.
  - 최근 5개의 매매 신호 데이터
  - 최근 20개의 거래 내역
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from streamlit_autorefresh import st_autorefresh
from config.config import CFG

def run_dashboard(bot):
    """
    Streamlit 대시보드를 생성하고 실행하는 메인 함수.

    이 함수는 `TradingBot` 인스턴스를 인자로 받아, 봇의 내부 상태(`bot.order`, `bot.model`, `bot.get_df()`)를
    주기적으로 읽어와 UI 컴포넌트를 렌더링합니다.

    Args:
        bot (TradingBot): 실행 중인 트레이딩 봇의 인스턴스.
    """
    # 60초(60,000ms)마다 페이지를 자동으로 새로고침하도록 설정합니다.
    st_autorefresh(interval=60_000, key="dashboard_refresh")

    # 페이지의 기본 설정을 구성합니다. 제목과 넓은 레이아웃(wide)을 사용합니다.
    st.set_page_config(page_title="MTF-XGB Futures Bot", layout="wide")
    st.title("🚀 Multi-TF + XGB Futures Trading Bot Dashboard")

    # --- 사이드바 (Sidebar) ---
    # 사이드바는 화면 왼쪽에 고정된 영역으로, 핵심 요약 정보를 표시하는 데 사용됩니다.

    # 현재 잔고를 가져옵니다.
    bal = bot.order.balance
    # 헤더에 모드, 잔고, 레버리지를 표시합니다.
    st.sidebar.header(f"{'PAPER' if bot.order.paper else 'LIVE'} | Balance: ${bal:,.0f} | Leverage: {CFG.LEVERAGE}×")
    # 마지막 모델 학습 시간을 표시합니다.
    st.sidebar.info(f"Model Last Trained: {bot.model.t_last_train:%H:%M UTC, %m-%d}")

    # 현재 포지션 상태를 표시합니다.
    if bot.order.pos:
        pos_info = bot.order.pos
        st.sidebar.success(f"POSITION: {pos_info['side'].upper()} @ {pos_info['entry']:.1f}")
    else:
        st.sidebar.warning("No open position.")

    # --- 메인 컨텐츠 ---

    # 봇으로부터 최신 데이터프레임을 스레드 안전하게 가져옵니다.
    df = bot.get_df()

    # 데이터프레임이 유효한 경우에만 차트와 테이블을 그립니다.
    if df is not None and not df.empty:
        # 1. 15분봉 캔들스틱 차트
        st.subheader("15-minute Candlestick Chart")
        fig = go.Figure(data=[
            go.Candlestick(x=df.index, open=df["open"], high=df["high"], low=df["low"], close=df["close"], name="Candles"),
            go.Scatter(x=df.index, y=df["ema_fast"], name="EMA Fast", line=dict(color="blue", width=1)),
            go.Scatter(x=df.index, y=df["ema_slow"], name="EMA Slow", line=dict(color="red", width=1))
        ])
        fig.update_layout(xaxis_rangeslider_visible=False) # 차트 아래의 작은 범위 슬라이더를 숨깁니다.
        st.plotly_chart(fig, use_container_width=True)

        # 2. RSI & MACD 지표 차트
        st.subheader("RSI & MACD Indicators")
        fig2 = go.Figure(data=[
            go.Scatter(x=df.index, y=df["rsi"], name="RSI", line=dict(color="purple")),
            go.Scatter(x=df.index, y=df["macd"], name="MACD", line=dict(color="green")),
            go.Scatter(x=df.index, y=df["macd_sig"], name="MACD Signal", line=dict(color="orange")),
        ])
        fig2.update_layout(xaxis_rangeslider_visible=False)
        st.plotly_chart(fig2, use_container_width=True)

        # 3. 최근 신호 데이터 테이블
        st.subheader("Latest Signals (tail 5)")
        # 표시할 컬럼만 선택하여 마지막 5개 행을 데이터프레임으로 보여줍니다.
        st.dataframe(df[["close", "prob_up", "long", "short", "exit_l", "exit_s"]].tail(5))

    # 거래 내역이 있는 경우에만 관련 정보를 표시합니다.
    if bot.order.trades:
        # 4. 거래 내역 테이블
        hist = pd.DataFrame(bot.order.trades)
        st.subheader("Trade History")
        # 최근 20개의 거래 내역을 보여줍니다.
        st.dataframe(hist.tail(20))

        # 5. 잔고 곡선 차트
        st.subheader("Balance Curve")
        fig3 = go.Figure(data=[
            go.Scatter(x=hist["time"], y=hist["bal"], mode="lines+markers", name="Balance")
        ])
        st.plotly_chart(fig3, use_container_width=True)
