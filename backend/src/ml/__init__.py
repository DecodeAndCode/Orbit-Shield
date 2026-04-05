"""ML enhancement layer for collision probability prediction.

Provides XGBoost-based models for:
- Covariance estimation from orbital metadata
- Conjunction risk classification (P(Pc > 1e-4))

All ML functionality is optional. When sklearn/xgboost are not installed,
ML_AVAILABLE is False and the screening pipeline falls back to classical methods.
"""

try:
    import sklearn  # noqa: F401
    import xgboost  # noqa: F401

    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
