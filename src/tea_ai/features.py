"""Feature validation and compositional recipe helpers."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from .constants import RECIPE_FEATURES
from .schema import TEABIOSENS_RECIPE_SCHEMA


def validate_composition(recipe: Mapping[str, float] | list[float] | tuple[float, ...], feature_order, total: float = 1.0, atol: float = 1e-6) -> np.ndarray:
    """Validate an N-part composition when its ordered feature schema is supplied."""
    if isinstance(recipe, Mapping):
        values = np.asarray([recipe[name] for name in feature_order], dtype=float)
    else:
        values = np.asarray(recipe, dtype=float)
    if values.shape != (len(feature_order),) or not np.isfinite(values).all():
        raise ValueError(f"Composition must contain {len(feature_order)} finite values")
    if (values < -atol).any() or not np.isclose(values.sum(), total, atol=atol):
        raise ValueError(f"Composition values must be non-negative and sum to {total:g}")
    return np.clip(values, 0, total)


def validate_recipe(recipe: Mapping[str, float] | list[float] | tuple[float, ...], atol: float = 1e-6) -> np.ndarray:
    return validate_composition(recipe, RECIPE_FEATURES, total=1.0, atol=atol)


def recipe_frame(recipes: np.ndarray, feature_order=None) -> pd.DataFrame:
    matrix = np.asarray(recipes, dtype=float)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    columns = list(feature_order or RECIPE_FEATURES)
    if matrix.shape[1] != len(columns):
        raise ValueError(f"Expected {len(columns)} recipe features")
    return pd.DataFrame(matrix, columns=columns)


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
