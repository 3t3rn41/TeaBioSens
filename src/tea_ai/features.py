"""Feature validation and compositional recipe helpers."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from .constants import RECIPE_FEATURES


def validate_recipe(recipe: Mapping[str, float] | list[float] | tuple[float, ...], atol: float = 1e-6) -> np.ndarray:
    if isinstance(recipe, Mapping):
        values = np.asarray([recipe[name] for name in RECIPE_FEATURES], dtype=float)
    else:
        values = np.asarray(recipe, dtype=float)
    if values.shape != (4,):
        raise ValueError("Recipe must contain four proportions in green, white, oolong, black order")
    if not np.isfinite(values).all():
        raise ValueError("Recipe proportions must be finite")
    if (values < -atol).any():
        raise ValueError("Recipe proportions must be non-negative")
    if not np.isclose(values.sum(), 1.0, atol=atol):
        raise ValueError(f"Recipe proportions must sum to 1.0; got {values.sum():.10g}")
    return np.clip(values, 0, 1)


def recipe_frame(recipes: np.ndarray) -> pd.DataFrame:
    matrix = np.asarray(recipes, dtype=float)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    if matrix.shape[1] != len(RECIPE_FEATURES):
        raise ValueError("Expected four recipe features")
    return pd.DataFrame(matrix, columns=RECIPE_FEATURES)


def recompute_ratios(chemistry: Mapping[str, float], epsilon: float = 1e-12) -> dict[str, float]:
    definitions = {
        "tp_theanine": ("tp_mggae_g", "l_theanine_mg_g"),
        "caf_tp": ("caffeine_pct", "tp_mggae_g"),
        "protein_tp": ("protein_ug_g", "tp_mggae_g"),
        "tf_tr": ("tf_pct", "tr_pct"),
    }
    ratios: dict[str, float] = {}
    for ratio, (numerator, denominator) in definitions.items():
        divisor = float(chemistry[denominator])
        ratios[ratio] = float(chemistry[numerator]) / divisor if abs(divisor) > epsilon else float("nan")
    return ratios

