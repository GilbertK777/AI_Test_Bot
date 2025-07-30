"""
포지션 및 주문 관리를 총괄하는 서비스.

이 클래스는 현재 포지션 상태(`self.pos`), 잔고(`self.balance`), 거래 내역(`self.trades`) 등을 관리하며,
라이브 트레이딩과 페이퍼 트레이딩(모의 투자)을 모두 지원합니다.
모든 공개 메서드는 스레드로부터 안전하게(thread-safe) 호출될 수 있도록 `threading.Lock`을 사용합니다.

주요 책임:
- **포지션 진입 (`open_position`)**: 새로운 롱 또는 숏 포지션을 엽니다.
  - 페이퍼 모드: 내부 상태만 업데이트하고 슬리피지를 시뮬레이션합니다.
  - 라이브 모드: 실제 거래소에 시장가 주문을 전송합니다.
- **TP/SL 주문 부착 (`_attach_tp_sl`)**: 포지션 진입 후, 자동으로 이익 실현(TP) 및 손절(SL) 주문을 거래소에 전송합니다.
- **포지션 종료 확인**:
  - 페이퍼 모드 (`poll_position_closed`): 현재 가격이 TP/SL 가격에 도달했는지 지속적으로 확인(polling)하여 포지션을 종료시킵니다.
  - 라이브 모드: 거래소에 부착된 TP/SL 주문이 체결되면, `sync_position`을 통해 포지션이 사라진 것을 감지합니다.
- **손익(PnL) 계산 (`_pnl`)**: 포지션 종료 시 손익을 계산합니다.
- **리스크 관리 (`is_paused`)**: 설정된 횟수(`CFG.MAX_LOSS`)만큼 연속 손실이 발생하면,
  설정된 시간(`CFG.PAUSE_HR`) 동안 신규 거래를 중단시킵니다.
- **상태 동기화 (`sync_position`)**: 라이브 모드에서 내부 포지션 상태와 실제 거래소의 포지션 상태가 일치하는지 주기적으로 확인하고 동기화합니다.
"""
import logging
import threading
from datetime import datetime, timedelta
from config.config import CFG
from src.utils.helpers import tg
from src.exchange.exchange_client import ExchangeClient

class OrderService:
    """포지션 관리, 주문 실행, 리스크 관리 등을 담당하는 클래스."""

    def __init__(self, ex: ExchangeClient, paper: bool = True, init_balance: float = 0.0):
        """
        OrderService 인스턴스를 초기화합니다.

        Args:
            ex (ExchangeClient): 거래소 통신을 위한 클라이언트 객체.
            paper (bool, optional): 페이퍼 트레이딩 모드 활성화 여부. Defaults to True.
            init_balance (float, optional): 초기 잔고 (페이퍼 트레이딩 시 사용). Defaults to 0.0.
        """
        self.ex = ex
        self.paper = paper
        self.balance = init_balance

        # 현재 포지션 정보. 없으면 None. 예: {"entry": 30000, "qty": 0.01, "side": "long"}
        self.pos = None
        # 모든 거래(진입/종료) 기록을 저장하는 리스트.
        self.trades = []

        # 리스크 관리 변수
        self.loss_cnt = 0         # 연속 손실 횟수
        self.pause_until = None   # 거래 중단이 해제되는 시간 (datetime 객체)

        # 멀티스레드 환경에서 공유 데이터(self.pos, self.balance 등)를 안전하게 접근하기 위한 잠금(lock) 객체.
        self.lock = threading.Lock()

        # 라이브 모드일 경우, 시작 시점에 레버리지와 마진 모드를 설정합니다.
        if not paper:
            self.ex.set_leverage(CFG.SYMBOL, CFG.LEVERAGE, CFG.ISOLATED)

    def _pnl(self, exit_px: float) -> float:
        """내부적으로 손익(PnL)을 계산합니다."""
        if not self.pos: return 0.0
        entry, qty, side = self.pos["entry"], self.pos["qty"], self.pos["side"]

        # 가격 변화에 따른 손익 계산
        delta = (exit_px - entry) if side == "long" else (entry - exit_px)

        # 수수료 및 펀딩비 계산
        fee = abs(exit_px * qty) * CFG.TRADE_FEE
        funding = abs(entry * qty) * self.ex.fetch_funding_rate(CFG.SYMBOL)

        # 최종 PnL = (가격 변화 * 수량 * 레버리지) - 수수료 - 펀딩비
        return delta * qty * CFG.LEVERAGE - fee - funding

    def _attach_tp_sl(self, side: str, entry_px: float, qty: float):
        """포지션 진입 후 TP/SL 주문을 거래소에 전송합니다 (라이브 모드 전용)."""
        # 설정된 비율에 따라 TP/SL 가격을 계산합니다.
        tp_px = entry_px * (1 + CFG.TP_PCT) if side == "long" else entry_px * (1 - CFG.TP_PCT)
        sl_px = entry_px * (1 - CFG.SL_PCT) if side == "long" else entry_px * (1 + CFG.SL_PCT)

        if self.paper:
            logging.info(f"[PAPER] Simulating TP/SL attachment at TP={tp_px:.2f}, SL={sl_px:.2f}")
            return

        try:
            # BUGFIX 주석: 원래 코드의 버그 수정 사항을 명시.
            # 주문 가격은 거래소에서 요구하는 정밀도(소수점 자릿수)에 맞춰야 합니다.
            # `price_to_precision`는 ccxt의 유틸리티 함수로, 이를 자동으로 처리해줍니다.
            tp_px_r = self.ex.client.price_to_precision(CFG.SYMBOL, tp_px)
            sl_px_r = self.ex.client.price_to_precision(CFG.SYMBOL, sl_px)

            # 종료 주문의 방향은 진입 포지션과 반대입니다.
            exit_side = "SELL" if side == "long" else "BUY"

            # 거래소에 TP 주문과 SL 주문을 각각 전송합니다.
            self.ex.create_exit_order(CFG.SYMBOL, exit_side, qty, tp_px_r, tp=True)
            self.ex.create_exit_order(CFG.SYMBOL, exit_side, qty, sl_px_r, tp=False)
            logging.info(f"[LIVE] TP/SL orders attached at TP={tp_px_r}, SL={sl_px_r}")
        except Exception as e:
            logging.error(f"Failed to attach TP/SL orders: {e}")
            tg(f"⚠️ Failed to attach TP/SL orders: {e}")

    def open_position(self, px: float, qty: float, side: str):
        """새로운 포지션을 엽니다."""
        with self.lock:
            if self.pos: return # 이미 포지션이 있으면 진입하지 않음

            # 페이퍼 모드에서는 슬리피지를 시뮬레이션하여 진입 가격을 계산합니다.
            entry_px = px * (1 + CFG.SLIP_PCT) if side == "long" else px * (1 - CFG.SLIP_PCT)

            if not self.paper:
                try:
                    # 라이브 모드에서는 실제 시장가 주문을 전송합니다.
                    order = self.ex.create_market_order(CFG.SYMBOL, "buy" if side == "long" else "sell", qty)
                    # 실제 체결된 가격으로 진입 가격을 업데이트합니다. 체결가 정보가 없으면 시뮬레이션 가격을 사용합니다.
                    entry_px = float(order.get("price", entry_px))
                except Exception as e:
                    logging.error(f"Failed to open {side} position: {e}")
                    tg(f"⚠️ Failed to open {side} position: {e}")
                    return

            # 내부 포지션 상태를 업데이트합니다.
            self.pos = {"entry": entry_px, "qty": qty, "side": side}
            # 거래 내역을 기록합니다.
            self.trades.append({"time": datetime.utcnow(), "side": side.upper(), "price": entry_px, "bal": self.balance})
            tg(f"🚀 {'[PAPER]' if self.paper else '[LIVE]'} {side.upper()} position opened @ {entry_px:.2f}")

            # TP/SL 주문을 부착합니다.
            self._attach_tp_sl(side, entry_px, qty)

    def poll_position_closed(self, px_now: float):
        """(페이퍼 모드 전용) 현재 가격을 기준으로 포지션 종료 여부를 확인합니다."""
        with self.lock:
            # 포지션이 없거나 라이브 모드일 경우 이 메서드는 작동하지 않습니다.
            if not self.pos or not self.paper: return

            entry, side = self.pos["entry"], self.pos["side"]
            # 현재 가격이 TP 또는 SL 가격에 도달했는지 확인합니다.
            hit_tp = (px_now >= entry * (1 + CFG.TP_PCT)) if side == "long" else (px_now <= entry * (1 - CFG.TP_PCT))
            hit_sl = (px_now <= entry * (1 - CFG.SL_PCT)) if side == "long" else (px_now >= entry * (1 + CFG.SL_PCT))

            if not (hit_tp or hit_sl): return # TP/SL에 도달하지 않았으면 아무것도 하지 않음

            # 포지션 종료 처리
            pnl = self._pnl(px_now)
            self.balance += pnl
            self.trades.append({"time": datetime.utcnow(), "side": f"CLOSE_{side.upper()}", "price": px_now, "bal": self.balance, "pnl": pnl})
            tg(f"✅ [PAPER] {side.upper()} position closed @ {px_now:.2f}. PnL={pnl:.2f}")

            # 리스크 관리: 연속 손실 확인
            self.loss_cnt = self.loss_cnt + 1 if pnl < 0 else 0
            if self.loss_cnt >= CFG.MAX_LOSS:
                self.pause_until = datetime.utcnow() + timedelta(hours=CFG.PAUSE_HR)
                tg(f"⛔ Max consecutive losses reached ({self.loss_cnt}). Pausing trading for {CFG.PAUSE_HR} hour(s).")

            # 내부 포지션 상태 초기화
            self.pos = None

    def is_paused(self) -> bool:
        """거래가 연속 손실로 인해 일시 중단 상태인지 확인합니다."""
        with self.lock:
            # `pause_until`이 설정되어 있고, 아직 현재 시간이 그 이전이라면 True를 반환.
            if self.pause_until and datetime.utcnow() < self.pause_until:
                return True
            # `pause_until` 시간이 지났다면, 중단 상태를 해제하고 관련 변수를 초기화.
            if self.pause_until and datetime.utcnow() >= self.pause_until:
                self.pause_until = None
                self.loss_cnt = 0
                tg("▶️ Trading has been resumed.")
            return False

    def sync_position(self):
        """(라이브 모드 전용) 실제 거래소의 포지션과 내부 상태를 동기화합니다."""
        with self.lock:
            # 페이퍼 모드이거나 내부적으로 포지션이 없다고 기록된 경우, 동기화가 불필요.
            if self.paper or not self.pos: return

            # 거래소에서 실제 포지션 정보를 가져옵니다.
            pos_ex = self.ex.fetch_position(CFG.SYMBOL)

            # 거래소에 해당 심볼의 포지션이 없는데, 내부적으로는 포지션이 있다고 기록된 경우
            # (예: TP/SL이 체결되었거나, 수동으로 포지션을 닫은 경우)
            if not pos_ex:
                tg("ℹ️ Position sync: No position found on exchange. Resetting internal state.")
                # 내부 포지션 상태를 초기화합니다.
                self.pos = None
