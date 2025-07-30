"""
Bybit USDT-Perpetual Futures 거래소 클라이언트 구현체.

이 모듈은 `ExchangeClient` 추상 클래스를 상속받아, 바이빗 USDT 무기한 선물 시장과의
실제 상호작용을 담당하는 구체적인 클래스 `BybitFutures`를 정의합니다.
`ccxt` 라이브러리를 사용하여 바이빗 API를 호출하는 로직이 포함됩니다.
"""
import logging
import ccxt
from src.exchange.exchange_client import ExchangeClient

class BybitFutures(ExchangeClient):
    """
    `ExchangeClient`의 바이빗 선물 거래소 전용 구현 클래스.

    `ccxt` 라이브러리의 바이빗 인스턴스를 내부적으로 사용하여,
    추상 메서드에서 정의된 기능들을 실제 API 호출로 연결합니다.
    """
    def __init__(self, key: str, secret: str):
        """
        BybitFutures 클라이언트 인스턴스를 초기화합니다.

        Args:
            key (str): 바이빗 API 키.
            secret (str): 바이빗 API 시크릿.
        """
        # ccxt 라이브러리를 사용하여 바이빗 거래소 객체를 생성합니다.
        self.client = ccxt.bybit({
            "apiKey": key,
            "secret": secret,
            "enableRateLimit": True,  # API 요청 속도 제한을 자동으로 준수하도록 설정합니다.
            "options": {
                "defaultType": "future"  # 모든 주문 및 API 호출의 기본 타입을 선물(future)로 지정합니다.
            }
        })
        # `fetch_time()`을 호출하여 API 서버와의 연결 및 인증 정보의 유효성을 테스트합니다.
        self.client.fetch_time()
        logging.info("Bybit Futures exchange client initialized successfully.")

    def set_leverage(self, symbol: str, leverage: int, isolated: bool):
        """
        지정된 심볼에 대한 레버리지 및 마진 모드를 설정합니다.
        바이빗 API는 ccxt를 통해 바이낸스와 동일한 방식으로 호출 가능합니다.
        """
        try:
            if isolated:
                self.client.set_margin_mode("ISOLATED", symbol)
            self.client.set_leverage(leverage, symbol)
            logging.info(f"[Bybit] Leverage for {symbol} set to {leverage}x.")
        except Exception as e:
            raise RuntimeError(f"Failed to set leverage on Bybit: {e}")

    def fetch_ohlcv(self, symbol: str, timeframe: str, since=None, limit: int = 500) -> list:
        """
        `ccxt`의 `fetch_ohlcv`를 직접 호출하여 OHLCV 데이터를 가져옵니다.
        """
        return self.client.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)

    def create_market_order(self, symbol: str, side: str, qty: float) -> dict:
        """
        `ccxt`의 `create_order`를 사용하여 시장가 주문을 생성합니다.
        """
        return self.client.create_order(symbol=symbol, type="MARKET", side=side.upper(), amount=qty)

    def create_exit_order(self, symbol: str, side: str, qty: float, stop_price: float, tp: bool = True) -> dict:
        """
        `ccxt`의 `create_order`를 사용하여 TP/SL 주문을 생성합니다.

        바이빗 API는 TP/SL 주문 시 `triggerDirection`이라는 추가 파라미터를 요구할 수 있습니다.
        이는 트리거 가격(stop_price)을 기준으로 현재가가 위에서 아래로 돌파할 때(fall) 발동할지,
        아래에서 위로 돌파할 때(rise) 발동할지를 지정합니다.
        - 1: Rise (가격이 트리거 가격 이상으로 상승 시)
        - 2: Fall (가격이 트리거 가격 이하로 하락 시)

        - TP 주문 (이익 실현):
          - 롱 포지션 종료(SELL): 현재가 > 진입가. `stop_price`가 현재가보다 높으므로, 가격이 상승하여 도달해야 함 -> Rise (1)
          - 숏 포지션 종료(BUY): 현재가 < 진입가. `stop_price`가 현재가보다 낮으므로, 가격이 하락하여 도달해야 함 -> Fall (2)
        - SL 주문 (손실 제한):
          - 롱 포지션 종료(SELL): 현재가 < 진입가. `stop_price`가 현재가보다 낮으므로, 가격이 하락하여 도달해야 함 -> Fall (2)
          - 숏 포지션 종료(BUY): 현재가 > 진입가. `stop_price`가 현재가보다 높으므로, 가격이 상승하여 도달해야 함 -> Rise (1)
        """
        order_type = "TAKE_PROFIT_MARKET" if tp else "STOP_MARKET"

        # 조건에 따른 triggerDirection 계산
        is_sell_order = side.upper() == "SELL"
        if (tp and is_sell_order) or (not tp and not is_sell_order):
            trigger_dir = 1  # Rise
        else:
            trigger_dir = 2  # Fall

        params = {
            "stopPrice": stop_price,
            "reduceOnly": True,
            "triggerDirection": trigger_dir  # Bybit에 특화된 파라미터
        }
        return self.client.create_order(
            symbol=symbol,
            type=order_type,
            side=side.upper(),
            amount=qty,
            params=params
        )

    def fetch_funding_rate(self, symbol: str) -> float:
        """
        현재 펀딩비를 조회합니다.
        ccxt의 Bybit 구현체는 `fetch_funding_rate` 메서드를 직접 지원하므로,
        암시적 API 호출 대신 이 메서드를 사용할 수 있습니다.
        (주: 원래 코드에서는 0.0을 반환했으나, 보다 정확한 구현으로 수정)
        """
        try:
            # ccxt의 통합된(unified) 메서드 사용
            rate_info = self.client.fetch_funding_rate(symbol)
            return float(rate_info.get("fundingRate", 0.0))
        except Exception:
            # API 호출 실패 시 0.0을 반환합니다.
            return 0.0

    def get_price_precision(self, symbol: str) -> int:
        """
        `ccxt`의 `market` 정보를 사용하여 가격 정밀도를 가져옵니다.
        """
        market = self.client.market(symbol)
        return int(market["precision"]["price"])

    def fetch_position(self, symbol: str) -> dict:
        """
        `ccxt`의 `fetch_positions`를 사용하여 현재 포지션 정보를 가져옵니다.
        """
        positions = self.client.fetch_positions([symbol])
        for p in positions:
            if p.get("symbol") == symbol and p.get("contracts", 0) > 0:
                return p
        return {}
