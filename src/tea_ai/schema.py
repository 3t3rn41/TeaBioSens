"""Configurable N-ingredient composition schema and TeaBioSens adapter."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Iterable, Mapping

import numpy as np
import yaml


@dataclass(frozen=True)
class RecipeSchema:
    ingredient_keys: tuple[str, ...]
    mass_columns: tuple[str, ...]
    proportion_columns: tuple[str, ...]
    allowed_mass_levels: tuple[tuple[float, ...], ...]
    total_mass: float
    mass_unit: str = "g"

    def __post_init__(self):
        n = len(self.ingredient_keys)
        if n < 1 or len(self.mass_columns) != n or len(self.proportion_columns) != n or len(self.allowed_mass_levels) != n:
            raise ValueError("Ingredient, mass, proportion, and level definitions must have the same non-zero length")
        if self.total_mass <= 0 or any(not levels for levels in self.allowed_mass_levels):
            raise ValueError("Recipe schema needs a positive total and at least one level per ingredient")
        for field in (self.ingredient_keys, self.mass_columns, self.proportion_columns):
            if len(set(field)) != n:
                raise ValueError("Recipe schema ingredient keys and column names must be unique")
        if any(not np.isfinite(level) or level < 0 for levels in self.allowed_mass_levels for level in levels):
            raise ValueError("Allowed ingredient masses must be finite and non-negative")

    @property
    def n_ingredients(self) -> int:
        return len(self.ingredient_keys)

    def enumerate_valid_points(self, atol: float = 1e-9) -> set[tuple[float, ...]]:
        return {
            tuple(float(value) for value in values)
            for values in product(*self.allowed_mass_levels)
            if np.isclose(sum(values), self.total_mass, atol=atol)
        }

    def validate_masses(self, values: Iterable[float], atol: float = 1e-8) -> np.ndarray:
        vector = np.asarray(list(values), dtype=float)
        if vector.shape != (self.n_ingredients,) or not np.isfinite(vector).all():
            raise ValueError(f"Recipe must contain {self.n_ingredients} finite ingredient amounts")
        if (vector < -atol).any() or not np.isclose(vector.sum(), self.total_mass, atol=atol):
            raise ValueError(f"Recipe amounts must be non-negative and sum to {self.total_mass:g} {self.mass_unit}")
        return np.clip(vector, 0, None)

    def validate_proportions(self, values: Iterable[float], atol: float = 1e-6) -> np.ndarray:
        vector = np.asarray(list(values), dtype=float)
        if vector.shape != (self.n_ingredients,) or not np.isfinite(vector).all():
            raise ValueError(f"Recipe must contain {self.n_ingredients} finite proportions")
        if (vector < -atol).any() or not np.isclose(vector.sum(), 1.0, atol=atol):
            raise ValueError("Recipe proportions must be non-negative and sum to 1.0")
        return np.clip(vector, 0, 1)

    def to_proportions(self, masses: Iterable[float]) -> np.ndarray:
        return self.validate_masses(masses) / self.total_mass

    def in_allowed_design(self, values: Iterable[float], atol: float = 1e-8) -> bool:
        vector = np.asarray(list(values), dtype=float)
        if vector.shape != (self.n_ingredients,) or not np.isfinite(vector).all():
            return False
        return any(np.allclose(vector, point, atol=atol, rtol=0) for point in self.enumerate_valid_points())

    def recipe_mapping(self, values: Iterable[float], proportions: bool = False) -> dict[str, float]:
        vector = np.asarray(list(values), dtype=float)
        keys = self.proportion_columns if proportions else self.mass_columns
        if vector.shape != (self.n_ingredients,):
            raise ValueError(f"Expected {self.n_ingredients} values")
        return dict(zip(keys, vector.astype(float).tolist()))


def recipe_schema_from_mapping(config: Mapping) -> RecipeSchema:
    """Build an N-dimensional recipe adapter from YAML/JSON-like configuration."""
    ingredients = config["ingredients"]
    return RecipeSchema(
        ingredient_keys=tuple(str(item["key"]) for item in ingredients),
        mass_columns=tuple(str(item["mass_column"]) for item in ingredients),
        proportion_columns=tuple(str(item["proportion_column"]) for item in ingredients),
        allowed_mass_levels=tuple(tuple(float(value) for value in item["levels"]) for item in ingredients),
        total_mass=float(config["total_mass"]),
        mass_unit=str(config.get("mass_unit", "g")),
    )


_CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs/feature_schema.yaml"
if _CONFIG_PATH.exists():
    _CONFIG = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
    TEABIOSENS_RECIPE_SCHEMA = recipe_schema_from_mapping(_CONFIG["recipe_design"])
else:
    # Package fallback; the checked-in YAML remains the project source of truth.
    TEABIOSENS_RECIPE_SCHEMA = RecipeSchema(
        ingredient_keys=("green", "white", "oolong", "black"),
        mass_columns=("green_g", "white_g", "oolong_g", "black_g"),
        proportion_columns=("green_pct", "white_pct", "oolong_pct", "black_pct"),
        allowed_mass_levels=((0.5, 1.0, 1.5, 2.0), (0.5, 1.0, 1.5, 2.0), (0.5, 1.0, 1.5, 2.0), (0.5, 1.0, 1.5, 2.0, 2.5)),
        total_mass=4.0,
    )
