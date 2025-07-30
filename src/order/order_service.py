"""
포지션·주문 관리 서비스 (Paper / Live 공통)
"""
import logging, threading
from datetime import datetime, timedelta
from config.config import CFG
from src.utils.helpers import tg
from src.exchange.exchange_client import ExchangeClient

class OrderService:
    """포지션 관리 + TP/SL 주문 부착"""

    def __init__(self, ex: ExchangeClient, paper=True, init_balance=0.0):
        self.ex = ex; self.paper = paper
        self.balance = init_balance
        self.pos, self.trades = None, []
        self.loss_cnt, self.pause_until = 0, None
        self.lock = threading.Lock()
        if not paper:
            self.ex.set_leverage(CFG.SYMBOL, CFG.LEVERAGE, CFG.ISOLATED)

    # ── 내부 유틸: PnL, TP/SL 부착, Pause 관리 (원본 주석 그대로) ──
    def _pnl(self, exit_px):
        if not self.pos: return 0.0
        entry, qty, side = self.pos["entry"], self.pos["qty"], self.pos["side"]
        delta = (exit_px - entry) if side=="long" else (entry - exit_px)
        fee = abs(exit_px * qty) * CFG.TRADE_FEE
        funding = abs(entry * qty) * self.ex.fetch_funding_rate(CFG.SYMBOL)
        return delta * qty * CFG.LEVERAGE - fee - funding

    def _attach_tp_sl(self, side, entry_px, qty):
        tp_px = entry_px*(1+CFG.TP_PCT) if side=="long" else entry_px*(1-CFG.TP_PCT)
        sl_px = entry_px*(1-CFG.SL_PCT) if side=="long" else entry_px*(1+CFG.SL_PCT)
        if self.paper:
            logging.info(f"[PAPER] TP/SL {tp_px:.2f}/{sl_px:.2f}")
            return
        try:
            # BUGFIX: 가격을 거래소의 정밀도(precision)에 맞게 변환해야 함
            tp_px_r = self.ex.client.price_to_precision(CFG.SYMBOL, tp_px)
            sl_px_r = self.ex.client.price_to_precision(CFG.SYMBOL, sl_px)
            exit_side = "SELL" if side=="long" else "BUY"
            self.ex.create_exit_order(CFG.SYMBOL, exit_side, qty, tp_px_r, tp=True)
            self.ex.create_exit_order(CFG.SYMBOL, exit_side, qty, sl_px_r, tp=False)
        except Exception as e:
            logging.error(f"TP/SL attach 실패: {e}"); tg(f"⚠️ TP/SL attach 실패: {e}")

    def open_position(self, px, qty, side):
        with self.lock:
            if self.pos: return
            entry_px = px*(1+CFG.SLIP_PCT) if side=="long" else px*(1-CFG.SLIP_PCT)
            if not self.paper:
                try:
                    order = self.ex.create_market_order(CFG.SYMBOL,
                                                        "buy" if side=="long" else "sell",
                                                        qty)
                    entry_px = float(order.get("price", entry_px))
                except Exception as e:
                    logging.error(f"{side} 주문 실패: {e}"); tg(f"⚠️ {side} 주문 실패: {e}"); return
            self.pos = {"entry": entry_px, "qty": qty, "side": side}
            self.trades.append({"time": datetime.utcnow(), "side": side.upper(),
                                "price": entry_px, "bal": self.balance})
            tg(f"🚀 {'[PAPER]' if self.paper else '[LIVE]'} {side.upper()} 진입 @ {entry_px:.2f}")
            self._attach_tp_sl(side, entry_px, qty)

    def poll_position_closed(self, px_now):
        with self.lock:
            if not self.pos or not self.paper: return
            entry, qty, side = self.pos["entry"], self.pos["qty"], self.pos["side"]
            hit_tp = (px_now >= entry*(1+CFG.TP_PCT)) if side=="long" else (px_now <= entry*(1-CFG.TP_PCT))
            hit_sl = (px_now <= entry*(1-CFG.SL_PCT)) if side=="long" else (px_now >= entry*(1+CFG.SL_PCT))
            if not (hit_tp or hit_sl): return
            pnl = self._pnl(px_now); self.balance += pnl
            self.trades.append({"time": datetime.utcnow(), "side":f"CLOSE_{side.upper()}",
                                "price":px_now,"bal":self.balance,"pnl":pnl})
            tg(f"✅ [PAPER] {side.upper()} 종료 @ {px_now:.2f}  PnL={pnl:.2f}")
            self.loss_cnt = self.loss_cnt+1 if pnl<0 else 0
            if self.loss_cnt>=CFG.MAX_LOSS:
                self.pause_until = datetime.utcnow()+timedelta(hours=CFG.PAUSE_HR)
                tg(f"⛔ 연속 손실 {self.loss_cnt} – {CFG.PAUSE_HR}h 휴식")
            self.pos=None

    def is_paused(self):
        with self.lock:
            if self.pause_until and datetime.utcnow() < self.pause_until:
                return True
            if self.pause_until and datetime.utcnow() >= self.pause_until:
                self.pause_until=None; self.loss_cnt=0; tg("▶️ 트레이딩 재개")
            return False

    def sync_position(self):
        """(Live 모드) 교차검증: 실제 거래소 포지션과 동기화"""
        with self.lock:
            if self.paper or not self.pos: return
            pos_ex = self.ex.fetch_position(CFG.SYMBOL)
            if not pos_ex:
                tg("ℹ️ 포지션 동기화: 거래소에 포지션 없음 → 내부 상태 초기화")
                self.pos = None
