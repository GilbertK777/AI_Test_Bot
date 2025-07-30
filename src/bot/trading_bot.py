"""
애플리케이션의 모든 구성요소(데이터, 모델, 주문, 전략)를 총괄하는 메인 오케스트레이터.

`TradingBot` 클래스는 `main.py`에서 초기화된 모든 서비스(Repository, Model, Order)를
주입받아, 이들을 조율하여 실제 트레이딩 로직을 수행합니다.

주요 역할:
- **메인 루프 (`loop`)**: 정해진 주기(`CFG.SLEEP_SEC`)마다 반복 실행되는 무한 루프.
  이 루프 안에서 데이터 조회, 모델 학습/예측, 신호 생성, 주문 실행의 전체 과정이 일어납니다.
- **주기적 모델 재학습**: 설정된 시간(`CFG.RETRAIN_HR`)이 경과하면, 최신 데이터를 사용하여
  `ModelService`의 `train` 메서드를 호출하여 모델을 재학습시킵니다.
- **매매 결정 및 실행**:
  1. `IndicatorRepository`로부터 최신 데이터와 지표를 받아옵니다.
  2. `ModelService`를 사용해 데이터에 예측 확률을 추가합니다.
  3. `Strategy`를 사용해 최종 매매 신호를 생성합니다.
  4. 생성된 신호에 따라 `OrderService`를 통해 포지션을 열거나, 현재 포지션 상태를 관리합니다.
- **데이터 공유**: UI(대시보드) 스레드와 최신 데이터프레임을 안전하게 공유하기 위해
  `threading.Lock`을 사용하여 `df_latest`에 대한 접근을 제어합니다.
"""
import time
import threading
import logging
from datetime import datetime
from config.config import CFG
from src.utils.helpers import tg
from src.strategy.strategy import Strategy
from src.order.order_service import OrderService
from src.model.model_service import ModelService
from src.data.indicator_repository import IndicatorRepository

class TradingBot:
    """메인 트레이딩 루프를 관리하고 모든 서비스를 조율하는 클래스."""

    def __init__(self, repo: IndicatorRepository, model: ModelService, order: OrderService):
        """
        TradingBot 인스턴스를 초기화합니다.

        Args:
            repo (IndicatorRepository): 데이터 제공 서비스.
            model (ModelService): 머신러닝 모델 서비스.
            order (OrderService): 주문 및 포지션 관리 서비스.
        """
        self.repo, self.model, self.order = repo, model, order
        # UI 스레드와 공유될 최신 데이터프레임. None으로 초기화.
        self.df_latest = None
        # `df_latest`에 대한 동시 접근을 막기 위한 락(lock).
        self.lock = threading.Lock()

    def loop(self):
        """
        봇의 메인 실행 루프. `main.py`에서 백그라운드 스레드로 실행됩니다.
        """
        while True:
            try:
                # 1. 리스크 관리 확인: 연속 손실로 인해 거래가 일시 중단 상태인지 확인합니다.
                if self.order.is_paused():
                    time.sleep(CFG.SLEEP_SEC)
                    continue # 일시 중단 상태이면 루프의 나머지 부분을 건너뛰고 다음 사이클로 넘어갑니다.

                # 2. 데이터 준비: IndicatorRepository를 통해 최신 멀티-타임프레임 데이터를 가져옵니다.
                df = self.repo.get_merged()

                # 3. 모델 재학습 여부 결정 및 실행
                # BUGFIX 주석: `.seconds`는 시간 차이의 '초' 부분만 반환(최대 86399).
                # 총 경과 시간을 초로 계산하려면 `.total_seconds()`를 사용해야 합니다.
                need_train = (self.model.model is None or
                              (datetime.utcnow() - self.model.t_last_train).total_seconds() >
                              CFG.RETRAIN_HR * 3600)
                if need_train:
                    self.model.train(df)

                # 4. 예측 및 전략 적용
                df = self.model.add_prob(df) # 데이터에 모델 예측 확률 추가
                df = Strategy.enrich(df)     # 예측 확률과 규칙을 결합하여 최종 신호 생성

                # 5. UI용 데이터 업데이트 (스레드 안전)
                with self.lock:
                    # `df_latest`를 업데이트할 때 락을 사용하여,
                    # UI 스레드가 `get_df`를 통해 데이터를 읽는 동안 데이터가 변경되는 것을 방지합니다.
                    self.df_latest = df.tail(500).copy()

                # 가장 마지막 데이터(가장 최신 캔들)를 `last` 변수에 저장합니다.
                last = df.iloc[-1]

                # 6. 주문 로직 실행
                if self.order.pos is None: # 현재 보유 포지션이 없는 경우
                    if last["long"] or last["short"]: # 새로운 롱 또는 숏 진입 신호가 발생했다면
                        # 포지션 크기(qty) 계산
                        if CFG.MARGIN_PER_TRADE > 0:
                            # 증거금 기준: (사용할 증거금 * 레버리지) / 현재가
                            qty = (CFG.MARGIN_PER_TRADE * CFG.LEVERAGE) / max(last["close"], 1e-6)
                        else:
                            # 수량 기준: 설정된 수량을 ATR로 나눠 변동성에 따라 수량 조절 (현재는 POS_SIZE가 작아 거의 고정수량)
                            qty = CFG.POS_SIZE / max(last["atr"], 1e-6)

                        # 최대 허용 수량을 초과하지 않도록 제한
                        qty = min(qty, CFG.MAX_QTY)

                        # OrderService를 통해 포지션 진입 요청
                        if last["long"]:
                            self.order.open_position(last["close"], qty, "long")
                        if last["short"]:
                            self.order.open_position(last["close"], qty, "short")
                else: # 현재 보유 포지션이 있는 경우
                    # 라이브 모드: 거래소의 실제 포지션과 동기화하여 불일치 문제 해결
                    self.order.sync_position()
                    # 페이퍼 모드: 현재 가격을 기준으로 TP/SL 도달 여부 확인
                    self.order.poll_position_closed(last["close"])

                # 다음 루프 사이클까지 대기
                time.sleep(CFG.SLEEP_SEC)
            except Exception as e:
                # 루프 내에서 어떤 예외든 발생하면 로그를 남기고, 잠시 대기 후 루프를 계속합니다.
                logging.error(f"An error occurred in the main loop: {e}")
                tg(f"⚠️ An error occurred in the main loop: {e}")
                time.sleep(30)

    def get_df(self):
        """
        UI 스레드에서 최신 데이터프레임을 안전하게 가져가기 위한 메서드.

        Returns:
            pd.DataFrame or None: 최신 데이터프레임의 복사본. 아직 데이터가 없으면 None.
        """
        with self.lock:
            # 락을 사용하여 `df_latest`를 읽는 동안 메인 루프 스레드가 데이터를 수정하지 못하도록 보장합니다.
            # `.copy()`를 사용하여 데이터의 복사본을 반환함으로써, UI 스레드에서의 작업이
            # 봇의 내부 데이터에 영향을 주지 않도록 합니다.
            return self.df_latest.copy() if self.df_latest is not None else None
