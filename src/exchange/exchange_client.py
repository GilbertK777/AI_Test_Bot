"""
거래소 클라이언트 추상 클래스 (Abstract Base Class).

이 모듈은 `BinanceFutures`와 `BybitFutures` 같은 구체적인 거래소 클라이언트 클래스들이
반드시 구현해야 하는 공통 인터페이스를 정의합니다.
파이썬의 `abc` (Abstract Base Classes) 모듈을 사용하여 추상 클래스를 만듭니다.

추상 클래스를 사용하는 이유:
1. 일관성 있는 API: 모든 거래소 클래스가 동일한 메서드 이름과 파라미터를 갖도록 강제하여,
   봇의 다른 부분(예: OrderService, IndicatorRepository)에서 거래소 종류에 상관없이
   동일한 방식으로 객체를 사용할 수 있게 합니다. (다형성, Polymorphism)
2. 확장성: 새로운 거래소(예: Bitget, OKX)를 추가하고 싶을 때, 이 `ExchangeClient`를 상속받아
   필수 메서드들을 구현하기만 하면 되므로 시스템 확장이 용이합니다.
3. 명확한 설계: 이 클래스 자체만 봐도 거래소 연동에 필요한 기능들이 무엇인지 명확하게 알 수 있습니다.
"""
import abc

class ExchangeClient(abc.ABC):
    """
    모든 거래소 클라이언트가 상속받아야 하는 추상 기본 클래스 (C#의 Interface와 유사).

    `@abc.abstractmethod` 데코레이터가 붙은 메서드는 자식 클래스에서 반드시 재정의(override)해야 합니다.
    만약 재정의하지 않고 자식 클래스의 인스턴스를 생성하려고 하면 `TypeError`가 발생합니다.
    """

    @abc.abstractmethod
    def fetch_ohlcv(self, symbol: str, timeframe: str, since=None, limit: int = 500) -> list:
        """
        지정된 심볼과 타임프레임의 OHLCV(시가, 고가, 저가, 종가, 거래량) 데이터를 가져옵니다.

        Args:
            symbol (str): 거래 페어 (예: 'BTC/USDT').
            timeframe (str): 캔들 봉의 시간 간격 (예: '15m', '1h', '4h').
            since (int, optional): 데이터를 가져오기 시작할 타임스탬프 (ms 단위). Defaults to None.
            limit (int, optional): 가져올 캔들 봉의 최대 개수. Defaults to 500.

        Returns:
            list: ccxt에서 반환하는 OHLCV 데이터 리스트. 각 요소는 [timestamp, open, high, low, close, volume] 형식의 리스트입니다.
        """
        ...

    @abc.abstractmethod
    def create_market_order(self, symbol: str, side: str, qty: float) -> dict:
        """
        시장가 주문(Market Order)을 생성합니다.

        Args:
            symbol (str): 주문할 거래 페어.
            side (str): 주문 방향 ('buy' 또는 'sell').
            qty (float): 주문 수량.

        Returns:
            dict: ccxt에서 반환하는 주문 결과 딕셔너리.
        """
        ...

    @abc.abstractmethod
    def set_leverage(self, symbol: str, leverage: int, isolated: bool) -> None:
        """
        지정된 심볼에 대한 레버리지 및 마진 모드를 설정합니다.

        Args:
            symbol (str): 설정할 거래 페어.
            leverage (int): 설정할 레버리지 배율.
            isolated (bool): 격리(True) 또는 교차(False) 마진 모드 설정.
        """
        ...

    @abc.abstractmethod
    def create_exit_order(self, symbol: str, side: str, qty: float, stop_price: float, tp: bool = True) -> dict:
        """
        포지션 종료를 위한 TP(Take-Profit) 또는 SL(Stop-Loss) 주문을 생성합니다.
        이러한 주문은 특정 가격(stop_price)에 도달했을 때 발동되는 조건부 주문입니다.

        Args:
            symbol (str): 주문할 거래 페어.
            side (str): 주문 방향 ('buy' 또는 'sell'). 롱 포지션 종료는 'sell', 숏 포지션 종료는 'buy'가 됩니다.
            qty (float): 주문 수량.
            stop_price (float): 주문이 발동될 트리거 가격.
            tp (bool, optional): True이면 이익 실현(Take-Profit) 주문, False이면 손절(Stop-Loss) 주문. Defaults to True.

        Returns:
            dict: ccxt에서 반환하는 주문 결과 딕셔너리.
        """
        ...

    @abc.abstractmethod
    def fetch_funding_rate(self, symbol: str) -> float:
        """
        현재 펀딩비를 조회합니다. 펀딩비는 롱/숏 포지션 간에 주기적으로 교환되는 수수료입니다.

        Args:
            symbol (str): 조회할 거래 페어.

        Returns:
            float: 현재 펀딩비. API에서 조회가 불가능하거나 실패할 경우 0.0을 반환할 수 있습니다.
        """
        ...

    @abc.abstractmethod
    def get_price_precision(self, symbol: str) -> int:
        """
        지정된 심볼의 가격 정밀도(소수점 이하 자릿수)를 가져옵니다.
        주문 가격을 거래소에서 허용하는 형식으로 맞추기 위해 필요합니다.

        Args:
            symbol (str): 조회할 거래 페어.

        Returns:
            int: 가격의 소수점 이하 자릿수.
        """
        ...

    @abc.abstractmethod
    def fetch_position(self, symbol: str) -> dict:
        """
        현재 보유 중인 포지션 정보를 조회합니다.

        Args:
            symbol (str): 조회할 거래 페어.

        Returns:
            dict: ccxt에서 반환하는 포지션 정보 딕셔너리. 포지션이 없으면 빈 딕셔너리 {}를 반환합니다.
        """
        ...
