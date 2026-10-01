"""Reproducible inference across both recipe prediction paths."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .constants import CHEMISTRY_ALL, CHEMISTRY_BASE, CHEMISTRY_RATIOS, RECIPE_FEATURES, SENSORY_TARGETS
from .design_space import RecipeDesignSpace
from .features import recompute_ratios, validate_recipe
from .io import project_root
from .uncertainty import predict_mean_std


class TeaPredictor:
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or project_root())
        self.master = pd.read_csv(self.root / "data/processed/blend_master.csv")
        self.design_space = RecipeDesignSpace(self.master)
        self.chemistry = joblib.load(self.root / "artifacts/models/chemistry/model.joblib")
        self.sensory = joblib.load(self.root / "artifacts/models/sensory/model.joblib")
        self.direct = joblib.load(self.root / "artifacts/models/direct_recipe/model.joblib")
        for name, expected in [("chemistry", RECIPE_FEATURES), ("sensory", CHEMISTRY_ALL), ("direct_recipe", RECIPE_FEATURES)]:
            path = self.root / f"artifacts/models/{name}/feature_order.json"
            order = json.loads(path.read_text(encoding="utf-8"))["features"]
            if order != expected:
                raise ValueError(f"Feature order mismatch for {name}: saved {order}, expected {expected}")
        self.chemistry_metrics = json.loads((self.root / "artifacts/reports/recipe_chemistry_metrics.json").read_text(encoding="utf-8"))
        self.direct_metrics = json.loads((self.root / "artifacts/reports/recipe_sensory_metrics.json").read_text(encoding="utf-8"))
        self.sensory_metrics = json.loads((self.root / "artifacts/reports/chemistry_sensory_metrics.json").read_text(encoding="utf-8"))

    @staticmethod
    def _single_row(values, columns):
        return pd.DataFrame([values], columns=columns)

    def predict_recipe(self, recipe_pct) -> dict:
        proportions = validate_recipe(recipe_pct)
        recipe_g = proportions * 4.0
        status = self.design_space.recipe_status(recipe_g)
        neighbors = self.design_space.nearest(recipe_g, k=3)
        base = {
            "recipe_pct": dict(zip(RECIPE_FEATURES, proportions.astype(float))),
            "recipe_g": dict(zip(["green_g", "white_g", "oolong_g", "black_g"], recipe_g.astype(float))),
            "design_status": status,
            "evidence_type": "MEASURED" if status == "OBSERVED" else ("PREDICTED" if status == "UNOBSERVED_VALID" else "INVALID"),
            "nearest_samples": neighbors,
            "nearest_sample_code": neighbors[0]["sample_code"] if neighbors else None,
            "nearest_distance_g": neighbors[0]["distance_g_euclidean"] if neighbors else None,
            "uncertainty_note": "GPR predictive standard deviation is a model-based spread estimate, not a calibrated confidence interval.",
        }
        if status == "INVALID_DESIGN_POINT":
            base["warning"] = "This combination is outside the current 32-point, 0.5 g-step TeaBioSens design space and cannot be recommended in V0.1–V0.4."
            return base

        recipe_frame = self._single_row(proportions, RECIPE_FEATURES)
        chemistry_mean = {}
        chemistry_std = {}
        for target in CHEMISTRY_BASE:
            estimator = self.chemistry["estimators"][target]
            chem_features = self.chemistry["feature_order_by_target"][target]
            chemistry_mean[target] = float(np.asarray(estimator.predict(recipe_frame[chem_features])).reshape(-1)[0])
            gp = self.chemistry["uncertainty_estimators"][target]
            _, std = predict_mean_std(gp, recipe_frame)
            chemistry_std[target] = float(std[0])
        ratios = recompute_ratios(chemistry_mean)
        chemistry_mean.update({key: value if np.isfinite(value) else None for key, value in ratios.items()})
        chemistry_frame = self._single_row([chemistry_mean.get(col, np.nan) for col in CHEMISTRY_ALL], CHEMISTRY_ALL)
        chemistry_frame = chemistry_frame.replace([np.inf, -np.inf], np.nan).fillna(0.0)

        path_a = {}
        path_a_std = {}
        for target in SENSORY_TARGETS:
            features = self.sensory["features_by_target"][target]
            estimator = self.sensory["estimators"][target]
            path_a[target] = float(np.asarray(estimator.predict(chemistry_frame[features])).reshape(-1)[0])
            gp = self.sensory["uncertainty_estimators"][target]
            _, std = predict_mean_std(gp, chemistry_frame[CHEMISTRY_BASE])
            path_a_std[target] = float(std[0])

        path_b = {}
        path_b_std = {}
        for target in SENSORY_TARGETS:
            estimator = self.direct["estimators"][target]
            direct_features = self.direct["feature_order_by_target"][target]
            path_b[target] = float(np.asarray(estimator.predict(recipe_frame[direct_features])).reshape(-1)[0])
            gp = self.direct["uncertainty_estimators"][target]
            _, std = predict_mean_std(gp, recipe_frame)
            path_b_std[target] = float(std[0])
        disagreement = {target: abs(path_a[target] - path_b[target]) for target in SENSORY_TARGETS}
        if not all(np.isfinite(value) for value in [*chemistry_mean.values(), *chemistry_std.values(), *path_a.values(), *path_a_std.values(), *path_b.values(), *path_b_std.values(), *disagreement.values()] if value is not None):
            raise FloatingPointError("Model inference returned a non-finite prediction or uncertainty")
        anomaly_reasons = []
        negative_chemistry = [name for name in CHEMISTRY_BASE if chemistry_mean[name] < 0]
        if negative_chemistry:
            anomaly_reasons.append(f"negative predicted chemistry: {negative_chemistry}")
        for path_name, scores in [("Path A", path_a), ("Path B", path_b)]:
            outside = [name for name, value in scores.items() if value < 0 or value > 100]
            if outside:
                anomaly_reasons.append(f"{path_name} sensory predictions outside [0, 100]: {outside}")
        base.update({
            "predicted_chemistry": chemistry_mean,
            "chemistry_uncertainty": chemistry_std,
            "path_a_sensory": path_a,
            "path_a_uncertainty": path_a_std,
            "path_b_sensory": path_b,
            "path_b_uncertainty": path_b_std,
            "model_disagreement_by_target": disagreement,
            "model_disagreement": disagreement["overall_score"],
            "predicted_uncertainty": path_b_std["overall_score"],
            "model_anomaly": bool(anomaly_reasons),
            "model_anomaly_reasons": anomaly_reasons,
        })
        observed = self.master[
            np.all(np.isclose(self.master[["green_g", "white_g", "oolong_g", "black_g"]].to_numpy(), recipe_g, atol=1e-8, rtol=0), axis=1)
        ]
        if not observed.empty:
            row = observed.iloc[0]
            base["sample_code"] = str(row["sample_code"])
            base["measured_chemistry"] = {key: float(row[key]) for key in CHEMISTRY_ALL}
            base["measured_sensory"] = {key: {"mean": float(row[f"{key}_mean"]), "std": float(row[f"{key}_std"]), "median": float(row[f"{key}_median"])} for key in SENSORY_TARGETS}
            base["n_ratings"] = int(row["n_ratings"])
        return base


def load_predictor(root: str | Path | None = None) -> TeaPredictor:
    return TeaPredictor(root)
