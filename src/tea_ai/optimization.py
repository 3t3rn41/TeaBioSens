"""Measured-first ranking of the 32 legal TeaBioSens design points."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .constants import CHEMISTRY_BASE, RECIPE_FEATURES, SENSORY_TARGETS
from .design_space import DESIGN_COLUMNS_G, RecipeDesignSpace, enumerate_valid_design_points
from .inference import TeaPredictor
from .io import project_root, write_json

DEFAULT_WEIGHTED_SENSORY = {
    "appearance": 0.15,
    "infusion_color": 0.15,
    "aroma": 0.20,
    "taste": 0.35,
    "solubility": 0.15,
}
RECOMMENDATION_PERMUTATION_ALPHA = 0.05


def _objective(values: dict, objective: str, weights: dict[str, float] | None = None) -> float:
    key_map = {
        "maximize_overall": "overall_score",
        "maximize_overall_score": "overall_score",
        "overall_score": "overall_score",
        "maximize_taste": "taste",
        "taste": "taste",
        "maximize_aroma": "aroma",
        "aroma": "aroma",
    }
    if objective in key_map:
        return float(values[key_map[objective]])
    if objective in {"weighted_sensory", "maximize_weighted_sensory"}:
        selected_weights = weights or DEFAULT_WEIGHTED_SENSORY
        if set(selected_weights) - set(SENSORY_TARGETS):
            raise ValueError(f"Unknown weighted sensory targets: {set(selected_weights) - set(SENSORY_TARGETS)}")
        total = float(sum(selected_weights.values()))
        if total <= 0 or any(weight < 0 for weight in selected_weights.values()):
            raise ValueError("Weighted sensory weights must be non-negative with positive sum")
        return float(sum((weight / total) * values[target] for target, weight in selected_weights.items()))
    raise ValueError(f"Unsupported objective: {objective}")


def _objective_std(values: dict, objective: str, weights: dict[str, float] | None = None) -> float:
    if objective in {"maximize_overall", "maximize_overall_score", "overall_score"}:
        return float(values.get("overall_score", 0.0))
    if objective in {"maximize_taste", "taste"}:
        return float(values.get("taste", 0.0))
    if objective in {"maximize_aroma", "aroma"}:
        return float(values.get("aroma", 0.0))
    selected_weights = weights or DEFAULT_WEIGHTED_SENSORY
    total = float(sum(selected_weights.values()))
    return float(np.sqrt(sum(((weight / total) ** 2) * values.get(target, 0.0) ** 2 for target, weight in selected_weights.items())))


def _reliable_chemistry_targets(metrics: dict) -> set[str]:
    reliable = set()
    for target, info in metrics.get("by_target", {}).items():
        selected = info.get("selected_metrics", {})
        baseline = info.get("baseline", {})
        if selected.get("mae", float("inf")) < baseline.get("mae", -float("inf")) and selected.get("rmse", float("inf")) < baseline.get("rmse", -float("inf")):
            reliable.add(target)
    return reliable


def _constraint_value_satisfied(value, limits):
    if not np.isfinite(value):
        return False
    return ("min" not in limits or value >= float(limits["min"])) and ("max" not in limits or value <= float(limits["max"]))


def select_diverse_top_k(candidates: pd.DataFrame, recipe_columns, score_column: str = "ranking_score", top_k: int = 10, min_linf: float = 0.05) -> pd.DataFrame:
    """Select a deterministic diverse Top-K over an arbitrary N-part recipe vector."""
    ordered = candidates.sort_values([score_column, "objective_value"], ascending=[False, False], kind="stable")
    chosen_indices = []
    chosen_vectors = []
    for index, candidate in ordered.iterrows():
        vector = candidate[list(recipe_columns)].to_numpy(dtype=float)
        if all(np.max(np.abs(vector - prior)) >= min_linf - 1e-12 for prior in chosen_vectors):
            chosen_indices.append(index)
            chosen_vectors.append(vector)
            if len(chosen_indices) >= max(1, int(top_k)):
                break
    result = ordered.loc[chosen_indices].copy()
    result.insert(0, "rank", np.arange(1, len(result) + 1))
    return result


def rank_design_space(
    predictor: TeaPredictor | None = None,
    objective: str = "maximize_overall",
    top_k: int = 10,
    risk_lambda: float = 1.0,
    disagreement_gamma: float = 1.0,
    weighted_sensory: dict[str, float] | None = None,
    recipe_bounds: dict[str, dict[str, float]] | None = None,
    chemistry_constraints: dict[str, dict[str, float]] | None = None,
    allow_experimental_chemistry_constraints: bool = False,
    diversity_min_linf: float = 0.05,
    output_dir: str | Path | None = None,
) -> dict:
    root = project_root()
    predictor = predictor or TeaPredictor(root)
    bounds = recipe_bounds or {}
    chemistry_constraints = chemistry_constraints or {}
    reliable = _reliable_chemistry_targets(predictor.chemistry_metrics)
    unavailable = set(chemistry_constraints) - reliable
    if unavailable and not allow_experimental_chemistry_constraints:
        raise ValueError(f"Chemistry constraints are experimental/unreliable and cannot be applied strictly: {sorted(unavailable)}")

    design = predictor.design_space
    model_gate = predictor.direct_metrics.get("gate", {})
    trustworthiness = getattr(predictor, "trustworthiness_metrics", {}) or {}
    permutation_test = trustworthiness.get("permutation_test", {})
    gate_b_permutation_p = permutation_test.get("gate_b_empirical_p")
    credibility_gate_pass = (
        gate_b_permutation_p is not None
        and np.isfinite(float(gate_b_permutation_p))
        and float(gate_b_permutation_p) < RECOMMENDATION_PERMUTATION_ALPHA
    )
    ai_recommendation_enabled = model_gate.get("status") == "PASS" and credibility_gate_pass
    recommendation_gate = {
        "raw_oof_gate_status": model_gate.get("status", "UNKNOWN"),
        "permutation_p_value": float(gate_b_permutation_p) if gate_b_permutation_p is not None else None,
        "permutation_alpha": RECOMMENDATION_PERMUTATION_ALPHA,
        "permutation_validation_status": "PASS" if credibility_gate_pass else "NOT_VALIDATED",
        "automated_prediction_recommendations_enabled": bool(ai_recommendation_enabled),
    }
    observed_lookup = {tuple(float(v) for v in row[DESIGN_COLUMNS_G]): row for _, row in design.master.iterrows()}
    rows = []
    for point in sorted(enumerate_valid_design_points()):
        proportions = np.asarray(point, dtype=float) / 4.0
        prediction = predictor.predict_recipe(proportions)
        status = prediction["design_status"]
        predicted_sensory = prediction["path_b_sensory"]
        path_a_sensory = prediction["path_a_sensory"]
        pred_objective = _objective(predicted_sensory, objective, weighted_sensory)
        disagreement = _objective({name: prediction["model_disagreement_by_target"][name] for name in SENSORY_TARGETS}, objective, weighted_sensory)
        pred_std = _objective_std(prediction["path_b_uncertainty"], objective, weighted_sensory)
        measured_row = observed_lookup.get(tuple(float(v) for v in point))
        if status == "OBSERVED":
            measured_sensory = {target: float(measured_row[f"{target}_mean"]) for target in SENSORY_TARGETS}
            measured_objective = _objective(measured_sensory, objective, weighted_sensory)
            measured_spread = {target: float(measured_row[f"{target}_std"]) for target in SENSORY_TARGETS}
            objective_uncertainty = _objective_std(measured_spread, objective, weighted_sensory)
            evidence_type = "MEASURED"
            ranking_score = measured_objective
            sample_code = str(measured_row["sample_code"])
            evidence_chemistry = {target: float(measured_row[target]) for target in CHEMISTRY_BASE}
        else:
            measured_sensory = {}
            measured_objective = np.nan
            objective_uncertainty = pred_std
            evidence_type = "PREDICTED"
            ranking_score = pred_objective - float(risk_lambda) * pred_std - float(disagreement_gamma) * disagreement
            sample_code = None
            evidence_chemistry = prediction["predicted_chemistry"]

        ingredient_ok = True
        for feature, limits in bounds.items():
            if feature not in RECIPE_FEATURES:
                raise ValueError(f"Unknown recipe-bound feature: {feature}")
            ingredient_ok &= _constraint_value_satisfied(float(proportions[RECIPE_FEATURES.index(feature)]), limits)
        chemistry_ok = True
        for target, limits in chemistry_constraints.items():
            chemistry_ok &= _constraint_value_satisfied(evidence_chemistry[target], limits)
        constraint_ok = bool(ingredient_ok and chemistry_ok)
        nearest = prediction["nearest_samples"][0] if prediction["nearest_samples"] else {}
        row = {
            **dict(zip(DESIGN_COLUMNS_G, [float(value) for value in point])),
            **dict(zip(RECIPE_FEATURES, proportions.astype(float))),
            "design_status": status,
            "evidence_type": evidence_type,
            "sample_code_if_observed": sample_code,
            "objective": objective,
            "measured_objective": measured_objective,
            "predicted_objective": pred_objective,
            "objective_value": measured_objective if status == "OBSERVED" else pred_objective,
            "objective_uncertainty": objective_uncertainty,
            "model_disagreement": disagreement,
            "ranking_score": ranking_score,
            "nearest_sample": nearest.get("sample_code"),
            "nearest_distance_g": nearest.get("distance_g_euclidean"),
            "within_user_constraints": constraint_ok,
            "model_anomaly": bool(prediction.get("model_anomaly", False)) if status != "OBSERVED" else False,
            "model_anomaly_reasons": prediction.get("model_anomaly_reasons", []) if status != "OBSERVED" else [],
            "recommendation_eligible": bool(constraint_ok and (status == "OBSERVED" or (ai_recommendation_enabled and not prediction.get("model_anomaly", False)))),
            "ai_recommendation_gate": model_gate.get("status", "UNKNOWN"),
            "gate_b_permutation_p_value": recommendation_gate["permutation_p_value"],
            "chemistry_constraints_experimental": bool(unavailable and allow_experimental_chemistry_constraints),
            "measured_sensory": measured_sensory,
            "measured_chemistry": ({target: float(measured_row[target]) for target in CHEMISTRY_BASE} if measured_row is not None else {}),
            "chemistry_for_constraints": evidence_chemistry,
            "predicted_sensory_path_a": path_a_sensory,
            "predicted_sensory_path_b": predicted_sensory,
            "predicted_chemistry": prediction["predicted_chemistry"],
            "prediction_detail": prediction,
        }
        if measured_row is not None:
            row["n_ratings"] = int(measured_row["n_ratings"])
            for target in SENSORY_TARGETS:
                row[f"measured_{target}_mean"] = float(measured_row[f"{target}_mean"])
                row[f"measured_{target}_std"] = float(measured_row[f"{target}_std"])
        rows.append(row)

    table = pd.DataFrame(rows)
    table["eligible"] = table["recommendation_eligible"]
    eligible = table[table["eligible"]]
    top = select_diverse_top_k(eligible, RECIPE_FEATURES, top_k=top_k, min_linf=diversity_min_linf)

    missing = table[table["design_status"] == "UNOBSERVED_VALID"].sort_values("objective_uncertainty", ascending=False, kind="stable").copy()
    missing.insert(0, "experiment_priority", np.arange(1, len(missing) + 1))
    summary = {
        **design.describe(),
        "objective": objective,
        "eligible_count": int(table["eligible"].sum()),
        "top_k_returned": int(len(top)),
        "risk_lambda": float(risk_lambda),
        "disagreement_gamma": float(disagreement_gamma),
        "diversity_min_linf": float(diversity_min_linf),
        "reliable_chemistry_constraints": sorted(reliable),
        "ai_recommendation_enabled": ai_recommendation_enabled,
        "recipe_sensory_gate": model_gate,
        "recommendation_credibility_gate": recommendation_gate,
        "scientific_note": "within-design reconstruction only; GPR spread and model disagreement are not calibrated probabilities.",
    }
    out = Path(output_dir or root / "artifacts/optimization")
    out.mkdir(parents=True, exist_ok=True)
    _flatten_for_csv(table).to_csv(out / "design_space_32.csv", index=False)
    _flatten_for_csv(missing).to_csv(out / "next_experiments.csv", index=False)
    _flatten_for_csv(top).to_csv(out / "top_candidates.csv", index=False)
    write_json(out / "optimization_summary.json", summary)
    return {"table": table, "top_candidates": top, "next_experiments": missing, "summary": summary}


def _flatten_for_csv(frame: pd.DataFrame) -> pd.DataFrame:
    copy = frame.copy()
    for column in copy.columns:
        if copy[column].dtype == object:
            copy[column] = copy[column].map(lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True, default=lambda item: item.item() if hasattr(item, "item") else str(item)) if isinstance(value, (dict, list, tuple)) else value)
    return copy
