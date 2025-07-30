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

def setup_exchange():
    """거래소 클라이언트 객체를 생성 및 반환"""
    if CFG.EXCHANGE_NAME == "BYBIT":
        exchange = BybitFutures(CFG.API_KEY, CFG.API_SECRET)
    else:
        exchange = BinanceFutures(CFG.API_KEY, CFG.API_SECRET)
    return exchange

def setup_services(exchange):
    """데이터, 모델, 주문 서비스 객체를 생성 및 반환"""
    repo = IndicatorRepository(exchange, CFG.SYMBOL)
    model = ModelService(CFG.MODEL_FP)
    order = OrderService(exchange, paper=CFG.TEST_MODE, init_balance=CFG.INIT_BAL)
    return repo, model, order

def start_bot_and_dashboard(repo, model, order):
    """봇을 생성하고 루프 및 대시보드를 실행"""
    bot = TradingBot(repo, model, order)
    threading.Thread(target=bot.loop, daemon=True).start()
    run_dashboard(bot)

def main():
    # ── 1) 거래소 선택 ──
    exchange = setup_exchange()

    # ── 2) 서비스 객체 생성 ──
    repo, model, order = setup_services(exchange)

    # ── 3) 봇 루프 & UI 실행 ──
    start_bot_and_dashboard(repo, model, order)

if __name__ == "__main__":
    main()
