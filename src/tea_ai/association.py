"""Model-free distance association tests for blend and sensory profiles."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.spatial.distance import pdist

from .constants import MODEL_SENSORY_TARGETS, RECIPE_FEATURES


def _mantel_pearson(left: np.ndarray, right: np.ndarray) -> float:
    left = np.asarray(left, dtype=float)
    right = np.asarray(right, dtype=float)
    if left.size != right.size or left.size < 3:
        raise ValueError("Mantel vectors must have the same length and at least three pairs")
    left_centered = left - left.mean()
    right_centered = right - right.mean()
    denominator = float(np.linalg.norm(left_centered) * np.linalg.norm(right_centered))
    if denominator == 0:
        return 0.0
    return float(np.dot(left_centered, right_centered) / denominator)


def _holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    adjusted = {}
    running = 0.0
    count = len(ordered)
    for index, (name, p_value) in enumerate(ordered):
        running = max(running, (count - index) * p_value)
        adjusted[name] = min(1.0, running)
    return adjusted


def mantel_recipe_sensory_test(
    blends: pd.DataFrame,
    permutations: int = 4_999,
    seed: int = 42,
) -> dict:
    """Joint-row permutation Mantel test on 30 independent recipe means.

    The global test compares Euclidean recipe distances to Euclidean distances
    between the five-column standardized sensory profiles. Per-target results
    are supplementary; their p-values receive Holm adjustment.
    """
    if permutations < 1:
        raise ValueError("permutations must be positive")
    required = [*RECIPE_FEATURES, *[f"{target}_mean" for target in MODEL_SENSORY_TARGETS]]
    missing = [name for name in required if name not in blends]
    if missing:
        raise ValueError(f"Missing blend fields: {missing}")
    if blends[required].isna().any().any():
        raise ValueError("Recipe and modeled sensory means must be complete")
    X = blends[RECIPE_FEATURES].to_numpy(dtype=float)
    Y = blends[[f"{target}_mean" for target in MODEL_SENSORY_TARGETS]].to_numpy(dtype=float)
    if len(X) < 4:
        raise ValueError("At least four independent recipes are required")
    sd = Y.std(axis=0, ddof=0)
    if np.any(sd == 0):
        raise ValueError("Each modeled sensory target must vary across recipes")
    Y_standardized = (Y - Y.mean(axis=0)) / sd
    recipe_distances = pdist(X, metric="euclidean")
    observed_by_target = {
        target: _mantel_pearson(recipe_distances, pdist(Y_standardized[:, [i]], metric="euclidean"))
        for i, target in enumerate(MODEL_SENSORY_TARGETS)
    }
    observed_global = _mantel_pearson(recipe_distances, pdist(Y_standardized, metric="euclidean"))

    rng = np.random.default_rng(seed)
    global_null = np.empty(permutations, dtype=float)
    target_null = {target: np.empty(permutations, dtype=float) for target in MODEL_SENSORY_TARGETS}
    for index in range(permutations):
        permuted = Y_standardized[rng.permutation(len(Y_standardized))]
        global_null[index] = _mantel_pearson(recipe_distances, pdist(permuted, metric="euclidean"))
        for column, target in enumerate(MODEL_SENSORY_TARGETS):
            target_null[target][index] = _mantel_pearson(
                recipe_distances,
                pdist(permuted[:, [column]], metric="euclidean"),
            )

    def permutation_summary(observed: float, null: np.ndarray) -> dict:
        exceedances = int(np.sum(np.abs(null) >= abs(observed)))
        return {
            "mantel_pearson_r": float(observed),
            "two_sided_exceedances": exceedances,
            "permutation_p_value": float((exceedances + 1) / (permutations + 1)),
            "null_95pct_interval": [float(x) for x in np.quantile(null, [0.025, 0.975])],
        }

    target_results = {
        target: permutation_summary(observed_by_target[target], target_null[target])
        for target in MODEL_SENSORY_TARGETS
    }
    adjusted = _holm_adjust({target: result["permutation_p_value"] for target, result in target_results.items()})
    for target, result in target_results.items():
        result["holm_adjusted_p_value"] = adjusted[target]
    return {
        "test": "Mantel Pearson correlation with joint row-permutation null",
        "n_independent_recipes": int(len(X)),
        "permutations": int(permutations),
        "seed": int(seed),
        "permutation_scheme": "Sensory sample rows are jointly permuted against fixed recipe rows; the five sensory outcomes remain together.",
        "recipe_distance": "Euclidean distance on the four ingredient proportions (equivalent scaling to grams because total mass is fixed).",
        "sensory_distance": "Euclidean distance on the five per-recipe sensory means after column-wise standardization.",
        "global_multivariate": permutation_summary(observed_global, global_null),
        "per_target_supplementary": target_results,
        "interpretation_limit": "A non-significant test means this sample did not detect distance association at the chosen threshold; it does not establish that association is absent and does not test causality or predictive performance.",
    }
