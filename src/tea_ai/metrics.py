"""Metrics calculated on complete out-of-fold prediction vectors."""

from __future__ import annotations

import numpy as np
from scipy.stats import spearmanr
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def regression_metrics(y_true, y_pred) -> dict[str, float]:
    actual = np.asarray(y_true, dtype=float).reshape(-1)
    predicted = np.asarray(y_pred, dtype=float).reshape(-1)
    valid = np.isfinite(actual) & np.isfinite(predicted)
    actual, predicted = actual[valid], predicted[valid]
    if not len(actual):
        return {"mae": float("nan"), "rmse": float("nan"), "r2": float("nan"), "spearman": float("nan"), "n": 0}
    corr = spearmanr(actual, predicted).statistic if len(actual) > 1 else float("nan")
    if not np.isfinite(corr):
        corr = float("nan")
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(np.sqrt(mean_squared_error(actual, predicted))),
        "r2": float(r2_score(actual, predicted)) if len(actual) > 1 else float("nan"),
        "spearman": float(corr),
        "n": int(len(actual)),
    }

