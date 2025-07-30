"""
Binance USD‑M Futures 구현 (ExchangeClient 상속)
"""
import logging, ccxt
from config.config import CFG
from src.exchange.exchange_client import ExchangeClient

class BinanceFutures(ExchangeClient):
    """Binance 선물 전용 구현"""
    def __init__(self, key: str, secret: str):
        self.client = ccxt.binance({
            "apiKey": key,
            "secret": secret,
            "enableRateLimit": True,
            "options": {"defaultType": "future"}
        })
        self.client.fetch_time()
        logging.info("Binance 연결 OK")

    # 이하 메서드는 단일 파일에서 사용한 구현 그대로 이동
    def set_leverage(self, symbol, leverage, isolated):
        try:
            if isolated:
                self.client.set_margin_mode("ISOLATED", symbol)
            self.client.set_leverage(leverage, symbol)
            logging.info(f"[Binance] 레버리지 {leverage}x 설정 완료")
        except Exception as e:
            raise RuntimeError(f"Binance 레버리지 설정 실패: {e}")

    def fetch_ohlcv(self, symbol, timeframe, since=None, limit=500):
        return self.client.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)

    def create_market_order(self, symbol, side, qty):
        side = side.upper()
        return self.client.create_order(symbol=symbol, type="MARKET",
                                        side=side, amount=qty)

    def create_exit_order(self, symbol, side, qty, stop_price, tp=True):
        order_type = "TAKE_PROFIT_MARKET" if tp else "STOP_MARKET"
        return self.client.create_order(
            symbol=symbol, type=order_type, side=side.upper(),
            amount=qty,
            params={"stopPrice": stop_price,
                    "reduceOnly": True, "closePosition": True}
        )

    def fetch_funding_rate(self, symbol):
        try:
            res = self.client.fapiPublicGetPremiumIndex({"symbol": symbol.replace("/", "")})
            return float(res["lastFundingRate"])
        except Exception:
            return 0.0
