"""Conservative model family constructors used by all prediction tasks."""

from __future__ import annotations

from sklearn.cross_decomposition import PLSRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ..constants import RANDOM_STATE
from ..uncertainty import gaussian_process


def candidate_estimators(n_features: int, include_optional: bool = True) -> dict[str, object]:
    candidates: dict[str, object] = {
        "ridge": Pipeline([("scale", StandardScaler()), ("model", Ridge(alpha=1.0))]),
        "pls": Pipeline([
            ("scale", StandardScaler()),
            ("model", PLSRegression(n_components=max(1, min(2, n_features)), scale=False)),
        ]),
        "gpr": gaussian_process(RANDOM_STATE),
        "random_forest": RandomForestRegressor(
            n_estimators=300, max_depth=4, min_samples_leaf=3,
            max_features=0.9, random_state=RANDOM_STATE, n_jobs=1,
        ),
    }
    if not include_optional:
        return candidates
    try:
        from xgboost import XGBRegressor
        candidates["xgboost"] = XGBRegressor(
            n_estimators=100, max_depth=2, learning_rate=0.04,
            subsample=0.85, colsample_bytree=0.85, reg_alpha=0.1,
            reg_lambda=2.0, objective="reg:squarederror", random_state=RANDOM_STATE,
            n_jobs=1, verbosity=0,
        )
    except ImportError:
        pass
    try:
        from catboost import CatBoostRegressor
        candidates["catboost"] = CatBoostRegressor(
            iterations=120, depth=3, learning_rate=0.04, l2_leaf_reg=3.0,
            loss_function="RMSE", random_seed=RANDOM_STATE, verbose=False,
            allow_writing_files=False, thread_count=1,
        )
    except ImportError:
        pass
    return candidates
