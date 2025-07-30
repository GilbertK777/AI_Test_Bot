"""
프로그램 진입점 – 환경설정에 따라 거래소 선택 후 봇+대시보드 실행
"""
import threading
from config.config import CFG
from src.exchange.binance_futures import BinanceFutures
from src.exchange.bybit_futures import BybitFutures
from src.data.indicator_repository import IndicatorRepository
from src.model.model_service import ModelService
from src.order.order_service import OrderService
from src.bot.trading_bot import TradingBot
from src.ui.dashboard import run_dashboard

def main():
    # ── 1) 거래소 선택 (ENV: EXCHANGE) ──
    if CFG.EXCHANGE_NAME == "BYBIT":
        exchange = BybitFutures(CFG.API_KEY, CFG.API_SECRET)
    else:
        exchange = BinanceFutures(CFG.API_KEY, CFG.API_SECRET)

    # ── 2) 서비스 객체 생성 ──
    repo  = IndicatorRepository(exchange, CFG.SYMBOL)
    model = ModelService(CFG.MODEL_FP)
    order = OrderService(exchange, paper=CFG.TEST_MODE, init_balance=CFG.INIT_BAL)

    # ── 3) 봇 루프 & UI 실행 ──
    bot = TradingBot(repo, model, order)
    threading.Thread(target=bot.loop, daemon=True).start()
    run_dashboard(bot)

if __name__ == "__main__":
    main()
