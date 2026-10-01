"""Clean and aggregate source observations without losing rating-level data."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .constants import (
    CHEMISTRY_ALL, CHEMISTRY_BASE, CHEMISTRY_RATIOS, DATA_VERSION, RATIO_FORMULAS,
    RAW_TO_CLEAN, RECIPE_FEATURES, RECIPE_G, SENSORY_TARGETS,
)
from .design_space import RecipeDesignSpace
from .io import sha256_file, utc_now, write_json
from .validation import assert_dataset_contract


def clean_observations(raw: pd.DataFrame) -> pd.DataFrame:
    assert_dataset_contract(raw)
    clean = raw.rename(columns=RAW_TO_CLEAN).copy()
    for column in clean.columns:
        if column != "sample_code":
            clean[column] = pd.to_numeric(clean[column], errors="raise")
    total = clean[RECIPE_G].sum(axis=1)
    for grams, ratio in zip(RECIPE_G, RECIPE_FEATURES):
        clean[ratio] = clean[grams] / total
    return clean


def build_datasets(raw: pd.DataFrame, source_path: str | Path, output_dir: str | Path) -> dict[str, Path]:
    clean = clean_observations(raw)
    static_fields = ["sample_code", *RECIPE_G, *RECIPE_FEATURES, *CHEMISTRY_ALL]
    master = clean.groupby("sample_code", sort=True, as_index=False)[static_fields[1:]].first()
    grouped = clean.groupby("sample_code", sort=True)
    for target in SENSORY_TARGETS:
        agg = grouped[target].agg(["mean", "std", "median"]).rename(
            columns={"mean": f"{target}_mean", "std": f"{target}_std", "median": f"{target}_median"}
        )
        master = master.merge(agg, left_on="sample_code", right_index=True, validate="one_to_one")
    master["n_ratings"] = grouped.size().reindex(master["sample_code"]).to_numpy()
    for ratio, (numerator, denominator) in RATIO_FORMULAS.items():
        safe_denominator = master[denominator].where(master[denominator].abs() > 1e-12)
        master[f"ratio_recomputed_{ratio}"] = master[numerator] / safe_denominator

    observation_columns = ["sample_code", *RECIPE_FEATURES, *CHEMISTRY_ALL, *SENSORY_TARGETS]
    sensory_observations = clean[observation_columns].copy()
    if len(master) != 30 or not master["sample_code"].is_unique:
        raise ValueError(f"M1 contract failed: expected 30 unique blend rows, got {len(master)}")
    if len(sensory_observations) != 597:
        raise ValueError(f"M1 contract failed: expected 597 rating rows, got {len(sensory_observations)}")
    if not np.allclose(master[RECIPE_FEATURES].sum(axis=1), 1.0, atol=1e-10):
        raise ValueError("M1 contract failed: recipe proportions do not sum to 1")
    for ratio in RATIO_FORMULAS:
        if not np.allclose(master[ratio], master[f"ratio_recomputed_{ratio}"], rtol=1e-6, atol=1e-8):
            raise ValueError(f"M1 contract failed: derived ratio does not match formula: {ratio}")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {
        "clean": out / "teabiosens_clean.csv",
        "master": out / "blend_master.csv",
        "sensory": out / "sensory_observations.csv",
        "manifest": out / "dataset_manifest.json",
    }
    clean.to_csv(paths["clean"], index=False)
    master.to_csv(paths["master"], index=False)
    sensory_observations.to_csv(paths["sensory"], index=False)
    design = RecipeDesignSpace(master)
    manifest = {
        "source_file": str(Path(source_path)),
        "source_sha256": sha256_file(source_path),
        "generated_at_utc": utc_now(),
        "source_sheet": "Sheet1",
        "source_rows": int(len(raw)),
        "source_columns": int(len(raw.columns)),
        "unique_sample_codes": int(clean["sample_code"].nunique()),
        "sample_codes": sorted(clean["sample_code"].unique().tolist()),
        "sample_rating_counts": {str(key): int(value) for key, value in clean["sample_code"].value_counts().sort_index().items()},
        "design_space": design.describe(),
        "data_version": DATA_VERSION,
        "random_state": 42,
        "outputs": {
            name: {"path": path.name, "rows": int(count), "columns": list(frame.columns)}
            for name, path, count, frame in [
                ("teabiosens_clean", paths["clean"], len(clean), clean),
                ("blend_master", paths["master"], len(master), master),
                ("sensory_observations", paths["sensory"], len(sensory_observations), sensory_observations),
            ]
        },
        "chemistry_base_fields": CHEMISTRY_BASE,
        "chemistry_ratio_fields": CHEMISTRY_RATIOS,
        "sensory_fields": SENSORY_TARGETS,
    }
    write_json(paths["manifest"], manifest)
    return paths
