"""
이 파일은 우리 트레이딩 봇이 얼마나 똑똑하고 건강한지, 단계별로 진찰해보기 위한 '병원 진료 차트' 같은 거예요.
각 기능들이 자기 역할을 잘 하고 있는지 하나씩 테스트해볼 수 있도록 도와줍니다.

**어떻게 사용하나요?**
1.  `.env` 파일에 우리가 원하는 설정을 모두 다 적어주세요. (예: 어떤 코인을 거래할지, 레버리지는 몇 배로 할지 등)
2.  이 파일을 실행하면(터미널에서 `python step_by_step_test.py`),
    아래에 만들어 둔 테스트 함수들이 순서대로 실행되면서 결과를 보여줄 거예요.
3.  마치 의사 선생님이 "숨 크게 쉬어보세요~" 하고 확인하는 것처럼,
    우리도 각 단계의 결과가 우리가 예상한 대로 나왔는지 눈으로 직접 확인하면 됩니다.
"""

# .env 파일에 적어둔 비밀 설정들을 파이썬으로 가져오기 위해 필요한 마법 도구예요.
from dotenv import load_dotenv
# 우리 프로그램의 모든 설정을 담고 있는 '설정 보관함'을 가져와요.
from config.config import CFG
# main.py 에서 만들었던 똑똑한 기능들을 가져와요.
from main import setup_exchange, setup_services
# 데이터를 다루는 '판다스'라는 아주 강력한 도구를 가져와요.
import pandas as pd
# 실제 데이터 리포지토리 클래스를 가져와요. 이걸 흉내내서 가짜 클래스를 만들 거예요.
from src.data.indicator_repository import IndicatorRepository
# 기술적 지표를 계산해주는 함수를 가져와요.
from src.utils.helpers import add_indicators
# ML 모델 서비스를 가져와요.
from src.model.model_service import ModelService
# 주문 서비스를 가져와요.
from src.order.order_service import OrderService
# 실제 거래소 클라이언트의 '설계도'를 가져와요. 이걸 상속받아 가짜 클라이언트를 만들 거예요.
from src.exchange.exchange_client import ExchangeClient
# 최종 매매 신호를 생성하는 전략 클래스를 가져와요.
from src.strategy.strategy import Strategy
# 파일 및 디렉토리 관리를 위한 도구를 가져와요.
import os
import shutil
from datetime import datetime


class MockIndicatorRepository(IndicatorRepository):
    """
    실제 거래소에 접속하는 대신, 우리가 미리 만들어둔 CSV 파일에서 데이터를 읽어오는
    '가짜' 데이터 리포지토리예요.
    이렇게 하면 인터넷 연결이나 거래소 API 차단 문제 없이 데이터 관련 기능을 테스트할 수 있어요.
    """
    def __init__(self, symbol=None):
        # 부모 클래스(IndicatorRepository)의 초기화 메서드를 호출하되,
        # 거래소(exchange) 부분은 None으로 설정해서 실제 접속을 막아요.
        super().__init__(exchange=None, symbol=symbol)
        print("   - [알림] 진짜 데이터 리포지토리 대신 '가짜' 리포지토리가 생성되었습니다.")

    def get_merged(self):
        """
        실제로는 여러 데이터를 합치고 복잡한 계산을 하지만,
        여기서는 그냥 CSV 파일을 읽어서 그 데이터를 반환하는 척할 거예요.
        """
        print("   - [알림] 가짜 리포지토리가 'mock_data.csv' 파일에서 데이터를 읽습니다...")
        # 'mock_data.csv' 파일을 읽어서 데이터프레임으로 만들어요.
        df = pd.read_csv("mock_data.csv")
        # 실제 데이터처럼 'timestamp' 컬럼을 날짜/시간 형식으로 바꿔줘요.
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        # 기술적 지표를 계산하는 부분은 진짜와 똑같이 사용해요.
        df_with_indicators = add_indicators(df)

        # --- 진짜 IndicatorRepository의 병합 로직 흉내내기 ---
        # ModelService가 "rsi_1h", "ema_fast_4h" 같은 특수한 이름의 컬럼을 찾기 때문에,
        # 우리도 가짜 데이터에 이 컬럼들을 만들어줘야 해요.
        # 여기서는 간단하게, 그냥 기본 타임프레임의 지표를 복사해서 이름만 바꿔줄게요.
        print("   - [알림] 모델 학습에 필요한 멀티-타임프레임 컬럼을 생성합니다...")
        df_with_indicators["rsi_1h"] = df_with_indicators["rsi"]
        df_with_indicators["ema_fast_4h"] = df_with_indicators["ema_fast"]
        df_with_indicators["ema_slow_4h"] = df_with_indicators["ema_slow"]

        # 모델 학습에는 '정답'에 해당하는 'target' 컬럼도 필요해요.
        # 다음 캔들의 종가가 현재 종가보다 올랐으면 1, 아니면 0으로 표시해요.
        df_with_indicators["target"] = (df_with_indicators["close"].shift(-1) > df_with_indicators["close"]).astype(int)

        # 실제 코드처럼, 마지막에 NaN 값이 있는 행들은 모두 제거해줘요.
        return df_with_indicators.dropna()


# 파이썬에게 "이 파일이 직접 실행될 때만 아래 코드를 동작시켜줘!" 라고 알려주는 약속이에요.
# 만약 다른 파일에서 이 파일을 import(가져오기) 할 때는 실행되지 않아요.
if __name__ == "__main__":
    # 제일 먼저, .env 파일에 적어둔 설정들을 모두 읽어와서 준비해요.
    # 이 한 줄이 없으면, 우리 봇은 어떤 설정을 써야 할지 몰라서 길을 잃게 돼요.
    load_dotenv()

    # === Phase 1: 환경 설정 및 데이터 검증 (가장 기본) ===
    # 집을 짓기 전에 땅이 튼튼한지, 설계도는 잘 나왔는지 확인하는 단계예요.
    # 봇이 제대로 달리려면, 가장 기본적인 환경과 데이터가 완벽해야 해요.

    def test_phase_1_1_config_values():
        """
        [테스트 1-1: 설정 값 검증]
        우리가 `.env` 파일에 정성껏 적어둔 설정들이 프로그램 안으로 잘 들어왔는지 확인하는 단계예요.
        마치 쇼핑 목록을 적어놓고, 가게에서 물건을 살 때 목록과 같은 물건을 집었는지 확인하는 것과 같아요.
        """
        # 테스트 시작을 보기 좋게 알려주는 메시지예요.
        print("="*60)
        print("▶️ [테스트 1-1] 설정(.env)이 프로그램에 잘 로드되었는지 확인합니다.")
        print("="*60)

        # 왜(Why) 이 테스트를 할까요?
        # 만약 SYMBOL 설정이 'BTC/USDT'가 아니라 엉뚱한 'ETH/USDT'로 들어왔다면,
        # 우리 봇은 우리가 원하지 않는 코인을 거래하려고 할 거예요. 그래서 꼭 확인해야 해요.

        # 어떻게(How) 테스트를 할까요?
        # CFG 보관함에 들어있는 값들을 하나씩 꺼내서 화면에 보여달라고 할 거예요.
        # 그리고 우리는 그 결과가 `.env` 파일의 내용과 똑같은지 눈으로 확인하면 돼요.

        print("1. 거래소 이름 (Exchange Name):")
        print(f"   - .env 파일에 설정된 값: {CFG.EXCHANGE_NAME}")
        print(f"   - (확인) 'BINANCE' 또는 'BYBIT' 중 하나로 잘 나왔나요?")
        print("-" * 20)

        print("2. 거래할 코인 (Symbol):")
        print(f"   - .env 파일에 설정된 값: {CFG.SYMBOL}")
        print(f"   - (확인) 우리가 거래하고 싶은 코인 이름이 정확한가요?")
        print("-" * 20)

        print("3. 레버리지 (Leverage):")
        print(f"   - .env 파일에 설정된 값: {CFG.LEVERAGE}")
        print(f"   - (확인) 우리가 설정한 레버리지 숫자가 맞나요?")
        print("-" * 20)

        print("4. 테스트 모드 (Test Mode):")
        print(f"   - .env 파일에 설정된 값: {CFG.TEST_MODE}")
        print(f"   - (확인) 'True'(모의투자) 또는 'False'(실전투자)가 맞나요? 지금은 True여야 안전해요!")
        print("-" * 20)

        print("5. 초기 자본금 (Initial Balance for Paper Trading):")
        print(f"   - .env 파일에 설정된 값: {CFG.INIT_BAL}")
        print(f"   - (확인) 모의투자를 위한 초기 자본금이 우리가 설정한 금액과 일치하나요?")
        print("\n")

        # assert는 '주장하다', '단언하다'라는 뜻이에요.
        # 개발자가 "이건 반드시 이래야 해!" 라고 강력하게 주장하는 코드예요.
        # 만약 이 주장이 틀리면, 프로그램은 그 자리에서 바로 멈추고 에러를 보여줘요.
        # 여기서는 "TEST_MODE는 반드시 True여야 해!" 라고 주장해서,
        # 실수로 실전 투자 모드로 테스트하는 것을 막아주는 안전장치 역할을 해요.
        assert CFG.TEST_MODE is True, "실수로 실제 돈을 사용할 수 있으니, 테스트 시에는 TEST_MODE를 항상 'true'로 설정해주세요!"

        print("✅ [성공] 설정 값들이 올바르게 로드된 것을 확인했습니다.")
        print("="*60, "\n")


    # --- 여기서부터 테스트를 실제로 실행하는 부분이에요 ---

    # 위에서 만든 '설정 값 검증' 테스트 함수를 실행해요.
    test_phase_1_1_config_values()

    def test_phase_1_2_data_and_indicators():
        """
        [테스트 1-2: 데이터 수집 및 지표 계산 검증]
        봇의 판단의 근거가 되는 '데이터'가 신선하고 정확한지 확인하는 단계예요.
        마치 요리하기 전에 재료가 신선한지, 잘 손질되었는지 확인하는 것과 같아요.
        """
        print("="*60)
        print("▶️ [테스트 1-2] 데이터 수집 및 기술적 지표 계산을 확인합니다.")
        print("="*60)

        # 왜(Why) 이 테스트를 할까요?
        # 만약 오래된 데이터를 가져오거나, 기술적 지표(RSI, MACD 등) 계산이 잘못된다면,
        # 봇은 잘못된 정보를 바탕으로 엉뚱한 판단을 내릴 수밖에 없어요.

        # 어떻게(How) 테스트를 할까요?
        # 1. 거래소 클라이언트를 먼저 설정합니다. (데이터를 가져오려면 거래소와 통신해야 하니까요)
        # 2. 데이터 담당 서비스(IndicatorRepository)를 통해 데이터를 가져오라고 시킵니다.
        # 3. 가져온 데이터가 최신인지, 그리고 각종 지표들이 숫자로 잘 계산되었는지 출력해서 확인합니다.

        print("1. '가짜' 데이터 리포지토리(MockIndicatorRepository)를 준비합니다...")
        # 진짜 거래소에 접속하는 대신, 가짜 리포지토리를 생성해요.
        repo = MockIndicatorRepository(symbol=CFG.SYMBOL)
        print("   - 준비 완료!")
        print("-" * 20)

        print("2. 가짜 리포지토리(repo)에서 데이터를 가져옵니다...")
        # 가짜 리포지토리의 get_merged()를 호출해요.
        # 이 함수는 내부에선 mock_data.csv를 읽고 지표를 계산해서 돌려줄 거예요.
        df = repo.get_merged()
        print("   - 데이터 수집 및 계산 완료!")
        print("-" * 20)

        print("3. 가져온 데이터가 최신 데이터인지 확인합니다.")
        print("   - 아래는 가장 최근 5개의 데이터입니다. 날짜와 시간이 현재와 비슷한가요?")
        # .tail(5)는 데이터의 가장 마지막 5줄(가장 최신 데이터)을 보여주는 명령어예요.
        print(df.tail(5))
        print("-" * 20)

        print("4. 주요 기술적 지표들이 잘 계산되었는지 확인합니다.")
        print("   - 아래는 주요 지표들의 마지막 10개 값입니다. 'NaN' 없이 숫자로 잘 채워져 있나요?")
        # 보고 싶은 특정 컬럼들만 골라서 마지막 10개를 출력해요.
        # 이를 통해 EMA, RSI, MACD 같은 핵심 지표들이 문제없이 계산되었는지 빠르게 확인할 수 있어요.
        print(df[['close', 'ema_fast', 'ema_slow', 'rsi', 'macd']].tail(10))
        print("\n")

        # 여기서도 assert를 사용해 "가져온 데이터는 비어있으면 안돼!" 라고 강력하게 주장해요.
        # 만약 데이터를 하나도 못가져왔다면(df.empty가 True라면), 테스트는 여기서 멈추게 돼요.
        assert not df.empty, "데이터를 가져오지 못했습니다. 인터넷 연결이나 API 키를 확인해주세요."

        print("✅ [성공] 데이터 수집 및 지표 계산이 올바르게 수행된 것을 확인했습니다.")
        print("="*60, "\n")

    # 위에서 만든 '데이터 및 지표 검증' 테스트 함수를 실행해요.
    test_phase_1_2_data_and_indicators()

    def test_phase_2_1_model_service():
        """
        [테스트 2-1: 머신러닝 모델 단위 테스트]
        봇의 두뇌 역할을 하는 ML 모델이 스스로 학습하고, 예측하는 기능을 잘 수행하는지 확인해요.
        """
        print("="*60)
        print("▶️ [테스트 2-1] 머신러닝 모델의 학습 및 예측 기능을 확인합니다.")
        print("="*60)

        # 왜(Why) 이 테스트를 할까요?
        # 모델이 제대로 학습되지 않거나, 엉뚱한 값을 예측한다면 봇의 모든 결정이 잘못될 수 있어요.
        # 그래서 모델의 핵심 기능인 '학습'과 '예측'을 따로 떼어내서 검증해야 해요.

        # 어떻게(How) 테스트를 할까요?
        # 1. 테스트를 위한 깨끗한 환경을 만듭니다. (기존에 학습된 모델 파일이 있다면 삭제)
        # 2. 가짜 데이터(mock_data)를 준비합니다.
        # 3. 모델 서비스(ModelService)에게 가짜 데이터로 학습하라고 시킵니다.
        # 4. 학습이 끝난 후, 모델 파일이 잘 저장되었는지 확인합니다.
        # 5. 학습된 모델에게 예측을 시켜보고, 결과가 정상적인지(0과 1 사이의 확률값) 확인합니다.

        print("1. 테스트 환경을 준비합니다...")
        # 'models' 라는 폴더가 이미 있다면, 깨끗한 테스트를 위해 폴더 안의 모든 것을 지워요.
        if os.path.exists(CFG.MODEL_DIR):
            shutil.rmtree(CFG.MODEL_DIR)
            print(f"   - 기존 '{CFG.MODEL_DIR}' 폴더를 삭제했습니다.")
        # 모델을 저장할 폴더를 새로 만들어요.
        os.makedirs(CFG.MODEL_DIR)
        print(f"   - 새 '{CFG.MODEL_DIR}' 폴더를 생성했습니다.")
        print("-" * 20)

        print("2. 모델 학습에 사용할 데이터를 준비합니다...")
        # 이전 테스트에서 사용했던 가짜 데이터 리포지토리를 다시 사용해요.
        mock_repo = MockIndicatorRepository(symbol=CFG.SYMBOL)
        df_train = mock_repo.get_merged()
        print(f"   - {len(df_train)} 줄의 학습 데이터를 준비했습니다.")
        print("-" * 20)

        print("3. 모델 서비스를 생성하고 학습을 시작합니다...")
        # 모델 서비스를 생성해요. CFG.MODEL_FP는 모델이 저장될 파일 경로예요.
        model = ModelService(CFG.MODEL_FP)
        # 학습 시작! 이 과정은 컴퓨터 성능에 따라 약간의 시간이 걸릴 수 있어요.
        model.train(df_train)
        print("-" * 20)

        print("4. 학습된 모델 파일이 잘 저장되었는지 확인합니다...")
        # 학습이 끝나면, CFG.MODEL_FP 경로에 모델 파일이 생겨야 해요.
        # 파일이 존재하는지 확인해서, 학습 및 저장 기능이 잘 작동했는지 검증해요.
        assert os.path.exists(CFG.MODEL_FP), f"학습 후 모델 파일({CFG.MODEL_FP})이 생성되지 않았습니다!"
        print(f"   - ✅ 성공: 모델 파일이 '{CFG.MODEL_FP}' 경로에 잘 저장되었습니다.")
        print("-" * 20)

        print("5. 학습된 모델로 예측을 수행하고 결과를 확인합니다...")
        # 학습에 사용했던 데이터로 예측을 수행해요.
        df_pred = model.add_prob(df_train)
        # 'prob_up' 컬럼이 새로 추가되었는지 확인해요.
        assert 'prob_up' in df_pred.columns, "예측 후 'prob_up' 컬럼이 추가되지 않았습니다!"
        print("   - 'prob_up' 컬럼이 성공적으로 추가되었습니다.")

        # 예측된 확률 값들이 0과 1 사이에 있는지 확인해요. 확률은 이 범위를 벗어날 수 없으니까요.
        is_prob_valid = df_pred['prob_up'].between(0, 1).all()
        assert is_prob_valid, "예측된 확률값이 0과 1 사이의 범위를 벗어났습니다!"
        print("   - 예측된 확률 값들이 모두 0과 1 사이의 유효한 값입니다.")
        print("   - 아래는 예측 결과의 마지막 5줄입니다.")
        print(df_pred[['close', 'prob_up']].tail())
        print("\n")

        print("✅ [성공] 모델의 학습, 저장, 예측 기능이 모두 올바르게 수행된 것을 확인했습니다.")
        print("="*60, "\n")

    # 위에서 만든 '모델 서비스 검증' 테스트 함수를 실행해요.
    test_phase_2_1_model_service()

    class MockExchange(ExchangeClient):
        """
        실제 거래소에 주문을 보내는 대신, 어떤 주문이 들어왔는지 기록만 하는 '가짜' 거래소 클라이언트예요.
        이걸 사용하면 실제 돈이나 API 키 없이도 주문 로직을 안전하게 테스트할 수 있어요.
        """
        def __init__(self):
            # 이 리스트에 들어온 주문들을 차곡차곡 기록할 거예요.
            self.orders = []
            # 실제 ExchangeClient는 내부에 ccxt 클라이언트 객체를 'client' 속성으로 가지고 있어요.
            # 우리 가짜 객체도 똑같은 구조를 갖도록 자기 자신을 'client'로 설정해요.
            self.client = self

        def get_name(self):
            return "MockExchange"

        def create_market_order(self, symbol, side, qty):
            # 시장가 주문을 기록해요.
            print(f"   - [가짜 거래소] 시장가 주문 접수: {symbol}, {side}, 수량 {qty}")
            order = {"symbol": symbol, "side": side, "qty": qty, "type": "market"}
            self.orders.append(order)
            # 실제 주문처럼 주문 정보를 담은 딕셔너리를 반환해요.
            return {"price": 50000 * 1.0005} # 슬리피지가 적용된 것처럼 가짜 체결가를 반환

        def create_exit_order(self, symbol, side, qty, price, tp):
            # TP/SL 주문을 기록해요.
            order_type = "TP" if tp else "SL"
            print(f"   - [가짜 거래소] {order_type} 주문 접수: {symbol}, {side}, 수량 {qty}, 가격 {price}")
            order = {"symbol": symbol, "side": side, "qty": qty, "price": price, "type": order_type}
            self.orders.append(order)
            return order

        def set_leverage(self, symbol, leverage, isolated):
            # 레버리지 설정 요청을 받았다고 로그만 남겨요.
            print(f"   - [가짜 거래소] 레버리지 설정: {symbol}, {leverage}x, 격리: {isolated}")

        def fetch_funding_rate(self, symbol):
            # 항상 0을 반환해서 펀딩비 계산을 단순하게 만들어요.
            return 0.0

        # --- 아래는 실제 코드에서 사용하지만, 이 테스트에서는 필요 없는 '필수' 메서드들이에요 ---
        # ExchangeClient 라는 설계도를 따르려면, 이 메서드들이 비어있더라도 꼭 존재해야 해요.
        def fetch_ohlcv(self, symbol, timeframe, since, limit):
            return [] # 그냥 비어있는 리스트를 반환해요.

        def fetch_position(self, symbol):
            return None # 포지션이 없다고 알려줘요.

        def get_price_precision(self, symbol, price):
            return price # 가격을 그대로 돌려줘요.

        def price_to_precision(self, symbol, price):
            return price # 가격을 그대로 돌려줘요.


    def test_phase_2_2_order_service():
        """
        [테스트 2-2: 주문 관리 단위 테스트]
        실제 돈을 다루는 주문 서비스가 실전처럼, 그리고 모의투자 상황에서 모두 잘 작동하는지 확인해요.
        특히, 지적해주신 대로 '손절/익절 주문'이 함께 잘 들어가는지 집중적으로 검증합니다.
        """
        print("="*60)
        print("▶️ [테스트 2-2] 주문 서비스의 핵심 기능(진입, 종료, SL/TP)을 확인합니다.")
        print("="*60)

        # --- 1. 실전 투자 모드 테스트 (가짜 거래소 사용) ---
        print("--- 1. 실전 투자 모드(paper=False) 테스트 ---")
        print("1. '가짜' 거래소 클라이언트와 주문 서비스를 준비합니다...")
        mock_exchange = MockExchange()
        # paper=False로 설정해서, 주문 서비스가 실제 주문을 보내는 로직을 타도록 만들어요.
        order_service_live = OrderService(mock_exchange, paper=False)
        print("-" * 20)

        print("2. 롱 포지션 진입을 요청합니다...")
        # 50000달러에 0.1 BTC 롱 포지션 진입!
        order_service_live.open_position(px=50000, qty=0.1, side="long")
        print("-" * 20)

        print("3. 손절/익절 주문이 거래소로 잘 전송되었는지 확인합니다...")
        # 가짜 거래소에 기록된 주문 목록을 확인해요.
        # 주문은 총 3개여야 해요: (1)시장가 진입, (2)TP 주문, (3)SL 주문
        assert len(mock_exchange.orders) == 3, f"시장가, TP, SL 포함 총 3개의 주문이 기록되어야 하는데, {len(mock_exchange.orders)}개만 기록되었습니다."
        print("   - ✅ 성공: 총 3개의 주문(시장가, TP, SL)이 정상적으로 접수되었습니다.")

        # 각 주문의 상세 내역을 확인해요.
        market_order = mock_exchange.orders[0]
        tp_order = mock_exchange.orders[1]
        sl_order = mock_exchange.orders[2]

        assert market_order['type'] == 'market' and market_order['side'] == 'buy'
        print("   - ✅ 성공: 첫 번째 주문은 '시장가 매수(buy)'가 맞습니다.")

        assert tp_order['type'] == 'TP' and tp_order['side'] == 'SELL'
        print(f"   - ✅ 성공: 두 번째 주문은 'TP 매도(SELL)' 주문이 맞습니다. (가격: {tp_order['price']})")

        assert sl_order['type'] == 'SL' and sl_order['side'] == 'SELL'
        print(f"   - ✅ 성공: 세 번째 주문은 'SL 매도(SELL)' 주문이 맞습니다. (가격: {sl_order['price']})")
        print("\n")


        # --- 2. 모의 투자 모드 테스트 ---
        print("--- 2. 모의 투자 모드(paper=True) 테스트 ---")
        print("1. 모의 투자용 주문 서비스를 준비합니다...")
        # paper=True로 설정해서, 모든 것을 자체적으로 시뮬레이션하도록 만들어요.
        order_service_paper = OrderService(MockExchange(), paper=True, init_balance=10000)
        print("-" * 20)

        print("2. 롱 포지션 진입을 요청합니다...")
        order_service_paper.open_position(px=50000, qty=0.1, side="long")
        entry_price = order_service_paper.pos['entry']
        print(f"   - 포지션 진입 완료. (진입가: {entry_price})")
        print("-" * 20)

        print("3. 가격이 손절(SL) 라인에 도달한 상황을 시뮬레이션합니다...")
        # SL 가격 = 진입가 * (1 - 0.02) = 50025 * 0.98 = 49024.5
        sl_price = entry_price * (1 - CFG.SL_PCT)
        order_service_paper.poll_position_closed(sl_price * 0.999) # 살짝 더 아래 가격으로 테스트
        assert order_service_paper.pos is None, "손절 후 포지션이 청산되지 않았습니다."
        print(f"   - ✅ 성공: 현재가가 SL 가격({sl_price:.2f})에 도달하자 포지션이 자동으로 청산되었습니다.")
        print(f"   - 현재 잔고: {order_service_paper.balance:.2f} (손실 반영)")
        print("-" * 20)

        print("4. 다시 진입 후, 가격이 익절(TP) 라인에 도달한 상황을 시뮬레이션합니다...")
        order_service_paper.open_position(px=50000, qty=0.1, side="long")
        entry_price = order_service_paper.pos['entry']
        tp_price = entry_price * (1 + CFG.TP_PCT)
        order_service_paper.poll_position_closed(tp_price * 1.001) # 살짝 더 위 가격으로 테스트
        assert order_service_paper.pos is None, "익절 후 포지션이 청산되지 않았습니다."
        print(f"   - ✅ 성공: 현재가가 TP 가격({tp_price:.2f})에 도달하자 포지션이 자동으로 청산되었습니다.")
        print(f"   - 현재 잔고: {order_service_paper.balance:.2f} (수익 반영)")
        print("\n")

        print("✅ [성공] 주문 서비스가 실전/모의 환경 모두에서 올바르게 작동하는 것을 확인했습니다.")
        print("="*60, "\n")


    # 위에서 만든 '주문 서비스 검증' 테스트 함수를 실행해요.
    test_phase_2_2_order_service()

    def test_phase_2_3_strategy():
        """
        [테스트 2-3: 전략 및 신호 생성 통합 테스트]
        데이터, 모델 예측, 전략 규칙이 모두 합쳐져서 최종 매매 신호가 올바르게 생성되는지 확인해요.
        """
        print("="*60)
        print("▶️ [테스트 2-3] 최종 매매 신호 생성 로직을 확인합니다.")
        print("="*60)

        # 왜(Why) 이 테스트를 할까요?
        # 각 부품(데이터, 모델)이 완벽해도, 최종 조립(전략)이 잘못되면 엉뚱한 신호가 나올 수 있어요.
        # "규칙도 맞고, 모델 예측도 좋을 때만" 진입 신호가 나오는지 확인해야 해요.

        # 어떻게(How) 테스트를 할까요?
        # 1. 테스트에 필요한 데이터와 학습된 모델을 준비합니다.
        # 2. Strategy.enrich()를 호출하여 최종 신호를 생성합니다.
        # 3. long 신호가 나온 지점들을 모두 찾아서, 정말로 rule_long과 prob_up 조건이 모두 참인지 검증합니다.
        # 4. short 신호에 대해서도 동일하게 검증합니다.

        print("1. 테스트에 필요한 데이터와 모델을 준비합니다...")
        mock_repo = MockIndicatorRepository(CFG.SYMBOL)
        model = ModelService(CFG.MODEL_FP) # 이전에 학습/저장된 모델을 불러와요.
        df = mock_repo.get_merged()
        df_with_prob = model.add_prob(df)
        print("   - 준비 완료!")
        print("-" * 20)

        print("2. 전략을 적용하여 최종 신호를 생성합니다...")
        df_final = Strategy.enrich(df_with_prob)
        print("   - 최종 신호 생성 완료!")
        print("-" * 20)

        print("3. 'long' 신호가 발생한 지점들을 검증합니다...")
        long_signals = df_final[df_final['long']]
        if not long_signals.empty:
            # long 신호가 하나라도 있다면, 그 신호들의 모든 'rule_long' 컬럼 값은 True여야만 해요.
            assert long_signals['rule_long'].all(), "'long' 신호가 나왔지만 'rule_long'이 False인 경우가 있습니다."
            # 또한, 'prob_up'은 BUY_TH 임계값보다 커야 해요.
            assert (long_signals['prob_up'] > CFG.BUY_TH).all(), f"'long' 신호가 나왔지만 상승 확률이 {CFG.BUY_TH} 이하인 경우가 있습니다."
            print(f"   - ✅ 성공: 총 {len(long_signals)}개의 'long' 신호 모두가 'rule_long'과 'prob_up > {CFG.BUY_TH}' 조건을 만족했습니다.")
        else:
            print("   - 정보: 이번 테스트 데이터에서는 'long' 신호가 발생하지 않았습니다.")
        print("-" * 20)

        print("4. 'short' 신호가 발생한 지점들을 검증합니다...")
        short_signals = df_final[df_final['short']]
        if not short_signals.empty:
            assert short_signals['rule_short'].all(), "'short' 신호가 나왔지만 'rule_short'이 False인 경우가 있습니다."
            assert (short_signals['prob_up'] < CFG.SHORT_TH).all(), f"'short' 신호가 나왔지만 상승 확률이 {CFG.SHORT_TH} 이상인 경우가 있습니다."
            print(f"   - ✅ 성공: 총 {len(short_signals)}개의 'short' 신호 모두가 'rule_short'과 'prob_up < {CFG.SHORT_TH}' 조건을 만족했습니다.")
        else:
            print("   - 정보: 이번 테스트 데이터에서는 'short' 신호가 발생하지 않았습니다.")
        print("\n")

        print("✅ [성공] 전략에 따른 최종 매매 신호 생성 로직이 올바르게 작동하는 것을 확인했습니다.")
        print("="*60, "\n")


    # 위에서 만든 '전략 검증' 테스트 함수를 실행해요.
    test_phase_2_3_strategy()

    def test_phase_2_4_risk_management():
        """
        [테스트 2-4: 리스크 관리 기능 검증]
        봇이 큰 손실을 입지 않도록 막아주는 중요한 안전장치, '연속 손실 제한' 기능이 잘 작동하는지 확인해요.
        """
        print("="*60)
        print("▶️ [테스트 2-4] 리스크 관리(연속 손실 시 거래 중단) 기능을 확인합니다.")
        print("="*60)

        # 왜(Why) 이 테스트를 할까요?
        # 시장이 예상과 다르게 흘러갈 때, 봇이 계속해서 돈을 잃는 것을 막아야 해요.
        # 이 기능은 설정된 횟수만큼 연속으로 손실이 나면, 봇을 잠시 쉬게 해서 더 큰 피해를 방지해요.

        # 어떻게(How) 테스트를 할까요?
        # 1. 모의 거래용 주문 서비스를 준비합니다.
        # 2. 일부러 손실이 나는 상황을 3번 연속으로 만듭니다. (CFG.MAX_LOSS 기본값이 3)
        # 3. 3번째 손실 직후, 봇이 '일시정지' 상태로 바뀌었는지 확인합니다.

        print("1. 모의 투자용 주문 서비스를 준비합니다...")
        order_service = OrderService(MockExchange(), paper=True, init_balance=10000)
        print("   - 준비 완료!")
        print("-" * 20)

        print("2. 일부러 손실을 3번 연속으로 발생시킵니다...")
        # CFG.MAX_LOSS 에 설정된 횟수만큼 반복해요.
        for i in range(CFG.MAX_LOSS):
            print(f"   - 손실 발생 시도 ({i+1}/{CFG.MAX_LOSS})...")
            # 롱 포지션에 진입하자마자
            order_service.open_position(px=50000, qty=0.1, side="long")
            entry_price = order_service.pos['entry']
            # 바로 손절 가격으로 청산시켜서 손실을 만들어요.
            sl_price = entry_price * (1 - CFG.SL_PCT)
            order_service.poll_position_closed(sl_price)
        print("   - 3회 연속 손실 발생 완료.")
        print("-" * 20)

        print("3. 거래가 '일시정지' 상태인지 확인합니다...")
        # is_paused() 메서드는 봇이 정지 상태일 때 True를 반환해야 해요.
        assert order_service.is_paused(), "연속 손실 후에도 거래가 중단되지 않았습니다."
        print("   - ✅ 성공: is_paused()가 True를 반환했습니다.")
        # pause_until 변수에는 미래의 시간이 기록되어 있어야 해요.
        assert order_service.pause_until > datetime.utcnow(), "거래 중단 시간이 올바르게 설정되지 않았습니다."
        print(f"   - ✅ 성공: 거래 중단이 {order_service.pause_until} 까지 설정되었습니다.")
        print("\n")

        print("✅ [성공] 연속 손실 시 거래 중단 기능이 올바르게 작동하는 것을 확인했습니다.")
        print("="*60, "\n")


    # 위에서 만든 '리스크 관리 검증' 테스트 함수를 실행해요.
    test_phase_2_4_risk_management()

    # (다음 테스트는 여기에 추가될 예정입니다...)
