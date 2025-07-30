"""
애플리케이션의 메인 진입점 (Entry Point).

이 스크립트는 전체 트레이딩 봇 애플리케이션을 시작하는 역할을 합니다.
실행 순서는 다음과 같습니다:
1. `config.py`에서 설정 값을 읽어와 사용할 거래소(`Binance` 또는 `Bybit`)를 결정합니다.
2. 해당 거래소와 통신할 수 있는 `ExchangeClient` 객체를 생성합니다.
3. 데이터, 모델, 주문을 처리하는 각 서비스(`IndicatorRepository`, `ModelService`, `OrderService`)를 초기화합니다.
   이때, 앞에서 생성한 거래소 객체를 서비스에 주입(Dependency Injection)합니다.
4. 모든 서비스를 관장하는 메인 `TradingBot` 객체를 생성합니다.
5. 봇의 메인 트레이딩 루프(`bot.loop`)를 백그라운드 스레드에서 실행시킵니다.
6. Streamlit을 사용하여 사용자 인터페이스(UI) 대시보드를 실행합니다.

`if __name__ == "__main__":` 블록을 사용하여 이 스크립트가 직접 실행될 때만 `main()` 함수가 호출되도록 보장합니다.
"""
import threading
from config.config import CFG
from src.exchange.binance_futures import BinanceFutures
from src.exchange.bybit_futures import BybitFutures
from src.data.indicator_repository import IndicatorRepository
from src.model.model_service import ModelService
from src.order.order_service import OrderService
from src.bot.trading_bot import TradingBot
from src.ui.dashboard import run_dashboard

def setup_exchange():
    """
    설정(`CFG.EXCHANGE_NAME`)에 따라 적절한 거래소 클라이언트 객체를 생성하고 반환합니다.

    `config.py`에 정의된 `EXCHANGE_NAME` 환경 변수 값에 따라
    'BYBIT'이면 `BybitFutures` 인스턴스를, 그 외의 경우(기본값 'BINANCE')는 `BinanceFutures` 인스턴스를 생성합니다.
    이렇게 생성된 거래소 객체는 실제 API 연동을 담당하며, 다른 서비스들에게 의존성으로 주입됩니다.

    Returns:
        ExchangeClient: `BinanceFutures` 또는 `BybitFutures`의 인스턴스.
                         두 클래스 모두 `ExchangeClient` 추상 클래스를 상속받으므로,
                         동일한 인터페이스(메서드)를 통해 제어할 수 있습니다.
    """
    if CFG.EXCHANGE_NAME == "BYBIT":
        # Bybit 거래소 클라이언트 생성
        exchange = BybitFutures(CFG.API_KEY, CFG.API_SECRET)
    else:
        # Binance 거래소 클라이언트 생성 (기본값)
        exchange = BinanceFutures(CFG.API_KEY, CFG.API_SECRET)
    return exchange

def setup_services(exchange):
    """
    애플리케이션의 핵심 서비스(데이터, 모델, 주문) 객체들을 생성하고 반환합니다.

    - IndicatorRepository: OHLCV 데이터 조회 및 기술적 지표 계산을 담당합니다.
    - ModelService: XGBoost 머신러닝 모델의 학습, 예측, 관리를 담당합니다.
    - OrderService: 포지션 관리, 실제/모의 주문 실행, 손익 계산 등을 담당합니다.

    Args:
        exchange (ExchangeClient): `setup_exchange`에서 생성된 거래소 클라이언트 객체.
                                   이 객체는 `IndicatorRepository`와 `OrderService`에 전달되어
                                   실제 거래소 데이터 조회 및 주문 실행에 사용됩니다.

    Returns:
        tuple: `(IndicatorRepository, ModelService, OrderService)` 튜플을 반환합니다.
    """
    # 데이터 리포지토리 서비스 초기화. 거래소 객체와 거래 심볼을 인자로 받습니다.
    repo = IndicatorRepository(exchange, CFG.SYMBOL)
    # 모델 서비스 초기화. 학습된 모델이 저장될 파일 경로를 인자로 받습니다.
    model = ModelService(CFG.MODEL_FP)
    # 주문 서비스 초기화. 거래소 객체, 페이퍼 트레이딩 모드 여부, 초기 잔고를 인자로 받습니다.
    order = OrderService(exchange, paper=CFG.TEST_MODE, init_balance=CFG.INIT_BAL)
    return repo, model, order

def start_bot_and_dashboard(repo, model, order):
    """
    트레이딩 봇을 생성하고, 봇의 메인 루프와 대시보드를 실행합니다.

    - TradingBot: 모든 서비스를 인자로 받아 전체 트레이딩 로직을 관장하는 오케스트레이터입니다.
    - `bot.loop`: 봇의 핵심 로직이 담긴 무한 루프. 백그라운드 스레드에서 실행되어
                  UI나 다른 작업을 차단하지 않습니다. `daemon=True`로 설정하여
                  메인 프로그램이 종료될 때 스레드도 함께 종료되도록 합니다.
    - `run_dashboard`: Streamlit 기반의 UI를 실행하는 함수. 메인 스레드에서 실행됩니다.

    Args:
        repo (IndicatorRepository): 데이터 서비스 객체.
        model (ModelService): 모델 서비스 객체.
        order (OrderService): 주문 서비스 객체.
    """
    # 모든 서비스를 주입하여 트레이딩 봇 인스턴스를 생성합니다.
    bot = TradingBot(repo, model, order)
    # 봇의 메인 루프를 별도의 스레드에서 시작합니다.
    threading.Thread(target=bot.loop, daemon=True).start()
    # 메인 스레드에서는 대시보드를 실행합니다.
    run_dashboard(bot)

def main():
    """
    애플리케이션의 메인 실행 함수.
    각 구성 요소를 설정하고 실행하는 과정을 순차적으로 호출합니다.
    """
    # ── 1) 거래소 선택 및 초기화 ──
    # 설정 파일에 따라 바이낸스 또는 바이빗 거래소 객체를 생성합니다.
    exchange = setup_exchange()

    # ── 2) 핵심 서비스 객체 생성 ──
    # 데이터, 모델, 주문 서비스를 초기화하고 필요한 의존성(exchange)을 주입합니다.
    repo, model, order = setup_services(exchange)

    # ── 3) 봇 루프 및 UI 실행 ──
    # 생성된 서비스들을 바탕으로 봇을 시작하고, 실시간 대시보드를 띄웁니다.
    start_bot_and_dashboard(repo, model, order)

# 이 스크립트가 인터프리터를 통해 직접 실행되었을 때만 아래 코드를 실행합니다.
# 다른 모듈에서 이 파일을 `import` 할 경우에는 실행되지 않습니다.
if __name__ == "__main__":
    main()
