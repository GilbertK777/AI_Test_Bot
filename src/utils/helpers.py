"""
공통 헬퍼: 로깅·텔레그램·기술적 지표 계산
다른 모듈에서 import 하여 사용.
"""
import logging, sys
from logging.handlers import RotatingFileHandler, StreamHandler
import pandas as pd
import ta
from telegram.ext import Updater
from config.config import CFG

# ── 로깅 셋업 ──────────────────────────────────────────────────────────
log_fmt = "%(asctime)s [%(levelname)s] %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=log_fmt,
    handlers=[
        RotatingFileHandler("bot_futures.log", maxBytes=5_000_000, backupCount=3),
        StreamHandler(sys.stdout)
    ]
)

# ── Telegram 헬퍼 ─────────────────────────────────────────────────────
def tg(msg: str) -> None:
    """텔레그램 메시지 전송 (예외 발생 시 로그만)"""
    try:
        # Updater(CFG.TG_TOKEN).bot.send_message(chat_id=CFG.TG_CHAT, text=msg)
        logging.info(f"Telegram (disabled) ▶ {msg}")
    except Exception as e:
        logging.error(f"Telegram 오류: {e}")

# ── 기술적 지표 계산 ──────────────────────────────────────────────────
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """EMA12/26, RSI14, ATR14, MACD, BollingerBand(20,2) 추가 후 반환"""
    df = df.copy()
    df["ema_fast"] = ta.trend.EMAIndicator(df["close"], 12).ema_indicator()
    df["ema_slow"] = ta.trend.EMAIndicator(df["close"], 26).ema_indicator()
    df["rsi"]      = ta.momentum.RSIIndicator(df["close"], 14).rsi()
    df["atr"]      = ta.volatility.AverageTrueRange(df["high"], df["low"],
                                                    df["close"], 14).average_true_range()
    macd = ta.trend.MACD(df["close"])
    df["macd"]     = macd.macd();    df["macd_sig"] = macd.macd_signal()
    bb  = ta.volatility.BollingerBands(df["close"], 20, 2)
    df["bb_low"]   = bb.bollinger_lband();  df["bb_high"] = bb.bollinger_hband()
    return df.dropna()
