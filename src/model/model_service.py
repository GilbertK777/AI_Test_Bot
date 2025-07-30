"""
XGBoost 모델 관리 (학습/예측/저장)
"""
import logging, joblib
import numpy as np
from datetime import datetime
from xgboost import XGBClassifier
from imblearn.over_sampling import SMOTE
from sklearn.model_selection import GridSearchCV
from config.config import CFG
from src.utils.helpers import tg

class ModelService:
    FEATURES = ["close", "ema_fast", "ema_slow", "rsi",
                "rsi_1h", "ema_fast_4h", "ema_slow_4h",
                "atr", "macd", "macd_sig"]

    def __init__(self, path):
        self.path = path
        self.model = joblib.load(path) if path.exists() else None
        self.t_last_train = datetime.min
        self.t_last_grid  = datetime.min

    def train(self, df):
        X, y = df[self.FEATURES], df["target"]
        split = int(len(df) * 0.8)
        X_tr, y_tr = SMOTE(random_state=42).fit_resample(X[:split], y[:split])
        if self.model is None or (datetime.utcnow() - self.t_last_grid).days >= CFG.GRID_DAYS:
            base = XGBClassifier(subsample=0.8, colsample_bytree=0.8,
                                 use_label_encoder=False, eval_metric="logloss")
            grid = GridSearchCV(base,
                                {"n_estimators": [120, 160],
                                 "max_depth": [3, 4],
                                 "learning_rate": [0.05, 0.1]},
                                cv=3, n_jobs=-1)
            grid.fit(X_tr, y_tr)
            self.model = grid.best_estimator_
            self.t_last_grid = datetime.utcnow()
            logging.info(f"GridSearch best: {grid.best_params_}")
        else:
            n_old = self.model.get_params().get("n_estimators", 0)
            self.model.set_params(n_estimators=n_old + 40)
            self.model.fit(X_tr, y_tr, xgb_model=self.model.get_booster())
        joblib.dump(self.model, self.path)
        self.t_last_train = datetime.utcnow()
        tg("📈 모델 재학습 완료")

    def add_prob(self, df):
        df = df.copy()
        df["prob_up"] = (self.model.predict_proba(df[self.FEATURES])[:, 1]
                         if self.model else 0.5)
        return df
