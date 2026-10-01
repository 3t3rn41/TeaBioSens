from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def test_selected_model_oof_error_artifact_covers_all_three_tasks():
    path = ROOT / "artifacts/predictions/prediction_error_by_sample.csv"
    assert path.exists(), "Run scripts/07_run_full_pipeline.py to generate selected OOF error rows"
    frame = pd.read_csv(path)
    assert {"task", "sample_code", "target", "y_true", "y_pred", "abs_error", "signed_error"} <= set(frame.columns)
    assert set(frame["task"]) == {"recipe_to_chemistry", "chemistry_to_sensory", "recipe_to_sensory"}
    assert frame.groupby(["task", "target"]).size().eq(30).all()
    assert frame[["y_true", "y_pred", "abs_error", "signed_error"]].notna().all().all()

