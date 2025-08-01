"""
전역 설정 + .env 로드 (C# static class 개념).
다른 모듈에서 `from config.config import CFG` 로 불러 사용.

이 모듈은 애플리케이션 전역에서 사용될 설정 값들을 관리하는 중앙 저장소 역할을 합니다.
`dotenv` 라이브러리를 사용하여 프로젝트 루트 디렉토리의 `.env` 파일로부터 환경 변수를 로드하고,
이를 `CFG` 클래스의 클래스 변수(정적 변수)로 할당합니다.

이를 통해 다음과 같은 이점을 얻을 수 있습니다:
- 설정의 중앙화: 모든 설정 값이 한 곳에 모여 있어 관리가 용이합니다.
- 보안: API 키와 같은 민감한 정보는 `.env` 파일에 저장하여 소스 코드로부터 분리하고,
  .gitignore에 .env를 추가하여 버전 관리 시스템에 포함되지 않도록 합니다.
- 유연성: 환경 변수를 통해 실행 환경(개발, 테스트, 운영)에 따라 다른 설정을 쉽게 적용할 수 있습니다.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# --- .env 파일 로드 ---
# `load_dotenv()` 함수는 현재 작업 디렉토리나 상위 디렉토리에서 `.env` 파일을 찾아
# 그 안에 정의된 키-값 쌍을 환경 변수로 로드합니다.
# 이 코드가 실행되는 시점부터 `os.getenv("KEY")`와 같은 방식으로 .env 파일의 값에 접근할 수 있습니다.
# 만약 .env 파일이 없다면, 환경 변수는 로드되지 않지만 오류가 발생하지는 않습니다.
load_dotenv()

# --- 필수 환경 변수 확인 ---
# 애플리케이션 실행에 반드시 필요한 공통 환경 변수 목록을 정의합니다.
_common_required = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]

# 선택된 거래소에 따라 필요한 API 키 변수를 동적으로 결정합니다.
_exchange_name = os.getenv("EXCHANGE", "BINANCE").upper()
_exchange_keys = []
if _exchange_name == "BINANCE":
    _exchange_keys = ["BINANCE_API_KEY", "BINANCE_API_SECRET"]
elif _exchange_name == "BYBIT":
    _exchange_keys = ["BYBIT_API_KEY", "BYBIT_API_SECRET"]

# 공통 변수와 거래소별 변수를 합쳐 최종 필수 환경 변수 목록을 만듭니다.
REQUIRED_ENV = _common_required + _exchange_keys

# 필수 변수가 설정되었는지 확인합니다.
_missing = [key for key in REQUIRED_ENV if not os.getenv(key)]
if _missing:
    # 누락된 변수가 있으면 프로그램을 종료합니다.
    sys.exit(f"[FATAL] .env 파일에 다음 필수 변수가 설정되지 않았습니다: {_missing}")


class CFG:
    """
    전역 설정 값들을 담는 정적(Static) 컨테이너 클래스.
    이 클래스의 모든 멤버는 클래스 변수이므로, 인스턴스를 생성할 필요 없이 `CFG.API_KEY`와 같이 직접 접근할 수 있습니다.
    `os.getenv(key, default)` 형태를 사용하여 환경 변수가 없을 경우 사용할 기본값을 지정합니다.
    """

    # --- API 및 계정 관련 설정 ---
    # 거래소별 API 키와 시크릿을 별도로 로드합니다.
    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
    BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
    BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
    BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")

    # 텔레그램 봇 토큰 및 채팅 ID
    TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TG_CHAT = os.getenv("TELEGRAM_CHAT_ID")

    # 사용할 거래소 이름. 'BYBIT' 또는 'BINANCE'를 지원합니다.
    EXCHANGE_NAME = _exchange_name

    # --- 심볼 및 레버리지 설정 ---
    # 거래할 암호화폐 페어(심볼). ccxt 라이브러리 형식(예: 'BTC/USDT')을 따릅니다.
    SYMBOL = os.getenv("SYMBOL", "BTC/USDT")
    # 선물 거래에 사용할 레버리지. 정수형으로 변환됩니다.
    LEVERAGE = int(os.getenv("LEVERAGE", 3))
    # 마진 모드 설정. True일 경우 '격리(ISOLATED)' 마진을 사용하고, False일 경우 '교차(CROSS)' 마진을 사용합니다.
    # 바이낸스와 바이빗 모두 격리 마진 설정을 지원합니다.
    ISOLATED = True

    # --- 포지션 크기 및 증거금 설정 ---
    # 1회 거래에 사용할 포지션 크기 (수량 기준). 예: 0.001 BTC.
    # `MARGIN_PER_TRADE`가 0보다 클 경우 이 값은 무시됩니다.
    POS_SIZE = float(os.getenv("POSITION_SIZE", 0.001))
    # 1회 거래에 사용할 증거금 (USDT 기준). 0보다 크면 이 값을 기준으로 포지션 크기를 계산합니다.
    # (계산식: `(증거금 * 레버리지) / 현재가`)
    MARGIN_PER_TRADE = float(os.getenv("POSITION_MARGIN", 0))
    # 테스트(페이퍼) 모드 활성화 여부. 'true'일 경우 실제 주문 없이 모의 거래를 실행합니다.
    TEST_MODE = os.getenv("TEST_MODE", "true").lower() == "true"
    # 페이퍼 트레이딩 시 사용할 초기 가상 잔고.
    INIT_BAL = float(os.getenv("INIT_BALANCE", 10_000))

    # --- 전략 파라미터 설정 ---
    # ML 모델의 예측 확률이 이 값보다 높고, 규칙 기반 조건이 맞으면 롱 포지션에 진입합니다.
    BUY_TH = float(os.getenv("PROB_BUY_TH", 0.65))
    # 롱 포지션 보유 중, ML 모델의 예측 확률이 이 값보다 낮아지면 청산 조건 중 하나가 됩니다.
    SELL_TH = float(os.getenv("PROB_SELL_TH", 0.40))
    # ML 모델의 예측 확률이 이 값보다 낮고, 규칙 기반 조건이 맞으면 숏 포지션에 진입합니다.
    SHORT_TH = float(os.getenv("PROB_SHORT_TH", 0.35))
    # 손절매(Stop-Loss) 비율. 진입 가격 대비 이 비율만큼 손실이 나면 포지션을 종료합니다. (예: 0.02 = 2%)
    SL_PCT = float(os.getenv("STOP_LOSS_PCT", 0.02))
    # 익절(Take-Profit) 비율. 진입 가격 대비 이 비율만큼 수익이 나면 포지션을 종료합니다. (예: 0.05 = 5%)
    TP_PCT = float(os.getenv("TP_PCT", 0.05))
    # 시장가 주문 시 발생할 수 있는 슬리피지(Slippage)를 고려한 비율.
    # 페이퍼 트레이딩에서 진입 가격을 계산할 때 사용됩니다. (예: 0.0005 = 0.05%)
    SLIP_PCT = float(os.getenv("SLIPPAGE_PCT", 0.0005))
    # 거래 수수료 비율. PnL 계산 시 이 비율만큼의 수수료를 차감합니다. (예: 0.0006 = 0.06%)
    TRADE_FEE = float(os.getenv("TRADE_FEE", 0.0006))

    # --- 주기 및 로깅 설정 ---
    # 메인 루프의 각 사이클이 끝난 후 대기할 시간 (초 단위).
    SLEEP_SEC = int(os.getenv("SLEEP_SEC", 60))
    # 모델을 재학습할 주기 (시간 단위). 이 시간이 지나면 모델을 다시 학습합니다.
    RETRAIN_HR = int(os.getenv("TRAIN_HR", 24))
    # 모델의 하이퍼파라미터를 GridSearchCV를 통해 다시 탐색할 주기 (일 단위).
    GRID_DAYS = int(os.getenv("GRIDSEARCH_INTERVAL_DAYS", 7))

    # --- 리스크 관리 설정 ---
    # 최대 허용 포지션 수량. 주문 시 이 수량을 초과하지 않도록 제한합니다.
    MAX_QTY = float(os.getenv("MAX_POSITION_LIMIT", 0.02))
    # 최대 연속 손실 횟수. 이 횟수만큼 연속으로 손실이 발생하면 트레이딩을 일시 중단합니다.
    MAX_LOSS = int(os.getenv("MAX_CONSECUTIVE_LOSSES", 3))
    # 연속 손실로 인해 트레이딩이 중단되었을 때, 휴식할 시간 (시간 단위).
    PAUSE_HR = int(os.getenv("PAUSE_HR", 1))

    # --- 경로 설정 ---
    # OHLCV 데이터 캐시(.parquet 파일)를 저장할 디렉토리 경로.
    DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
    # 학습된 ML 모델(.joblib 파일)을 저장할 디렉토리 경로.
    MODEL_DIR = Path(os.getenv("MODEL_DIR", "models"))
    # 거래 심볼에 따라 동적으로 생성되는 모델 파일의 전체 경로.
    MODEL_FP = MODEL_DIR / f"xgb_{SYMBOL.replace('/', '_')}_fut.joblib"

    @staticmethod
    def validate() -> None:
        """
        클래스에 로드된 설정 값들의 유효성을 검증하고, 필요한 디렉토리를 생성합니다.
        이 메서드는 모듈이 처음 임포트될 때 단 한 번 호출됩니다.
        """
        # 포지션 크기를 결정하는 두 가지 방법 중 하나는 반드시 설정되어야 합니다.
        if CFG.POS_SIZE <= 0 and CFG.MARGIN_PER_TRADE <= 0:
            raise ValueError("POSITION_SIZE 또는 POSITION_MARGIN 중 하나는 0보다 커야 합니다.")

        # 레버리지는 최소 1 이상이어야 합니다.
        if CFG.LEVERAGE < 1:
            raise ValueError("LEVERAGE는 1 이상이어야 합니다.")

        # 데이터와 모델을 저장할 디렉토리가 존재하지 않으면 생성합니다.
        # `exist_ok=True`는 디렉토리가 이미 존재하더라도 오류를 발생시키지 않습니다.
        CFG.DATA_DIR.mkdir(exist_ok=True)
        CFG.MODEL_DIR.mkdir(exist_ok=True)


# --- 최초 로드 시 유효성 검증 실행 ---
# 이 스크립트(모듈)가 파이썬 인터프리터에 의해 처음 로드될 때,
# `CFG.validate()`를 호출하여 설정 값의 유효성을 즉시 검사합니다.
# 만약 검증에 실패하면, 프로그램은 시작 단계에서 예외를 발생시키고 종료됩니다.
CFG.validate()
