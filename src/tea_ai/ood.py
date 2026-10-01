"""Convex-hull and empirical nearest-neighbour domain checks."""

from __future__ import annotations

import numpy as np
from scipy.spatial import ConvexHull, QhullError
from sklearn.neighbors import NearestNeighbors

from .constants import RECIPE_FEATURES


class RecipeDomain:
    def __init__(self, recipes, sample_codes=None):
        matrix = np.asarray(recipes, dtype=float)
        if matrix.ndim != 2 or matrix.shape[1] != 4 or len(matrix) < 4:
            raise ValueError("Recipe domain requires at least four four-part recipes")
        self.recipes = matrix
        self.xyz = matrix[:, :3]
        self.sample_codes = np.asarray(sample_codes if sample_codes is not None else [f"S{i+1}" for i in range(len(matrix))])
        self.hull = None
        try:
            self.hull = ConvexHull(self.xyz)
        except QhullError:
            # The optimizer is deliberately limited to a low-dimensional compositional space.
            # A failed hull here signals data geometry that cannot support a 3-D hull check.
            self.hull = None
        nearest = NearestNeighbors(n_neighbors=2).fit(self.recipes)
        distances, _ = nearest.kneighbors(self.recipes)
        empirical = distances[:, 1]
        self.neighbor_threshold = float(np.quantile(empirical, 0.90))
        self.edge_threshold = float(max(self.neighbor_threshold * 2.0, self.neighbor_threshold + 1e-12))

    def inside_hull(self, recipes, tolerance: float = 1e-9) -> np.ndarray:
        matrix = np.asarray(recipes, dtype=float)
        if matrix.ndim == 1:
            matrix = matrix.reshape(1, -1)
        if self.hull is None:
            return np.zeros(len(matrix), dtype=bool)
        equations = self.hull.equations
        # scipy uses A*x + b <= 0 for points inside the hull.
        return np.all(matrix[:, :3] @ equations[:, :-1].T + equations[:, -1] <= tolerance, axis=1)

    def inspect(self, recipe) -> dict:
        matrix = np.asarray(recipe, dtype=float).reshape(1, -1)
        inside = bool(self.inside_hull(matrix)[0])
        distances = np.linalg.norm(self.recipes - matrix, axis=1)
        index = int(np.argmin(distances))
        distance = float(distances[index])
        if not inside:
            status = "OUT_OF_DOMAIN"
        elif distance > self.neighbor_threshold:
            status = "NEAR_EDGE"
        else:
            status = "IN_DOMAIN"
        return {
            "inside_hull": inside,
            "ood_status": status,
            "nearest_sample_code": str(self.sample_codes[index]),
            "nearest_distance": distance,
            "neighbor_threshold_p90": self.neighbor_threshold,
        }

