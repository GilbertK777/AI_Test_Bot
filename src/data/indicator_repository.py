"""
멀티‑타임프레임 OHLCV + 지표 병합 Repository
"""
import logging, ccxt
import pandas as pd
from config.config import CFG
from src.utils.helpers import add_indicators
from src.exchange.exchange_client import ExchangeClient

class IndicatorRepository:
    """15m / 1h / 4h 데이터 병합 제공"""

    def __init__(self, exchange: ExchangeClient, symbol: str):
        self.exchange = exchange
        self.symbol   = symbol

    def _fetch_cache(self, tf: str, limit: int = 500) -> pd.DataFrame:
        from pathlib import Path
        fp = CFG.DATA_DIR / f"{self.symbol.replace('/', '_')}_{tf}.parquet"
        cached = pd.read_parquet(fp) if fp.exists() else pd.DataFrame()
        since  = int(cached.index[-2].value / 1e6) if len(cached) > 2 else None
        try:
            need = 2 if since else limit
            rows = self.exchange.fetch_ohlcv(self.symbol, tf,
                                             since=since, limit=need)
            df_new = pd.DataFrame(rows, columns=["ts", "open", "high", "low",
                                                 "close", "volume"])
            df_new["ts"] = pd.to_datetime(df_new["ts"], unit="ms")
            df_new.set_index("ts", inplace=True)
            full = pd.concat([cached, df_new]).drop_duplicates(keep="last")
            full.to_parquet(fp)
            return full.tail(limit)
        except ccxt.NetworkError as e:
            logging.warning(f"{tf} 네트워크 오류: {e}")
            return cached.tail(limit)
        except Exception as e:
            logging.error(f"{tf} fetch 실패: {e}")
            return cached.tail(limit)

    def get_merged(self) -> pd.DataFrame:
        """15m 기준 + 상위 TF 지표 결합"""
        df15 = add_indicators(self._fetch_cache("15m"))
        df1h = add_indicators(self._fetch_cache("1h")).resample("15T").ffill()
        df4h = add_indicators(self._fetch_cache("4h")).resample("15T").ffill()
        if df15.empty or df1h.empty or df4h.empty:
            raise ValueError("타임프레임 데이터 부족")
        base = df15.copy()
        base["rsi_1h"]      = df1h["rsi"]
        base["ema_fast_4h"] = df4h["ema_fast"]
        base["ema_slow_4h"] = df4h["ema_slow"]
        base["target"]      = (base["close"].shift(-1) > base["close"]).astype(int)
        return base.dropna()
