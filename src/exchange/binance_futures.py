"""
Binance USD-M Futures 거래소 클라이언트 구현체.

이 모듈은 `ExchangeClient` 추상 클래스를 상속받아, 바이낸스 선물 시장(USD-M Futures)과의
실제 상호작용을 담당하는 구체적인 클래스 `BinanceFutures`를 정의합니다.
`ccxt` 라이브러리를 사용하여 바이낸스 API를 호출하는 로직이 포함됩니다.
"""
import logging
import ccxt
from src.exchange.exchange_client import ExchangeClient

class BinanceFutures(ExchangeClient):
    """
    `ExchangeClient`의 바이낸스 선물 거래소 전용 구현 클래스.

    `ccxt` 라이브러리의 바이낸스 인스턴스를 내부적으로 사용하여,
    추상 메서드에서 정의된 기능들을 실제 API 호출로 연결합니다.
    """
    def __init__(self, key: str, secret: str):
        """
        BinanceFutures 클라이언트 인스턴스를 초기화합니다.

        Args:
            key (str): 바이낸스 API 키.
            secret (str): 바이낸스 API 시크릿.
        """
        # ccxt 라이브러리를 사용하여 바이낸스 거래소 객체를 생성합니다.
        self.client = ccxt.binance({
            "apiKey": key,
            "secret": secret,
            "enableRateLimit": True,  # API 요청 속도 제한을 자동으로 준수하도록 설정합니다.
            "options": {
                "defaultType": "future"  # 모든 주문 및 API 호출의 기본 타입을 선물(future)로 지정합니다.
            }
        })
        # `fetch_time()`을 호출하여 API 서버와의 연결 및 인증 정보의 유효성을 테스트합니다.
        # 성공적으로 완료되면, API 키와 시크릿이 올바르다는 것을 의미합니다.
        self.client.fetch_time()
        logging.info("Binance Futures exchange client initialized successfully.")

    def set_leverage(self, symbol: str, leverage: int, isolated: bool):
        """
        지정된 심볼에 대한 레버리지 및 마진 모드를 설정합니다.

        바이낸스 API는 마진 모드 설정과 레버리지 설정을 별도로 호출해야 합니다.
        """
        try:
            # `isolated`가 True일 경우, 마진 모드를 'ISOLATED'(격리)로 설정합니다.
            if isolated:
                # `set_margin_mode`는 ccxt의 통합되지 않은(implicit) API 호출 방식입니다.
                self.client.set_margin_mode("ISOLATED", symbol)
            # `set_leverage`를 호출하여 레버리지 배율을 설정합니다.
            self.client.set_leverage(leverage, symbol)
            logging.info(f"[Binance] Leverage for {symbol} set to {leverage}x.")
        except Exception as e:
            # API 호출 중 오류(예: 잘못된 심볼, 권한 문제) 발생 시 런타임 에러를 발생시킵니다.
            raise RuntimeError(f"Failed to set leverage on Binance: {e}")

    def fetch_ohlcv(self, symbol: str, timeframe: str, since=None, limit: int = 500) -> list:
        """
        `ccxt`의 `fetch_ohlcv`를 직접 호출하여 OHLCV 데이터를 가져옵니다.
        """
        return self.client.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)

    def create_market_order(self, symbol: str, side: str, qty: float) -> dict:
        """
        `ccxt`의 `create_order`를 사용하여 시장가 주문을 생성합니다.
        """
        # `side` 파라미터를 대문자로 변환합니다 (예: 'buy' -> 'BUY').
        side = side.upper()
        return self.client.create_order(symbol=symbol, type="MARKET", side=side, amount=qty)

    def create_exit_order(self, symbol: str, side: str, qty: float, stop_price: float, tp: bool = True) -> dict:
        """
        `ccxt`의 `create_order`를 사용하여 TP/SL 주문을 생성합니다.

        바이낸스 선물 API에서는 `TAKE_PROFIT_MARKET`과 `STOP_MARKET` 주문 유형을 사용하며,
        `stopPrice` 파라미터로 트리거 가격을 지정합니다.
        `reduceOnly=True`는 이 주문이 포지션을 줄이는 방향으로만 작동하도록 보장합니다.
        `closePosition=True`는 바이낸스 전용 파라미터로, 포지션 전체를 종료하는 주문을 나타냅니다.
        """
        # `tp` 플래그에 따라 주문 유형을 결정합니다.
        order_type = "TAKE_PROFIT_MARKET" if tp else "STOP_MARKET"
        return self.client.create_order(
            symbol=symbol,
            type=order_type,
            side=side.upper(),
            amount=qty,
            params={
                "stopPrice": stop_price,    # 주문이 발동될 가격
                "reduceOnly": True,         # 포지션 감소만 허용
                "closePosition": True       # 포지션 전체 청산 (바이낸스 선물 전용)
            }
        )

    def fetch_funding_rate(self, symbol: str) -> float:
        """
        `ccxt`의 암시적 API 호출을 사용하여 현재 펀딩비를 조회합니다.

        `fapiPublicGetPremiumIndex`는 `ccxt`가 내부적으로 `fapi/v1/premiumIndex` GET 요청으로 변환합니다.
        심볼 형식은 API 요구사항에 맞게 '/'를 제거해야 합니다 (예: 'BTC/USDT' -> 'BTCUSDT').
        """
        try:
            # 심볼 형식 변환
            symbol_no_slash = symbol.replace("/", "")
            # 암시적 API 호출
            res = self.client.fapiPublicGetPremiumIndex({"symbol": symbol_no_slash})
            # 결과에서 `lastFundingRate` 값을 float으로 변환하여 반환합니다.
            return float(res["lastFundingRate"])
        except Exception:
            # API 호출 실패 시 0.0을 반환합니다.
            return 0.0

    def get_price_precision(self, symbol: str) -> int:
        """
        `ccxt`의 `market` 정보를 사용하여 가격 정밀도를 가져옵니다.
        """
        market = self.client.market(symbol)
        # `market` 객체의 `precision` 딕셔너리에서 'price' 키의 값을 정수로 변환하여 반환합니다.
        return int(market["precision"]["price"])

    def fetch_position(self, symbol: str) -> dict:
        """
        `ccxt`의 `fetch_positions`를 사용하여 현재 포지션 정보를 가져옵니다.

        `fetch_positions`는 모든 포지션 목록을 반환하므로,
        지정된 심볼과 일치하고 실제 계약 수량이 0보다 큰 포지션만 필터링하여 반환합니다.
        """
        # 특정 심볼에 대한 포지션만 조회합니다.
        positions = self.client.fetch_positions([symbol])
        # 반환된 포지션 목록을 순회합니다.
        for p in positions:
            # 심볼이 일치하고, 'contracts' (계약 수량)가 0보다 큰 경우에만 해당 포지션 정보를 반환합니다.
            if p.get("symbol") == symbol and p.get("contracts", 0) > 0:
                return p
        # 일치하는 포지션이 없으면 빈 딕셔너리를 반환합니다.
        return {}
