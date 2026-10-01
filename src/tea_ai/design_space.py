"""The project's finite 32-point, 4 g recipe design space."""

from __future__ import annotations

from itertools import product
from typing import Iterable

import numpy as np
import pandas as pd

from .constants import RECIPE_FEATURES

GREEN_LEVELS = (0.5, 1.0, 1.5, 2.0)
WHITE_LEVELS = (0.5, 1.0, 1.5, 2.0)
OOLONG_LEVELS = (0.5, 1.0, 1.5, 2.0)
BLACK_LEVELS = (0.5, 1.0, 1.5, 2.0, 2.5)
TOTAL_MASS_G = 4.0
DESIGN_COLUMNS_G = ["green_g", "white_g", "oolong_g", "black_g"]


def enumerate_valid_design_points() -> set[tuple[float, float, float, float]]:
    """Enumerate combinations from the documented weighing levels and fixed total."""
    levels = (GREEN_LEVELS, WHITE_LEVELS, OOLONG_LEVELS, BLACK_LEVELS)
    return {
        tuple(float(value) for value in point)
        for point in product(*levels)
        if np.isclose(sum(point), TOTAL_MASS_G, atol=1e-9)
    }


def extract_observed_recipe_points(frame: pd.DataFrame) -> set[tuple[float, float, float, float]]:
    points = frame[DESIGN_COLUMNS_G].drop_duplicates().to_numpy(dtype=float)
    return {tuple(float(value) for value in row) for row in points}


def classify_design_point(recipe_g: Iterable[float], observed_points: set[tuple[float, ...]], atol: float = 1e-8) -> str:
    point = np.asarray(list(recipe_g), dtype=float)
    if point.shape != (4,) or not np.isfinite(point).all():
        return "INVALID_DESIGN_POINT"
    if not np.isclose(point.sum(), TOTAL_MASS_G, atol=atol):
        return "INVALID_DESIGN_POINT"
    if not any(np.allclose(point, known, atol=atol, rtol=0) for known in enumerate_valid_design_points()):
        return "INVALID_DESIGN_POINT"
    if any(np.allclose(point, known, atol=atol, rtol=0) for known in observed_points):
        return "OBSERVED"
    return "UNOBSERVED_VALID"


class RecipeDesignSpace:
    def __init__(self, blend_master: pd.DataFrame):
        self.master = blend_master.copy()
        self.points = enumerate_valid_design_points()
        self.observed_points = extract_observed_recipe_points(self.master)
        if len(self.points) != 32:
            raise ValueError(f"Expected 32 legal design points, enumerated {len(self.points)}")
        if len(self.observed_points) != 30:
            raise ValueError(f"Expected 30 observed recipe points, found {len(self.observed_points)}")
        if not self.observed_points <= self.points:
            raise ValueError("Observed recipes include points outside the defined discrete design")
        self.missing_points = self.points - self.observed_points
        self.observed = {
            tuple(float(v) for v in row[DESIGN_COLUMNS_G]): row
            for _, row in self.master.set_index("sample_code").iterrows()
        }
        self.observed_codes = list(self.master["sample_code"].astype(str))
        self.observed_matrix_g = self.master[DESIGN_COLUMNS_G].to_numpy(dtype=float)
        self.observed_matrix_pct = self.master[RECIPE_FEATURES].to_numpy(dtype=float)

    @property
    def coverage(self) -> float:
        return len(self.observed_points) / len(self.points)

    def recipe_status(self, recipe_g, atol: float = 1e-8) -> str:
        return classify_design_point(recipe_g, self.observed_points, atol=atol)

    def nearest(self, recipe_g, k: int = 3) -> list[dict]:
        point = np.asarray(recipe_g, dtype=float).reshape(1, 4)
        distances = np.linalg.norm(self.observed_matrix_g - point, axis=1)
        order = np.argsort(distances, kind="stable")[: max(0, min(k, len(distances)))]
        result = []
        for index in order:
            measured = self.observed_matrix_g[index]
            result.append({
                "sample_code": self.observed_codes[index],
                "distance_g_euclidean": float(distances[index]),
                "recipe_delta_g": (point[0] - measured).tolist(),
            })
        return result

    def describe(self) -> dict:
        return {
            "valid_point_count": len(self.points),
            "observed_point_count": len(self.observed_points),
            "unobserved_valid_count": len(self.missing_points),
            "coverage": self.coverage,
            "unobserved_points_g": [list(point) for point in sorted(self.missing_points)],
        }

