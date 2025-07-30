"""
TradingBot: Repository + Model + Strategy + OrderService orchestrator
"""
import time, threading, logging
from datetime import datetime
from config.config import CFG
from src.utils.helpers import tg
from src.strategy.strategy import Strategy
from src.order.order_service import OrderService
from src.model.model_service import ModelService
from src.data.indicator_repository import IndicatorRepository

class TradingBot:
    """메인 트레이딩 루프 관리"""

    def __init__(self, repo: IndicatorRepository,
                 model: ModelService,
                 order: OrderService):
        self.repo, self.model, self.order = repo, model, order
        self.df_latest = None; self.lock = threading.Lock()

    def loop(self):
        while True:
            try:
                if self.order.is_paused(): time.sleep(CFG.SLEEP_SEC); continue
                df = self.repo.get_merged()
                need_train = (self.model.model is None or
                              (datetime.utcnow()-self.model.t_last_train).seconds >
                              CFG.RETRAIN_HR*3600)
                if need_train: self.model.train(df)
                df = self.model.add_prob(df)
                df = Strategy.enrich(df)
                with self.lock: self.df_latest = df.tail(500).copy()
                last = df.iloc[-1]

                if self.order.pos is None:
                    if last["long"] or last["short"]:
                        qty = (CFG.MARGIN_PER_TRADE*CFG.LEVERAGE)/max(last["close"],1e-6) \
                              if CFG.MARGIN_PER_TRADE>0 else CFG.POS_SIZE/max(last["atr"],1e-6)
                        qty = min(qty, CFG.MAX_QTY)
                        if last["long"]:  self.order.open_position(last["close"], qty, "long")
                        if last["short"]: self.order.open_position(last["close"], qty, "short")
                else:
                    self.order.poll_position_closed(last["close"])
                time.sleep(CFG.SLEEP_SEC)
            except Exception as e:
                logging.error(f"루프 오류: {e}"); tg(f"⚠️ 루프 오류: {e}"); time.sleep(30)

    def get_df(self):
        with self.lock:
            return self.df_latest.copy() if self.df_latest is not None else None
