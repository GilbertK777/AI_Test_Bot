"""
규칙 기반(Rule-based)과 머신러닝(ML)을 결합한 하이브리드 트레이딩 전략.

이 모듈은 최종적인 매매 신호(Long, Short, Exit)를 생성하는 로직을 포함합니다.
`Strategy` 클래스는 상태를 갖지 않는 정적(static) 메서드만을 포함하므로,
인스턴스를 생성할 필요 없이 `Strategy.enrich(df)`와 같이 직접 호출하여 사용합니다.

전략의 핵심 아이디어:
1.  **규칙 기반 필터**: 기술적 지표(EMA, RSI, MACD)를 사용하여 1차적으로 유망한 진입 시점을 포착합니다.
    -   `rule_long`: 상승 추세이면서 과매도 구간에 가까운 시점 (EMA 골든크로스, RSI 낮은 수준, MACD 상승)
    -   `rule_short`: 하락 추세이면서 과매수 구간에 가까운 시점 (EMA 데드크로스, RSI 높은 수준, MACD 하락)
2.  **ML 모델 결정**: 규칙 기반 필터를 통과한 시점에서, `ModelService`가 예측한 상승 확률(`prob_up`)을
    사용하여 최종 진입 여부를 결정합니다.
    -   롱(Long) 진입: `rule_long`이 참이고, 상승 확률이 설정된 임계값(`CFG.BUY_TH`)보다 높을 때.
    -   숏(Short) 진입: `rule_short`가 참이고, 상승 확률이 설정된 임계값(`CFG.SHORT_TH`)보다 낮을 때.
3.  **청산 신호**: 포지션 보유 중, 특정 조건이 발생하면 청산 신호를 생성합니다. 청산 신호는 여러 조건의
    논리합(OR)으로 구성되어, 하나라도 만족하면 발동됩니다.
"""
from config.config import CFG

class Strategy:
    """
    데이터프레임에 진입/청산 신호 컬럼을 추가하는 정적 클래스.
    """

    @staticmethod
    def enrich(df):
        """
        주어진 데이터프레임에 매매 신호 컬럼들(`long`, `short`, `exit_l`, `exit_s`)을 추가합니다.

        Args:
            df (pd.DataFrame): `ModelService`에서 `prob_up` 컬럼까지 추가된 데이터프레임.

        Returns:
            pd.DataFrame: 매매 신호 컬럼들이 추가된 데이터프레임.
        """
        # 원본 수정을 방지하기 위해 데이터프레임 복사
        df = df.copy()

        # --- 1. 규칙 기반 롱/숏 진입 조건 생성 ---

        # `rule_long`: 롱 포지션 진입을 위한 1차 규칙 필터
        df["rule_long"] = (
            (df["ema_fast"] > df["ema_slow"]) &  # 단기 EMA > 장기 EMA (상승 추세)
            (df["rsi"] < 40) &                  # RSI가 40 미만 (과매도 구간 근접, 반등 기대)
            (df["macd"] > df["macd_sig"])       # MACD선 > 시그널선 (상승 모멘텀)
        )

        # `rule_short`: 숏 포지션 진입을 위한 1차 규칙 필터
        df["rule_short"] = (
            (df["ema_fast"] < df["ema_slow"]) &  # 단기 EMA < 장기 EMA (하락 추세)
            (df["rsi"] > 60) &                  # RSI가 60 초과 (과매수 구간 근접, 조정 기대)
            (df["macd"] < df["macd_sig"])       # MACD선 < 시그널선 (하락 모멘텀)
        )

        # --- 2. ML 모델 예측을 결합한 최종 진입 신호 생성 ---

        # `long`: 최종 롱 포지션 진입 신호
        # `rule_long` 조건을 만족하고, 동시에 모델이 예측한 상승 확률이 `BUY_TH` 임계값보다 높아야 함.
        df["long"] = df["rule_long"] & (df["prob_up"] > CFG.BUY_TH)

        # `short`: 최종 숏 포지션 진입 신호
        # `rule_short` 조건을 만족하고, 동시에 모델이 예측한 상승 확률이 `SHORT_TH` 임계값보다 낮아야 함.
        df["short"] = df["rule_short"] & (df["prob_up"] < CFG.SHORT_TH)

        # --- 3. 포지션 청산 신호 생성 ---

        # `exit_l`: 롱 포지션 청산 신호 (여러 조건 중 하나만 만족해도 True)
        df["exit_l"] = (
            (df["prob_up"] < CFG.SELL_TH) |     # 모델 예측 상승 확률이 `SELL_TH` 임계값 미만으로 하락
            (df["rsi"] > 70) |                  # RSI가 70 초과 (과매수 상태 진입)
            (df["macd"] < df["macd_sig"])       # MACD선이 시그널선 아래로 하향 돌파 (상승 모멘텀 약화)
        )

        # `exit_s`: 숏 포지션 청산 신호 (여러 조건 중 하나만 만족해도 True)
        df["exit_s"] = (
            (df["prob_up"] > CFG.BUY_TH) |      # 모델 예측 상승 확률이 `BUY_TH` 임계값 초과로 상승
            (df["rsi"] < 30) |                  # RSI가 30 미만 (과매도 상태 진입)
            (df["macd"] > df["macd_sig"])       # MACD선이 시그널선 위로 상향 돌파 (하락 모멘텀 약화)
        )

        # NOTE: 잠재적 전략 개선점에 대한 설명
        # 현재 구조에서는 일부 진입/청산 조건이 서로 상충되거나 중복될 수 있습니다.
        # 예를 들어, 롱 포지션 진입 조건 중 하나인 `(df["macd"] > df["macd_sig"])`는
        # 숏 포지션 청산 조건(`exit_s`)에도 포함됩니다.
        # 반대로, 롱 포지션 청산 조건 중 하나인 `(df["macd"] < df["macd_sig"])`는
        # 숏 포지션 진입 조건(`rule_short`)에 포함됩니다.
        #
        # 이러한 중복은 다음과 같은 문제를 야기할 수 있습니다:
        # - Whipsaw (톱니 현상): 횡보장에서 작은 가격 변동에도 진입과 청산이 매우 짧은 시간 안에 반복되어
        #   거래 비용만 누적시킬 수 있습니다. 예를 들어, MACD가 시그널선을 살짝 넘어서 롱에 진입했다가,
        #   바로 다음 캔들에서 살짝 아래로 내려와서 청산되는 상황이 발생할 수 있습니다.
        #
        # 개선 방안:
        # - 진입 조건과 청산 조건의 민감도를 다르게 설정 (예: 진입은 더 엄격하게, 청산은 더 관대하게).
        # - 진입/청산 로직에 시간 지연(time delay)이나 연속적인 신호 확인(confirmation)과 같은 필터를 추가.
        # - 상태 머신(State Machine)을 도입하여 '진입 탐색', '포지션 보유', '청산 탐색' 등 상태에 따라
        #   다른 규칙을 적용하는 것을 고려해볼 수 있습니다.
        return df
