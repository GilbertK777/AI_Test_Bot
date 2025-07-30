"""
전역 설정 + .env 로드 (C# static class 개념).
다른 모듈에서 `from config.config import CFG` 로 불러 사용.
"""
import os, sys
from pathlib import Path
from dotenv import load_dotenv

# ── .env 로드 ──────────────────────────────────────────────────────────
load_dotenv()  # ~/.env

# 필수 키 확인
REQUIRED_ENV = ["BINANCE_API_KEY", "BINANCE_API_SECRET",
                "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
_missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
if _missing:
    sys.exit(f"[FATAL] .env에 다음 변수가 없습니다 →  {_missing}")


class CFG:
    """전역(Static) 설정 컨테이너"""
    # ── API & 계정 ──
    API_KEY      = os.getenv("BINANCE_API_KEY")
    API_SECRET   = os.getenv("BINANCE_API_SECRET")
    TG_TOKEN     = os.getenv("TELEGRAM_BOT_TOKEN")
    TG_CHAT      = os.getenv("TELEGRAM_CHAT_ID")
    EXCHANGE_NAME= os.getenv("EXCHANGE", "BINANCE").upper()

    # ── 심볼 & 레버리지 ──
    SYMBOL   = os.getenv("SYMBOL", "BTC/USDT")
    LEVERAGE = int(os.getenv("LEVERAGE", 3))
    ISOLATED = True  # 격리마진

    # ── 포지션 크기 / 증거금 ──
    POS_SIZE          = float(os.getenv("POSITION_SIZE", 0.001))
    MARGIN_PER_TRADE  = float(os.getenv("POSITION_MARGIN", 0))
    TEST_MODE         = os.getenv("TEST_MODE", "true").lower() == "true"
    INIT_BAL          = float(os.getenv("INIT_BALANCE", 10_000))

    # ── 전략 파라미터 ──
    BUY_TH   = float(os.getenv("PROB_BUY_TH",   0.65))
    SELL_TH  = float(os.getenv("PROB_SELL_TH",  0.40))
    SHORT_TH = float(os.getenv("PROB_SHORT_TH", 0.35))
    SL_PCT   = float(os.getenv("STOP_LOSS_PCT", 0.02))
    TP_PCT   = float(os.getenv("TP_PCT",        0.05))
    SLIP_PCT = float(os.getenv("SLIPPAGE_PCT",  0.0005))

    # ── 주기 & 로깅 ──
    SLEEP_SEC  = int(os.getenv("SLEEP_SEC", 60))
    RETRAIN_HR = int(os.getenv("TRAIN_HR", 24))
    GRID_DAYS  = int(os.getenv("GRIDSEARCH_INTERVAL_DAYS", 7))

    # ── 리스크 관리 ──
    MAX_QTY  = float(os.getenv("MAX_POSITION_LIMIT", 0.02))
    MAX_LOSS = int(os.getenv("MAX_CONSECUTIVE_LOSSES", 3))
    PAUSE_HR = int(os.getenv("PAUSE_HR", 1))

    # ── 경로 ──
    DATA_DIR  = Path(os.getenv("DATA_DIR",  "data"))
    MODEL_DIR = Path(os.getenv("MODEL_DIR", "models"))
    MODEL_FP  = MODEL_DIR / f"xgb_{SYMBOL.replace('/', '_')}_fut.joblib"

    @staticmethod
    def validate() -> None:
        """설정값 유효성 검증 + 디렉터리 생성"""
        if CFG.POS_SIZE <= 0 and CFG.MARGIN_PER_TRADE <= 0:
            raise ValueError("POSITION_SIZE 또는 POSITION_MARGIN 중 하나는 설정되어야 합니다.")
        if CFG.LEVERAGE < 1:
            raise ValueError("LEVERAGE >= 1 이어야 합니다.")
        CFG.DATA_DIR.mkdir(exist_ok=True)
        CFG.MODEL_DIR.mkdir(exist_ok=True)


# 최초 로드 시 1회 검증
CFG.validate()
