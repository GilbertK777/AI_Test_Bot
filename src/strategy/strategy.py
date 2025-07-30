"""
규칙기반 + ML 혼합 Long/Short/Exit 시그널 생성
"""
from config.config import CFG

class Strategy:
    """진입·청산 신호 계산 Static 클래스"""

    @staticmethod
    def enrich(df):
        df = df.copy()
        df["rule_long"] = ((df["ema_fast"] > df["ema_slow"]) &
                           (df["rsi"] < 40) &
                           (df["macd"] > df["macd_sig"]))
        df["rule_short"] = ((df["ema_fast"] < df["ema_slow"]) &
                            (df["rsi"] > 60) &
                            (df["macd"] < df["macd_sig"]))
        df["long"]  = df["rule_long"]  & (df["prob_up"] > CFG.BUY_TH)
        df["short"] = df["rule_short"] & (df["prob_up"] < CFG.SHORT_TH)
        df["exit_l"] = ((df["prob_up"] < CFG.SELL_TH) |
                        (df["rsi"] > 70) |
                        (df["macd"] < df["macd_sig"]))
        df["exit_s"] = ((df["prob_up"] > CFG.BUY_TH) |
                        (df["rsi"] < 30) |
                        (df["macd"] > df["macd_sig"]))
        # NOTE: 일부 진입/청산 조건이 중복 (e.g., long 진입/청산 모두 macd>sig 조건 포함).
        # 이는 빠른 손절 또는 Whipsaw(잦은 매매)를 유발할 수 있으므로 전략 검토 필요.
        return df
