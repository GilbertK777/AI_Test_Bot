"""
XGBoost 머신러닝 모델의 전체 생명주기(학습, 예측, 저장/로드)를 관리하는 서비스.

이 클래스는 다음과 같은 역할을 수행합니다:
1.  **모델 로딩**: 애플리케이션 시작 시, 지정된 경로에 저장된 기존 모델 파일(.joblib)을 불러옵니다.
2.  **모델 학습 (`train`)**:
    -   **데이터 준비**: 입력된 데이터프레임에서 학습에 사용할 피처(X)와 타겟(y)을 분리합니다.
    -   **데이터 불균형 처리**: `SMOTE` (Synthetic Minority Over-sampling Technique)를 사용하여
        상승(1)과 하락(0) 타겟의 비율을 인위적으로 맞춰 모델이 한쪽으로 편향되는 것을 방지합니다.
    -   **주기적 하이퍼파라미터 튜닝**: `CFG.GRID_DAYS` 주기로 `GridSearchCV`를 실행하여
        최적의 모델 하이퍼파라미터(`n_estimators`, `max_depth` 등)를 탐색하고, 최적 모델을 저장합니다.
    -   **점진적 학습**: GridSearchCV를 실행하지 않는 주기에는, 기존 모델에 새로운 데이터를 추가하여
        `n_estimators`를 늘려가는 방식으로 빠르게 재학습(online learning)을 수행합니다.
    -   **모델 저장**: 학습이 완료된 모델은 `joblib`을 사용하여 파일로 저장됩니다.
3.  **예측 (`add_prob`)**: 학습된 모델을 사용하여 주어진 데이터프레임의 각 행(캔들)에 대해
    '다음 캔들 가격이 상승할 확률' (`prob_up`)을 예측하고, 이 값을 새로운 컬럼으로 추가합니다.
"""
import logging
import joblib
from datetime import datetime
from xgboost import XGBClassifier
from imblearn.over_sampling import SMOTE
from sklearn.model_selection import GridSearchCV
from config.config import CFG
from src.utils.helpers import tg

class ModelService:
    """XGBoost 모델 관리 (학습/예측/저장/로드) 클래스"""

    # 모델 학습에 사용될 피처(특성) 목록.
    # `IndicatorRepository`에서 생성된 멀티-타임프레임 지표들이 포함됩니다.
    FEATURES = ["close", "ema_fast", "ema_slow", "rsi",
                "rsi_1h", "ema_fast_4h", "ema_slow_4h",
                "atr", "macd", "macd_sig"]

    def __init__(self, path):
        """
        ModelService 인스턴스를 초기화합니다.

        Args:
            path (Path): 모델을 저장하거나 불러올 파일 경로 객체.
        """
        self.path = path
        # 지정된 경로에 모델 파일이 존재하면 `joblib.load`를 통해 모델을 불러옵니다.
        # 파일이 없으면 `self.model`은 None으로 초기화됩니다.
        self.model = joblib.load(path) if path.exists() else None
        # 마지막으로 모델을 학습한 시간을 기록하기 위한 변수. `datetime.min`으로 초기화.
        self.t_last_train = datetime.min
        # 마지막으로 GridSearchCV를 실행한 시간을 기록하기 위한 변수.
        self.t_last_grid = datetime.min

    def train(self, df):
        """
        주어진 데이터프레임으로 XGBoost 모델을 학습시킵니다.

        학습 과정은 두 가지 모드로 나뉩니다:
        1.  **전체 학습 (GridSearch)**: 모델이 없거나, 마지막 GridSearch 이후 설정된 기간(`CFG.GRID_DAYS`)이
            지났을 경우 수행됩니다. 최적의 하이퍼파라미터를 찾아 새로운 모델을 생성합니다.
        2.  **점진적 학습**: 기존 모델이 있고 GridSearch 주기가 아닐 경우, 기존 모델에 데이터를 추가하여
            `n_estimators` (트리의 개수)를 늘리는 방식으로 빠르게 재학습합니다.

        Args:
            df (pd.DataFrame): `IndicatorRepository`에서 생성된, 피처와 'target' 컬럼이 포함된 데이터프레임.
        """
        logging.info("Starting model training...")
        # 데이터프레임에서 피처(X)와 타겟(y)을 분리합니다.
        X, y = df[self.FEATURES], df["target"]

        # 데이터를 80%의 학습용(train)과 20%의 검증용(validation)으로 분할합니다. (현재 코드에서는 검증용을 사용하지 않음)
        split = int(len(df) * 0.8)
        X_train_orig, y_train_orig = X[:split], y[:split]

        # SMOTE를 사용하기 전에, 각 클래스의 샘플 수를 확인합니다.
        n_samples_class_0 = (y_train_orig == 0).sum()
        n_samples_class_1 = (y_train_orig == 1).sum()
        n_minority_samples = min(n_samples_class_0, n_samples_class_1)

        # SMOTE는 최소한 k_neighbors + 1 개의 샘플이 필요합니다.
        # 소수 클래스의 샘플 수가 너무 적으면 SMOTE를 적용할 수 없으므로, 이 경우엔 그냥 원본 데이터를 사용합니다.
        if n_minority_samples > 1:
            # k_neighbors는 소수 클래스의 샘플 수보다 작아야 합니다.
            # 기본값(5)보다 샘플 수가 적으면, 샘플 수 - 1을 k_neighbors로 설정하여 에러를 방지합니다.
            k_neighbors = min(5, n_minority_samples - 1)
            logging.info(f"Applying SMOTE with k_neighbors={k_neighbors}")
            X_tr, y_tr = SMOTE(random_state=42, k_neighbors=k_neighbors).fit_resample(X_train_orig, y_train_orig)
        else:
            logging.warning("Skipping SMOTE due to insufficient samples in the minority class.")
            X_tr, y_tr = X_train_orig, y_train_orig

        # GridSearch를 수행해야 할 조건인지 확인합니다.
        # (1) self.model이 None (즉, 한번도 학습된 적 없음) 이거나,
        # (2) 마지막 GridSearch를 실행한 지 `CFG.GRID_DAYS`일 이상 경과한 경우.
        if self.model is None or (datetime.utcnow() - self.t_last_grid).days >= CFG.GRID_DAYS:
            logging.info("Performing full training with GridSearchCV...")
            # 기본 XGBClassifier 모델을 정의합니다. 과적합 방지를 위해 `subsample`과 `colsample_bytree`를 사용합니다.
            base = XGBClassifier(subsample=0.8, colsample_bytree=0.8,
                                 use_label_encoder=False, eval_metric="logloss")
            # 탐색할 하이퍼파라미터 그리드를 정의합니다.
            param_grid = {
                "n_estimators": [120, 160],  # 트리의 개수
                "max_depth": [3, 4],         # 트리의 최대 깊이
                "learning_rate": [0.05, 0.1] # 학습률
            }
            # GridSearchCV 객체를 생성합니다. `cv=3`은 3-fold 교차 검증을 의미합니다. `n_jobs=-1`은 모든 CPU 코어를 사용합니다.
            grid = GridSearchCV(base, param_grid, cv=3, n_jobs=-1)
            grid.fit(X_tr, y_tr)

            # 탐색 결과 가장 성능이 좋았던 모델을 `self.model`로 설정합니다.
            self.model = grid.best_estimator_
            self.t_last_grid = datetime.utcnow()
            logging.info(f"GridSearch finished. Best parameters: {grid.best_params_}")
        else:
            # 점진적 학습을 수행합니다.
            logging.info("Performing incremental training...")
            # 기존 모델의 `n_estimators` 값을 가져와 40만큼 늘립니다.
            n_old = self.model.get_params().get("n_estimators", 100) # 기본값 100
            self.model.set_params(n_estimators=n_old + 40)
            # `xgb_model` 파라미터에 기존 부스터(booster)를 전달하여 학습을 이어갑니다.
            self.model.fit(X_tr, y_tr, xgb_model=self.model.get_booster())

        # 학습이 완료된 모델 객체를 파일로 저장합니다.
        joblib.dump(self.model, self.path)
        self.t_last_train = datetime.utcnow()
        logging.info(f"Model training complete. Model saved to {self.path}")
        tg("📈 모델 재학습 완료")

    def add_prob(self, df):
        """
        학습된 모델을 사용하여 데이터프레임에 상승 확률(`prob_up`)을 추가합니다.

        Args:
            df (pd.DataFrame): 피처 컬럼들이 포함된 데이터프레임.

        Returns:
            pd.DataFrame: 'prob_up' 컬럼이 추가된 데이터프레임.
        """
        df = df.copy()
        if self.model:
            # `predict_proba`는 각 클래스에 대한 확률을 반환합니다. [P(class=0), P(class=1)]
            # `[:, 1]`을 사용하여 클래스 1(상승)에 대한 확률만 선택합니다.
            probabilities = self.model.predict_proba(df[self.FEATURES])
            df["prob_up"] = probabilities[:, 1]
        else:
            # 모델이 아직 학습되지 않았다면, 중립적인 값인 0.5로 채웁니다.
            df["prob_up"] = 0.5
        return df
