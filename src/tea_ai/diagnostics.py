"""Small-sample diagnostics for the TeaBioSens repeated-rating data."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .constants import SENSORY_TARGETS


def sensory_noise_decomposition(
    observations: pd.DataFrame,
    targets: list[str] | None = None,
) -> dict:
    """Estimate between-recipe and within-recipe variance by one-way ANOVA.

    This is an unbalanced one-way random-effects method-of-moments estimate.
    The within-recipe component is rating spread plus residual variation; with
    no rater IDs it cannot isolate panelist, session, or measurement effects.
    """
    targets = list(targets or SENSORY_TARGETS)
    if "sample_code" not in observations:
        raise ValueError("observations must include sample_code")
    groups = observations.groupby("sample_code", sort=True)
    counts = groups.size().astype(float)
    n_blends = len(counts)
    n_ratings = int(counts.sum())
    if n_blends < 2 or n_ratings <= n_blends:
        raise ValueError("At least two blends and repeated ratings are required")
    n0 = float((n_ratings - np.square(counts.to_numpy()).sum() / n_ratings) / (n_blends - 1))
    if n0 <= 0:
        raise ValueError("Effective group size must be positive")

    results = {}
    for target in targets:
        if target not in observations:
            raise ValueError(f"Missing sensory field: {target}")
        if observations[target].isna().any():
            raise ValueError(f"Missing values in sensory field: {target}")
        means = groups[target].mean()
        grand_mean = float(observations[target].mean())
        ss_within = float(groups[target].apply(lambda values: np.square(values.to_numpy(dtype=float) - values.mean()).sum()).sum())
        ss_between = float((counts * np.square(means - grand_mean)).sum())
        ms_within = ss_within / (n_ratings - n_blends)
        ms_between = ss_between / (n_blends - 1)
        variance_between = max(0.0, (ms_between - ms_within) / n0)
        variance_within = max(0.0, ms_within)
        total_component_variance = variance_between + variance_within
        icc = variance_between / total_component_variance if total_component_variance > 0 else None
        group_mean_reliability = [
            variance_between / (variance_between + variance_within / float(n))
            if variance_between + variance_within / float(n) > 0 else None
            for n in counts
        ]
        valid_reliability = [value for value in group_mean_reliability if value is not None]
        results[target] = {
            "grand_mean": grand_mean,
            "between_recipe_variance": float(variance_between),
            "within_recipe_rating_variance": float(variance_within),
            "between_recipe_variance_share": float(icc) if icc is not None else None,
            "within_recipe_variance_share": float(1 - icc) if icc is not None else None,
            "icc_method_of_moments": float(icc) if icc is not None else None,
            "mean_of_recipe_mean_reliability": float(np.mean(valid_reliability)) if valid_reliability else None,
            "ratings_per_recipe_mean": float(counts.mean()),
            "ratings_needed_for_mean_se_below_between_recipe_sd": (
                int(math.floor(variance_within / variance_between) + 1) if variance_between > 0 else None
            ),
            "ms_between": float(ms_between),
            "ms_within": float(ms_within),
        }
    return {
        "method": "unbalanced one-way random-effects ANOVA method of moments",
        "n_independent_recipes": int(n_blends),
        "n_rating_rows": int(n_ratings),
        "effective_group_size_n0": n0,
        "rating_counts_by_recipe": {str(code): int(count) for code, count in counts.items()},
        "targets": results,
        "interpretation_limit": "No rater IDs are available; within-recipe variance combines rater-to-rater spread, residual, and other within-recipe variation. It is not a pure measurement-error estimate.",
    }
