"""
ExchangeClient 추상 클래스 – Binance/Bybit 구현 공통 인터페이스
"""
import abc

class ExchangeClient(abc.ABC):
    """C# Interface 같은 추상 클래스"""

    @abc.abstractmethod
    def fetch_ohlcv(self, symbol: str, timeframe: str, since=None, limit=500):
        ...

    @abc.abstractmethod
    def create_market_order(self, symbol: str, side: str, qty: float):
        ...

    @abc.abstractmethod
    def set_leverage(self, symbol: str, leverage: int, isolated: bool):
        ...

    @abc.abstractmethod
    def create_exit_order(self, symbol: str, side: str, qty: float,
                          stop_price: float, tp: bool = True):
        ...

    @abc.abstractmethod
    def fetch_funding_rate(self, symbol: str) -> float:
        ...
