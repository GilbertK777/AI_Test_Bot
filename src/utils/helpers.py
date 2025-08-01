"""
공통 헬퍼(Helper) 모듈.

이 모듈은 애플리케이션의 여러 부분에서 공통적으로 사용되는 유틸리티 함수들을 모아놓은 곳입니다.
- 로깅(Logging) 설정: 파일 및 콘솔에 로그를 남기도록 표준 로깅 모듈을 설정합니다.
- 텔레그램(Telegram) 알림: 간단한 함수 호출로 텔레그램 메시지를 보냅니다.
- 기술적 지표(Technical Indicators) 계산: `pandas-ta` 라이브러리를 사용하여 OHLCV 데이터에 다양한 기술적 지표를 추가합니다.

다른 모듈에서는 `from src.utils.helpers import tg, add_indicators`와 같이 필요한 함수를 직접 임포트하여 사용합니다.
로깅 설정은 이 모듈이 임포트되는 시점에 자동으로 적용됩니다.
"""
import logging
import sys
from logging import StreamHandler
from logging.handlers import RotatingFileHandler
import pandas as pd
import ta
from telegram.ext import Updater
from config.config import CFG

# --- 로깅(Logging) 설정 ---
# 애플리케이션 전역에서 사용할 로거(Logger)를 설정합니다.
# 이 코드는 모듈이 처음 임포트될 때 한 번만 실행되며, 이후 모든 `logging` 호출에 적용됩니다.

# 로그 메시지 형식 지정: "시간 [로그레벨] 메시지" 형태로 출력됩니다.
# 예: "2023-10-27 10:30:00,123 [INFO] 봇 시작"
log_fmt = "%(asctime)s [%(levelname)s] %(message)s"

# `logging.basicConfig`를 사용하여 루트 로거의 기본 설정을 구성합니다.
logging.basicConfig(
    level=logging.INFO,  # INFO 레벨 이상의 로그만 처리합니다 (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    format=log_fmt,      # 위에서 정의한 로그 메시지 형식을 사용합니다.
    handlers=[
        # RotatingFileHandler: 로그 파일을 관리합니다.
        # 파일 크기가 `maxBytes`에 도달하면 새 파일에 로깅을 시작하고,
        # 오래된 로그 파일은 `backupCount` 개수만큼 유지합니다 (예: bot.log, bot.log.1, bot.log.2).
        RotatingFileHandler("bot_futures.log", maxBytes=5_000_000, backupCount=3), # 5MB
        # StreamHandler: 로그 메시지를 콘솔(stdout)에도 함께 출력합니다.
        StreamHandler(sys.stdout)
    ]
)


# --- 텔레그램(Telegram) 헬퍼 ---
def tg(msg: str) -> None:
    """
    텔레그램 메시지를 전송하는 헬퍼 함수.

    `config.py`에 설정된 `TG_TOKEN`과 `TG_CHAT` 정보를 사용하여 지정된 텔레그램 채팅으로 메시지를 보냅니다.
    네트워크 오류 등 예외가 발생하더라도 프로그램이 중단되지 않도록 처리하고, 대신 에러 로그를 남깁니다.
    현재 코드에서는 실제 전송 라인이 주석 처리되어 있어, 실제 메시지 발송 대신 INFO 레벨의 로그를 남깁니다.
    실제 사용 시에는 주석을 해제해야 합니다.

    Args:
        msg (str): 전송할 메시지 내용.
    """
    try:
        # 아래 라인의 주석을 해제하면 실제 텔레그램 메시지가 발송됩니다.
        # Updater(CFG.TG_TOKEN).bot.send_message(chat_id=CFG.TG_CHAT, text=msg)

        # 현재는 비활성화 상태이며, 로그로만 메시지 내용을 출력합니다.
        logging.info(f"Telegram (disabled) ▶ {msg}")
    except Exception as e:
        # 텔레그램 메시지 전송 중 오류 발생 시, 에러 로그를 기록합니다.
        logging.error(f"Telegram 오류: {e}")


# --- 기술적 지표 계산 ---
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    주어진 OHLCV 데이터프레임에 다양한 기술적 지표를 계산하여 추가합니다.

    `ta` 라이브러리(https://github.com/bukosabino/ta)를 사용하여 다음 지표들을 계산합니다:
    - EMA (Exponential Moving Average): 지수이동평균. 최근 가격에 더 큰 가중치를 둡니다.
    - RSI (Relative Strength Index): 상대강도지수. 과매수/과매도 상태를 판단하는 데 사용됩니다.
    - ATR (Average True Range): 평균 실제 범위. 가격 변동성을 측정하는 지표입니다.
    - MACD (Moving Average Convergence Divergence): 이동평균 수렴/발산. 추세의 강도와 방향을 나타냅니다.
    - Bollinger Bands: 볼린저 밴드. 이동평균선을 중심으로 표준편차 밴드를 표시하여 변동성을 시각화합니다.

    Args:
        df (pd.DataFrame): 'open', 'high', 'low', 'close', 'volume' 컬럼을 포함하는 OHLCV 데이터프레임.

    Returns:
        pd.DataFrame: 원본 데이터프레임에 기술적 지표 컬럼들이 추가된 새로운 데이터프레임.
                      지표 계산으로 인해 초기에 NaN 값을 갖는 행들은 제거됩니다.
    """
    # 원본 데이터프레임을 수정하지 않기 위해 복사본을 만들어 사용합니다.
    df = df.copy()

    # EMA (지수이동평균) - 단기(12), 장기(26)
    # 추세 추종 지표로, 단기 EMA가 장기 EMA 위에 있으면 상승 추세로 해석합니다.
    df["ema_fast"] = ta.trend.EMAIndicator(df["close"], window=12).ema_indicator()
    df["ema_slow"] = ta.trend.EMAIndicator(df["close"], window=26).ema_indicator()

    # RSI (상대강도지수) - 14기간
    # 모멘텀 지표로, 보통 70 이상이면 과매수, 30 이하이면 과매도 상태로 봅니다.
    df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()

    # ATR (평균 실제 범위) - 14기간
    # 변동성 지표로, ATR 값이 높을수록 가격 변동성이 크다는 의미입니다. 손절매 거리 계산 등에 활용될 수 있습니다.
    df["atr"] = ta.volatility.AverageTrueRange(df["high"], df["low"], df["close"], window=14).average_true_range()

    # MACD (이동평균 수렴/발산) - 표준 12, 26, 9 설정
    # MACD 선(12-26 EMA 차이)과 시그널 선(MACD의 9 EMA)의 교차를 통해 매매 신호를 포착합니다.
    macd = ta.trend.MACD(df["close"])
    df["macd"] = macd.macd()
    df["macd_sig"] = macd.macd_signal()

    # Bollinger Bands (볼린저 밴드) - 20기간, 표준편차 2
    # 가격이 상단 밴드에 닿으면 과매수, 하단 밴드에 닿으면 과매도 상태로 해석될 수 있습니다.
    bb = ta.volatility.BollingerBands(df["close"], window=20, window_dev=2)
    df["bb_low"] = bb.bollinger_lband()
    df["bb_high"] = bb.bollinger_hband()

    # 지표 계산 초기에 발생하는 NaN 값들을 포함한 행을 모두 제거하고 반환합니다.
    return df.dropna()
