from pathlib import Path

import numpy as np
import pandas as pd

from tea_ai.design_space import enumerate_valid_design_points, extract_observed_recipe_points
from tea_ai.validation import assert_dataset_contract, audit_dataframe

ROOT = Path(__file__).resolve().parents[1]


def test_source_dataset_contract_and_design_space():
    raw = pd.read_excel(ROOT / "data/raw/TeaBioSens.xlsx", sheet_name="Sheet1")
    assert_dataset_contract(raw)
    assert len(raw) == 597
    assert raw.shape[1] == 30
    assert raw["Sample code"].nunique() == 30
    assert raw.isna().sum().sum() == 0
    counts = raw["Sample code"].value_counts()
    assert all(counts[f"S{i}"] == 20 for i in range(1, 30))
    assert counts["S30"] == 17
    assert np.allclose(raw[["Green tea", "White tea", "Oolong tea", "Black tea"]].sum(axis=1), 4.0)
    report = audit_dataframe(raw)
    assert report["status"] == "PASS_WITH_WARNINGS"
    assert len(enumerate_valid_design_points()) == 32
    observed = extract_observed_recipe_points(raw.rename(columns={"Green tea": "green_g", "White tea": "white_g", "Oolong tea": "oolong_g", "Black tea": "black_g"}))
    assert len(observed) == 30
    assert len(enumerate_valid_design_points() - observed) == 2


def test_processed_dataset_row_contract():
    master = pd.read_csv(ROOT / "data/processed/blend_master.csv")
    observations = pd.read_csv(ROOT / "data/processed/sensory_observations.csv")
    clean = pd.read_csv(ROOT / "data/processed/teabiosens_clean.csv")
    assert len(master) == 30 and master["sample_code"].is_unique
    assert len(observations) == 597 and len(clean) == 597
    assert np.allclose(master[["green_pct", "white_pct", "oolong_pct", "black_pct"]].sum(axis=1), 1.0)

