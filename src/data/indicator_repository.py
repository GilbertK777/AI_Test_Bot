"""
멀티-타임프레임(Multi-Timeframe) OHLCV 데이터 및 기술적 지표를 관리하는 리포지토리.

이 클래스는 트레이딩 전략에 필요한 데이터를 준비하는 핵심적인 역할을 수행합니다.
주요 기능은 다음과 같습니다:
1. 여러 타임프레임(예: 15분, 1시간, 4시간)의 OHLCV 데이터를 거래소로부터 조회합니다.
2. 조회한 데이터를 Parquet 파일 형식으로 로컬에 캐싱(caching)하여, 다음 조회 시 API 요청을 최소화하고 속도를 향상시킵니다.
3. 각 타임프레임 데이터에 기술적 지표(EMA, RSI 등)를 추가합니다.
4. 상위 타임프레임(1h, 4h)의 데이터를 기준 타임프레임(15m)에 맞게 리샘플링(resampling)합니다.
5. 모든 데이터를 병합하여 최종적으로 모델 학습 및 예측에 사용될 통합 데이터프레임을 생성합니다.
"""
import logging
import ccxt
import pandas as pd
from config.config import CFG
from src.utils.helpers import add_indicators
from src.exchange.exchange_client import ExchangeClient

class IndicatorRepository:
    """
    15분, 1시간, 4시간 봉 데이터를 조회, 캐싱, 병합하여 제공하는 클래스.
    """

    def __init__(self, exchange: ExchangeClient, symbol: str):
        """
        IndicatorRepository 인스턴스를 초기화합니다.

        Args:
            exchange (ExchangeClient): 거래소와의 통신을 담당하는 클라이언트 객체.
            symbol (str): 조회할 거래 페어 심볼 (예: 'BTC/USDT').
        """
        self.exchange = exchange
        self.symbol = symbol

    def _fetch_cache(self, tf: str, limit: int = 500) -> pd.DataFrame:
        """
        지정된 타임프레임의 데이터를 조회하고 로컬에 캐싱하는 내부 메서드.

        1. 로컬 캐시(Parquet 파일)가 있는지 확인하고, 있다면 불러옵니다.
        2. 캐시된 데이터의 마지막 시간부터 현재까지의 최신 데이터를 거래소에 요청합니다.
           - 캐시가 없는 경우, `limit` 개수만큼의 과거 데이터를 요청합니다.
           - 캐시가 있는 경우, 중복을 피하기 위해 마지막 2개 봉부터 요청하여 최신 데이터를 보충합니다.
        3. 새로 받은 데이터와 기존 캐시 데이터를 합치고, 중복을 제거한 후 다시 Parquet 파일로 저장합니다.
        4. 최종적으로 `limit` 개수만큼의 최신 데이터를 데이터프레임으로 반환합니다.

        네트워크 오류 등 예외 발생 시, API 요청은 실패하지만 프로그램이 중단되지 않고
        현재까지 캐시된 데이터만이라도 반환하여 안정성을 높입니다.

        Args:
            tf (str): 조회할 타임프레임 (예: '15m', '1h').
            limit (int): 반환할 데이터의 최대 행 수 (최신 데이터 기준).

        Returns:
            pd.DataFrame: 요청된 타임프레임의 OHLCV 데이터프레임.
        """
        from pathlib import Path
        # 심볼과 타임프레임을 조합하여 캐시 파일 경로를 생성합니다. (예: data/BTC_USDT_15m.parquet)
        fp = CFG.DATA_DIR / f"{self.symbol.replace('/', '_')}_{tf}.parquet"

        # 파일이 존재하면 읽어오고, 없으면 빈 데이터프레임을 생성합니다.
        cached = pd.read_parquet(fp) if fp.exists() else pd.DataFrame()

        # 캐시된 데이터가 2개 이상 있을 경우, 마지막에서 두 번째 봉의 타임스탬프를 `since`로 설정합니다.
        # 이렇게 하면 마지막 봉이 미완성 상태일 경우에도 누락 없이 데이터를 이어받을 수 있습니다.
        since = int(cached.index[-2].value / 1e6) if len(cached) > 2 else None

        try:
            # `since` 값이 있으면 최신 2개 봉만, 없으면(최초 조회) `limit` 개수만큼 요청합니다.
            need = 2 if since else limit
            # 거래소 클라이언트를 통해 OHLCV 데이터를 조회합니다.
            rows = self.exchange.fetch_ohlcv(self.symbol, tf, since=since, limit=need)

            # ccxt가 반환한 리스트를 pandas 데이터프레임으로 변환합니다.
            df_new = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
            # 타임스탬프(ms)를 datetime 객체로 변환하고 인덱스로 설정합니다.
            df_new["ts"] = pd.to_datetime(df_new["ts"], unit="ms")
            df_new.set_index("ts", inplace=True)

            # 기존 캐시 데이터와 새로 받은 데이터를 합칩니다.
            full = pd.concat([cached, df_new])
            # 인덱스(시간) 기준으로 중복된 데이터를 제거하되, 마지막 값(최신 데이터)을 유지합니다.
            full = full.drop_duplicates(keep="last")

            # 업데이트된 전체 데이터를 다시 Parquet 파일로 저장하여 캐시를 갱신합니다.
            full.to_parquet(fp)

            # 최종적으로 최신 `limit` 개수의 데이터만 잘라서 반환합니다.
            return full.tail(limit)
        except ccxt.NetworkError as e:
            logging.warning(f"Network error while fetching {tf} data: {e}. Returning cached data.")
            return cached.tail(limit)
        except Exception as e:
            logging.error(f"Failed to fetch {tf} data: {e}. Returning cached data.")
            return cached.tail(limit)

    def get_merged(self) -> pd.DataFrame:
        """
        모든 타임프레임의 데이터를 조회, 처리, 병합하여 최종 피처(feature) 데이터프레임을 생성합니다.

        1. `_fetch_cache`를 사용하여 15분, 1시간, 4시간 봉 데이터를 각각 가져옵니다.
        2. 각 데이터프레임에 `add_indicators` 헬퍼 함수를 사용하여 기술적 지표를 추가합니다.
        3. 1시간과 4시간 데이터를 15분 간격으로 리샘플링합니다. `ffill()`(forward-fill)을 사용하여
           상위 타임프레임의 값이 해당 시간 동안 유지되도록 채웁니다.
           (예: 1시의 1h RSI 값은 1:00, 1:15, 1:30, 1:45에 모두 동일하게 적용됨)
        4. 15분 데이터를 기준으로, 리샘플링된 상위 타임프레임의 특정 지표들을 컬럼으로 추가합니다.
        5. 머신러닝 모델의 정답(label)으로 사용될 'target' 컬럼을 생성합니다.
           (다음 15분 봉의 종가가 현재 종가보다 높으면 1, 아니면 0)
        6. 결측치(NaN)가 있는 행을 모두 제거하고 최종 데이터프레임을 반환합니다.

        Returns:
            pd.DataFrame: 멀티-타임프레임 지표가 모두 병합된 최종 데이터프레임.
        """
        # 1. 각 타임프레임 데이터 조회 및 지표 추가
        df15 = add_indicators(self._fetch_cache("15m"))

        # 2. 상위 타임프레임 데이터 조회, 지표 추가, 리샘플링
        df1h = add_indicators(self._fetch_cache("1h")).resample("15T").ffill()
        df4h = add_indicators(self._fetch_cache("4h")).resample("15T").ffill()

        # 데이터가 하나라도 비어있으면 오류를 발생시켜 시스템 중단을 방지합니다.
        if df15.empty or df1h.empty or df4h.empty:
            raise ValueError("Failed to fetch sufficient data for one or more timeframes.")

        # 3. 데이터 병합
        base = df15.copy()
        # 15분봉 데이터에 1시간봉의 RSI와 4시간봉의 EMA 값들을 새로운 컬럼으로 추가합니다.
        base["rsi_1h"] = df1h["rsi"]
        base["ema_fast_4h"] = df4h["ema_fast"]
        base["ema_slow_4h"] = df4h["ema_slow"]

        # 4. 타겟(정답) 변수 생성
        # `shift(-1)`은 다음 행의 값을 현재 행으로 가져옵니다.
        # 즉, 다음 15분 봉의 종가가 현재 종가보다 높은지를 비교하여 target 값을 결정합니다.
        base["target"] = (base["close"].shift(-1) > base["close"]).astype(int)

        # 5. 결측치 제거 후 반환
        # 리샘플링이나 지표 추가 과정에서 발생할 수 있는 모든 결측치를 제거하여 모델 학습에 문제가 없도록 합니다.
        return base.dropna()
