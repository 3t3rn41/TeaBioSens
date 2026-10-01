from pathlib import Path

import numpy as np
import pandas as pd

from tea_ai.constants import RECIPE_FEATURES, SENSORY_TARGETS
from tea_ai.design_space import RecipeDesignSpace
from tea_ai.optimization import rank_design_space


class FakePredictor:
    def __init__(self):
        root = Path(__file__).resolve().parents[1]
        self.design_space = RecipeDesignSpace(pd.read_csv(root / "data/processed/blend_master.csv"))
        self.chemistry_metrics = {"by_target": {}}
        self.direct_metrics = {"gate": {"status": "PASS"}}

    def predict_recipe(self, recipe_pct):
        recipe = np.asarray(recipe_pct)
        grams = recipe * 4.0
        status = self.design_space.recipe_status(grams)
        score = float(60 + recipe[0] * 20 + recipe[3] * 10)
        sensory = {name: score - i for i, name in enumerate(SENSORY_TARGETS)}
        distance = self.design_space.nearest(grams, k=3)
        return {
            "recipe_pct": dict(zip(RECIPE_FEATURES, recipe)),
            "design_status": status,
            "path_a_sensory": sensory,
            "path_b_sensory": sensory,
            "path_b_uncertainty": {name: 1.0 for name in SENSORY_TARGETS},
            "model_disagreement_by_target": {name: 0.0 for name in SENSORY_TARGETS},
            "predicted_chemistry": {"protein_ug_g": 1.0},
            "nearest_samples": distance,
        }


def test_ranker_returns_all_points_and_two_experiments_reproducibly(tmp_path):
    first = rank_design_space(FakePredictor(), top_k=10, output_dir=tmp_path / "a")
    second = rank_design_space(FakePredictor(), top_k=10, output_dir=tmp_path / "b")
    assert len(first["table"]) == 32
    assert len(first["next_experiments"]) == 2
    assert first["summary"]["coverage"] == 0.9375
    assert first["top_candidates"]["evidence_type"].isin(["MEASURED", "PREDICTED"]).all()
    recipes = first["top_candidates"][RECIPE_FEATURES].to_numpy()
    for i in range(len(recipes)):
        for j in range(i):
            assert np.max(np.abs(recipes[i] - recipes[j])) >= 0.05
    pd.testing.assert_frame_equal(first["table"], second["table"])
    assert (tmp_path / "a/design_space_32.csv").exists()
    assert (tmp_path / "a/next_experiments.csv").exists()
