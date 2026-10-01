from pathlib import Path

import numpy as np
import pytest

from tea_ai.inference import TeaPredictor

ROOT = Path(__file__).resolve().parents[1]
READY = all((ROOT / f"artifacts/models/{name}/model.joblib").exists() for name in ["chemistry", "sensory", "direct_recipe"])


@pytest.mark.skipif(not READY, reason="Run scripts/07_run_full_pipeline.py to create inference artifacts")
def test_same_saved_models_and_input_are_reproducible():
    predictor = TeaPredictor(ROOT)
    known = predictor.design_space.master.iloc[0]
    recipe = known[["green_pct", "white_pct", "oolong_pct", "black_pct"]].to_numpy(dtype=float)
    a = predictor.predict_recipe(recipe)
    b = predictor.predict_recipe(recipe)
    assert a["design_status"] == "OBSERVED"
    assert a["path_b_sensory"] == b["path_b_sensory"]
    assert a["predicted_chemistry"] == b["predicted_chemistry"]

