"""Raw dataset audit and reusable data contract checks."""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
import pandas as pd

from .constants import CHEMISTRY_ALL, RAW_TO_CLEAN, RECIPE_G, SAMPLE_COUNTS, SENSORY_TARGETS
from .design_space import enumerate_valid_design_points, extract_observed_recipe_points


def audit_dataframe(df: pd.DataFrame, sheet_name: str = "Sheet1") -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    expected = list(RAW_TO_CLEAN)
    missing_columns = [name for name in expected if name not in df.columns]
    extra_columns = [str(name) for name in df.columns if name not in expected]
    if missing_columns:
        errors.append(f"Missing required columns: {missing_columns}")
    if extra_columns:
        warnings.append(f"Unexpected columns: {extra_columns}")
    if sheet_name != "Sheet1":
        errors.append(f"Expected worksheet Sheet1, got {sheet_name}")

    counts = df["Sample code"].astype(str).value_counts().sort_index().to_dict() if "Sample code" in df else {}
    if len(df) != 597:
        errors.append(f"Expected 597 observations, got {len(df)}")
    if len(df.columns) != 30:
        errors.append(f"Expected 30 columns, got {len(df.columns)}")
    if set(map(str, counts)) != set(SAMPLE_COUNTS):
        errors.append("Sample codes must be S1-S30")
    for sample_code, expected_count in SAMPLE_COUNTS.items():
        actual = counts.get(sample_code)
        if actual != expected_count:
            errors.append(f"{sample_code} expected {expected_count} rows, got {actual}")

    missing_total = int(df.isna().sum().sum())
    if missing_total:
        errors.append(f"Found {missing_total} missing values")
    numeric_columns = [column for column in expected if column != "Sample code"]
    non_numeric = []
    numeric = df[numeric_columns].apply(pd.to_numeric, errors="coerce") if not missing_columns else pd.DataFrame()
    if not numeric.empty:
        for col in numeric_columns:
            if numeric[col].isna().any():
                non_numeric.append(col)
        if non_numeric:
            errors.append(f"Non-numeric or missing values in numeric columns: {non_numeric}")
        values = numeric.to_numpy(dtype=float)
        if not np.isfinite(values).all():
            errors.append("Numeric columns contain Inf or -Inf")

    duplicate_rows = int(df.duplicated().sum())
    if duplicate_rows:
        warnings.append(f"{duplicate_rows} exact duplicate rating row(s); retained as supplied")

    if all(col in df for col in RECIPE_G_RAW):
        recipe_sum = df[RECIPE_G_RAW].apply(pd.to_numeric, errors="coerce").sum(axis=1)
        if (df[RECIPE_G_RAW].apply(pd.to_numeric, errors="coerce") < 0).any().any():
            errors.append("Recipe ingredients must be non-negative")
        bad_sum = ~np.isclose(recipe_sum.to_numpy(), 4.0, atol=1e-8)
        if bad_sum.any():
            errors.append(f"{int(bad_sum.sum())} recipe rows do not sum to 4.0 g")
        per_sample_recipe = df.groupby("Sample code")[RECIPE_G_RAW].nunique(dropna=False)
        if (per_sample_recipe > 1).any().any():
            errors.append("Recipe varies within one Sample code")
        clean_recipe_frame = df.rename(columns=RAW_TO_CLEAN)
        valid_points = enumerate_valid_design_points()
        observed_points = extract_observed_recipe_points(clean_recipe_frame)
        missing_points = valid_points - observed_points
        expected_missing = {
            (0.5, 1.0, 1.5, 1.0),
            (0.5, 1.5, 0.5, 1.5),
        }
        if len(valid_points) != 32:
            errors.append(f"Expected exactly 32 enumerated legal design points, got {len(valid_points)}")
        if len(observed_points) != 30:
            errors.append(f"Expected exactly 30 observed recipe points, got {len(observed_points)}")
        if missing_points != expected_missing:
            errors.append(f"Unexpected unobserved valid design points: {sorted(missing_points)}")
        if valid_points and not np.isclose(len(observed_points) / len(valid_points), 0.9375):
            errors.append("Observed design-space coverage is not 93.75%")
        design_space = {
            "valid_point_count": len(valid_points),
            "observed_point_count": len(observed_points),
            "coverage": len(observed_points) / len(valid_points) if valid_points else 0.0,
            "unobserved_points_g": [list(point) for point in sorted(missing_points)],
        }
    else:
        design_space = None

    chemistry_raw = [key for key, value in RAW_TO_CLEAN.items() if value in CHEMISTRY_ALL]
    if all(col in df for col in chemistry_raw):
        static = df.groupby("Sample code")[chemistry_raw].nunique(dropna=False)
        inconsistent = static.columns[(static > 1).any()].tolist()
        if inconsistent:
            errors.append(f"Chemistry varies within sample: {inconsistent}")

    sensory_raw = [key for key, value in RAW_TO_CLEAN.items() if value in SENSORY_TARGETS]
    if all(col in df for col in sensory_raw):
        sensory = df[sensory_raw].apply(pd.to_numeric, errors="coerce")
        outside = ((sensory < 0) | (sensory > 100)).any()
        if outside.any():
            errors.append(f"Sensory scores outside [0, 100]: {outside[outside].index.tolist()}")

    ratio_checks = {}
    if not missing_columns:
        clean = df.rename(columns=RAW_TO_CLEAN)
        formulas = {
            "tp_theanine": ("tp_mggae_g", "l_theanine_mg_g"),
            "caf_tp": ("caffeine_pct", "tp_mggae_g"),
            "protein_tp": ("protein_ug_g", "tp_mggae_g"),
            "tf_tr": ("tf_pct", "tr_pct"),
        }
        for ratio, (numerator, denominator) in formulas.items():
            expected_ratio = clean[numerator] / clean[denominator]
            difference = np.abs(clean[ratio] - expected_ratio)
            max_diff = float(difference.max())
            ratio_checks[ratio] = {"max_abs_difference": max_diff, "allclose": bool(np.allclose(clean[ratio], expected_ratio, rtol=1e-6, atol=1e-8))}
            if not ratio_checks[ratio]["allclose"]:
                errors.append(f"Ratio formula mismatch: {ratio} (max abs diff {max_diff:g})")

    numeric_stats = {}
    if not numeric.empty:
        numeric_stats = {
            col: {"min": float(numeric[col].min()), "max": float(numeric[col].max()), "mean": float(numeric[col].mean())}
            for col in sensory_raw
        }
    return {
        "status": "FAIL" if errors else ("PASS_WITH_WARNINGS" if warnings else "PASS"),
        "sheet": sheet_name,
        "rows_with_header": int(len(df) + 1),
        "data_rows": int(len(df)),
        "columns": int(len(df.columns)),
        "unique_sample_codes": int(df["Sample code"].nunique()) if "Sample code" in df else 0,
        "sample_counts": counts,
        "missing_values": missing_total,
        "exact_duplicate_rows": duplicate_rows,
        "recipe_total_g": {"min": float(df[RECIPE_G_RAW].apply(pd.to_numeric).sum(axis=1).min()), "max": float(df[RECIPE_G_RAW].apply(pd.to_numeric).sum(axis=1).max())} if all(c in df for c in RECIPE_G_RAW) else None,
        "ratio_checks": ratio_checks,
        "design_space": design_space,
        "sensory_summary": numeric_stats,
        "errors": errors,
        "warnings": warnings,
    }


RECIPE_G_RAW = ["Green tea", "White tea", "Oolong tea", "Black tea"]


def assert_dataset_contract(df: pd.DataFrame) -> None:
    report = audit_dataframe(df)
    if report["errors"]:
        raise ValueError("Dataset contract failed: " + "; ".join(report["errors"]))
