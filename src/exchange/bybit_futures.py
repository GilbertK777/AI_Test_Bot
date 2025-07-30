"""
Bybit USDT‑Perpetual Futures 구현 (ExchangeClient 상속)
"""
import logging, ccxt
from config.config import CFG
from src.exchange.exchange_client import ExchangeClient

class BybitFutures(ExchangeClient):
    """Bybit 선물 전용 구현"""
    def __init__(self, key: str, secret: str):
        self.client = ccxt.bybit({
            "apiKey": key,
            "secret": secret,
            "enableRateLimit": True,
            "options": {"defaultType": "future"}
        })
        self.client.fetch_time()
        logging.info("Bybit 연결 OK")

    def set_leverage(self, symbol, leverage, isolated):
        try:
            if isolated:
                self.client.set_margin_mode("ISOLATED", symbol)
            self.client.set_leverage(leverage, symbol)
            logging.info(f"[Bybit] 레버리지 {leverage}x 설정 완료")
        except Exception as e:
            raise RuntimeError(f"Bybit 레버리지 설정 실패: {e}")

    def fetch_ohlcv(self, symbol, timeframe, since=None, limit=500):
        return self.client.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)

    def create_market_order(self, symbol, side, qty):
        return self.client.create_order(symbol=symbol, type="MARKET",
                                        side=side.upper(), amount=qty)

    def create_exit_order(self, symbol, side, qty, stop_price, tp=True):
        order_type = "TAKE_PROFIT_MARKET" if tp else "STOP_MARKET"
        trigger_dir = 1 if ((tp and side.upper()=="SELL") or
                            (not tp and side.upper()=="BUY")) else 2
        params = {"stopPrice": stop_price,
                  "reduceOnly": True,
                  "triggerDirection": trigger_dir}
        return self.client.create_order(symbol=symbol, type=order_type,
                                        side=side.upper(), amount=qty,
                                        params=params)

    def fetch_funding_rate(self, symbol):
        # Bybit 펀딩률 API는 별도; 여기선 0.0
        return 0.0

    def get_price_precision(self, symbol: str) -> int:
        market = self.client.market(symbol)
        return int(market["precision"]["price"])

    def fetch_position(self, symbol: str) -> dict:
        positions = self.client.fetch_positions([symbol])
        for p in positions:
            if p.get("symbol") == symbol and p.get("contracts", 0) > 0:
                return p
        return {}

    def cancel_all_orders(self, symbol: str):
        # Bybit 선물에서는 symbol 파라미터 필수
        return self.client.cancel_all_orders(symbol)
