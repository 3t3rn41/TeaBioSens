#!/usr/bin/env python3
"""Permutation and fold-influence checks for the direct Recipe -> Sensory gate."""

from __future__ import annotations

import argparse
import json
import math
import os
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest
from sklearn.exceptions import ConvergenceWarning
from threadpoolctl import threadpool_limits

from _common import ROOT
from tea_ai.constants import LINEAR_RECIPE_FEATURES, RECIPE_FEATURES, SENSORY_TARGETS
from tea_ai.metrics import regression_metrics
from tea_ai.models.common import candidate_estimators
from tea_ai.cv import leave_one_out

warnings.filterwarnings("ignore", category=ConvergenceWarning)

_X_ALL = None
_X_LINEAR = None
_Y = None
_TARGETS = None
_FOLDS = None
_FAMILIES = None
_SPECS = None
_THREADPOOL_LIMITER = None


def _init_worker(root_path: str):
    global _X_ALL, _X_LINEAR, _Y, _TARGETS, _FOLDS, _FAMILIES, _SPECS, _THREADPOOL_LIMITER
    _THREADPOOL_LIMITER = threadpool_limits(limits=1)
    root = Path(root_path)
    frame = pd.read_csv(root / "data/processed/blend_master.csv")
    _X_ALL = frame[RECIPE_FEATURES]
    _X_LINEAR = frame[LINEAR_RECIPE_FEATURES]
    _TARGETS = list(SENSORY_TARGETS)
    _Y = frame[[f"{name}_mean" for name in _TARGETS]].to_numpy(dtype=float)
    _FOLDS = list(leave_one_out(len(frame)))
    optional = candidate_estimators(4)
    _SPECS = {
        "ridge_a": ("ridge", _X_LINEAR),
        "pls": ("pls", _X_ALL),
        "gpr": ("gpr", _X_ALL),
        "random_forest": ("random_forest", _X_ALL),
    }
    for family in ("xgboost", "catboost"):
        if family in optional:
            _SPECS[family] = (family, _X_ALL)
    _FAMILIES = list(_SPECS)


def _score(y: np.ndarray, prediction: np.ndarray) -> tuple[float, float]:
    error = np.asarray(prediction, dtype=float) - np.asarray(y, dtype=float)
    return float(np.mean(np.abs(error))), float(np.sqrt(np.mean(np.square(error))))


def _one_permutation(task: tuple[int, list[int]]) -> dict:
    permutation_id, row_order = task
    y_matrix = _Y[np.asarray(row_order, dtype=int)]
    predictions = {
        target: {family: np.full(len(_Y), np.nan) for family in _FAMILIES}
        for target in _TARGETS
    }
    baselines = {target: np.full(len(_Y), np.nan) for target in _TARGETS}

    for train_idx, test_idx in _FOLDS:
        estimators = candidate_estimators(4)
        for j, target in enumerate(_TARGETS):
            y = y_matrix[:, j]
            baselines[target][test_idx] = float(np.mean(y[train_idx]))
            for family, (estimator_name, X) in _SPECS.items():
                estimator = estimators[estimator_name]
                estimator.fit(X.iloc[train_idx], y[train_idx])
                predictions[target][family][test_idx] = np.asarray(
                    estimator.predict(X.iloc[test_idx]), dtype=float,
                ).reshape(-1)

    improved = {}
    selected = {}
    for j, target in enumerate(_TARGETS):
        y = y_matrix[:, j]
        baseline_mae, baseline_rmse = _score(y, baselines[target])
        model_scores = {
            family: _score(y, predictions[target][family])
            for family in _FAMILIES
        }
        passing = [
            name for name, (mae, rmse) in model_scores.items()
            if mae < baseline_mae and rmse < baseline_rmse
        ]
        # Match train_direct_recipe_sensory(): for Overall score, prefer a
        # baseline-beating candidate if one exists; for other targets choose
        # the lowest-MAE family, then recompute the simultaneous-pass event.
        pool = passing if target == "overall_score" and passing else _FAMILIES
        chosen = min(pool, key=lambda name: model_scores[name])
        selected[target] = chosen
        mae, rmse = model_scores[chosen]
        improved[target] = mae < baseline_mae and rmse < baseline_rmse

    return {
        "permutation_id": int(permutation_id),
        "n_targets_improved": int(sum(improved.values())),
        "all_six_improved": bool(all(improved.values())),
        "gate_b_overall_pass": bool(improved["overall_score"]),
        **{f"improved_{target}": bool(value) for target, value in improved.items()},
        **{f"selected_{target}": name for target, name in selected.items()},
    }


def _fold_sensitivity(root: Path, out_dir: Path) -> dict:
    metrics = json.loads((root / "artifacts/reports/recipe_sensory_metrics.json").read_text(encoding="utf-8"))
    oof = pd.read_csv(root / "artifacts/predictions/recipe_sensory_oof.csv")
    fold_rows = []
    deletion_rows = []
    summaries = {}

    for target in SENSORY_TARGETS:
        chosen = metrics["by_target"][target]["selected_model"]
        rows = oof[oof["target"] == target]
        selected = rows[rows["model"] == chosen].set_index("sample_code").sort_index()
        baseline = rows[rows["model"] == "mean"].set_index("sample_code").sort_index()
        if selected.index.tolist() != baseline.index.tolist() or len(selected) != 30:
            raise ValueError(f"Expected matched 30-fold OOF predictions for {target}")

        y = selected["y_true"].to_numpy(dtype=float)
        pred = selected["y_pred"].to_numpy(dtype=float)
        base_pred = baseline["y_pred"].to_numpy(dtype=float)
        abs_err = np.abs(y - pred)
        base_abs_err = np.abs(y - base_pred)
        sq_gain = np.square(y - base_pred) - np.square(y - pred)
        abs_gain = base_abs_err - abs_err
        selected_metrics = regression_metrics(y, pred)
        baseline_metrics = regression_metrics(y, base_pred)

        for i, code in enumerate(selected.index):
            fold_rows.append({
                "target": target,
                "sample_code": code,
                "selected_model": chosen,
                "y_true": y[i],
                "y_pred": pred[i],
                "baseline_pred": base_pred[i],
                "abs_error": abs_err[i],
                "baseline_abs_error": base_abs_err[i],
                "absolute_error_gain_vs_mean": abs_gain[i],
                "squared_error_gain_vs_mean": sq_gain[i],
                "fold_mae_win": bool(abs_err[i] < base_abs_err[i]),
                "fold_squared_error_win": bool(sq_gain[i] > 0),
            })
            mask = np.arange(len(y)) != i
            model_without_fold = regression_metrics(y[mask], pred[mask])
            baseline_without_fold = regression_metrics(y[mask], base_pred[mask])
            deletion_rows.append({
                "target": target,
                "excluded_sample_code": code,
                "model_mae": model_without_fold["mae"],
                "baseline_mae": baseline_without_fold["mae"],
                "model_rmse": model_without_fold["rmse"],
                "baseline_rmse": baseline_without_fold["rmse"],
                "both_metrics_still_improve": bool(
                    model_without_fold["mae"] < baseline_without_fold["mae"]
                    and model_without_fold["rmse"] < baseline_without_fold["rmse"]
                ),
            })

        positive_gain = np.sort(np.maximum(sq_gain, 0.0))[::-1]
        positive_total = float(positive_gain.sum())
        top3_share = float(positive_gain[:3].sum() / positive_total) if positive_total else None
        dropped = [row for row in deletion_rows if row["target"] == target]
        summaries[target] = {
            "selected_model": chosen,
            "n_folds": len(y),
            "oof_mae": selected_metrics["mae"],
            "mean_baseline_mae": baseline_metrics["mae"],
            "mae_improvement": baseline_metrics["mae"] - selected_metrics["mae"],
            "oof_rmse": selected_metrics["rmse"],
            "mean_baseline_rmse": baseline_metrics["rmse"],
            "rmse_improvement": baseline_metrics["rmse"] - selected_metrics["rmse"],
            "folds_with_lower_absolute_error": int(np.sum(abs_err < base_abs_err)),
            "folds_with_lower_squared_error": int(np.sum(sq_gain > 0)),
            "median_abs_error": float(np.median(abs_err)),
            "p90_abs_error": float(np.quantile(abs_err, 0.90)),
            "max_abs_error": float(abs_err.max()),
            "worst_fold_sample_code": str(selected.index[int(np.argmax(abs_err))]),
            "top3_share_of_positive_squared_error_gain": top3_share,
            "leave_one_evaluation_fold_out_preserves_both": int(sum(r["both_metrics_still_improve"] for r in dropped)),
            "leave_one_evaluation_fold_out_cases": len(dropped),
            "jackknife_min_mae_improvement": float(min(r["baseline_mae"] - r["model_mae"] for r in dropped)),
            "jackknife_min_rmse_improvement": float(min(r["baseline_rmse"] - r["model_rmse"] for r in dropped)),
        }

    pd.DataFrame(fold_rows).to_csv(out_dir / "gate_b_fold_sensitivity.csv", index=False)
    pd.DataFrame(deletion_rows).to_csv(out_dir / "gate_b_fold_deletion_sensitivity.csv", index=False)
    return summaries


def _markdown_report(result: dict) -> str:
    lines = [
        "# Recipe → Sensory credibility checks", "",
        f"Permutation test: {result['permutation_test']['permutations']} joint row permutations, seed {result['permutation_test']['seed']}; row-wise permutation keeps the six sensory outcomes together.",
        "The model family selection rule is re-run inside every permutation. The empirical one-sided p-value uses (1 + exceedances) / (B + 1). This is a conditional null test assuming recipe-label exchangeability under no recipe/sensory association; it is not an external validation set.", "",
        f"- Observed targets improving both OOF MAE and RMSE: {result['observed']['n_targets_improved']}/6.",
        f"- Null permutations with 6/6 improving: {result['permutation_test']['six_of_six_exceedances']} / {result['permutation_test']['permutations']}; empirical p = {result['permutation_test']['six_of_six_empirical_p']:.6f}.",
        f"- Null permutations with Overall-score Gate B passing: {result['permutation_test']['gate_b_exceedances']} / {result['permutation_test']['permutations']}; empirical p = {result['permutation_test']['gate_b_empirical_p']:.6f}.", "",
        "## LOO fold sensitivity", "",
        "Each row in `gate_b_fold_sensitivity.csv` is one held-out blend. `fold_deletion_sensitivity.csv` removes that evaluation row from the already-computed OOF vector and recomputes aggregate MAE/RMSE; it measures metric concentration and does not retrain folds.", "",
        "| Target | Selected | MAE vs mean | RMSE vs mean | Absolute-error wins | Squared-error wins | Drop-one cases retaining both improvements | Worst fold |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for target, info in result["fold_sensitivity"].items():
        lines.append(
            f"| `{target}` | `{info['selected_model']}` | {info['mae_improvement']:.4f} | {info['rmse_improvement']:.4f} | "
            f"{info['folds_with_lower_absolute_error']}/{info['n_folds']} | {info['folds_with_lower_squared_error']}/{info['n_folds']} | "
            f"{info['leave_one_evaluation_fold_out_preserves_both']}/{info['leave_one_evaluation_fold_out_cases']} | {info['worst_fold_sample_code']} |"
        )
    lines.extend(["", "All scores are blend-mean outcomes over 30 independent recipes. Small-sample LOO comparisons remain descriptive and do not establish industrial generalization.", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--permutations", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--output-dir", default=str(ROOT / "artifacts/reports/gate_b_validation"))
    parser.add_argument("--checkpoint-every", type=int, default=20)
    args = parser.parse_args()
    if args.permutations < 1 or args.n_jobs < 1:
        parser.error("--permutations and --n-jobs must be positive")
    root = ROOT
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    fold_summary = _fold_sensitivity(root, out_dir)
    direct = json.loads((root / "artifacts/reports/recipe_sensory_metrics.json").read_text(encoding="utf-8"))
    observed_passes = {
        target: bool(
            info["selected_metrics"]["mae"] < info["baseline"]["mae"]
            and info["selected_metrics"]["rmse"] < info["baseline"]["rmse"]
        )
        for target, info in direct["by_target"].items()
    }
    observed = {
        "n_targets_improved": int(sum(observed_passes.values())),
        "all_six_improved": bool(all(observed_passes.values())),
        "gate_b_overall_pass": observed_passes["overall_score"],
        "selected_models": {target: info["selected_model"] for target, info in direct["by_target"].items()},
    }

    rng = np.random.default_rng(args.seed)
    n = len(pd.read_csv(root / "data/processed/blend_master.csv"))
    jobs = [(i + 1, rng.permutation(n).tolist()) for i in range(args.permutations)]
    rows = []
    print(f"[PERM] start B={args.permutations}, seed={args.seed}, jobs={args.n_jobs}", flush=True)
    with ProcessPoolExecutor(max_workers=args.n_jobs, initializer=_init_worker, initargs=(str(root),)) as pool:
        futures = [pool.submit(_one_permutation, job) for job in jobs]
        for future in as_completed(futures):
            rows.append(future.result())
            complete = len(rows)
            if complete % args.checkpoint_every == 0 or complete == args.permutations:
                pd.DataFrame(sorted(rows, key=lambda row: row["permutation_id"])).to_csv(out_dir / "gate_b_permutation_distribution.csv", index=False)
                elapsed = time.monotonic() - started
                print(f"[PERM] {complete}/{args.permutations} completed; elapsed={elapsed:.1f}s", flush=True)

    rows.sort(key=lambda row: row["permutation_id"])
    pd.DataFrame(rows).to_csv(out_dir / "gate_b_permutation_distribution.csv", index=False)
    six_events = sum(row["n_targets_improved"] >= observed["n_targets_improved"] for row in rows)
    gate_events = sum(bool(row["gate_b_overall_pass"]) >= observed["gate_b_overall_pass"] for row in rows)
    six_ci = binomtest(six_events, len(rows)).proportion_ci(confidence_level=0.95, method="exact")
    gate_ci = binomtest(gate_events, len(rows)).proportion_ci(confidence_level=0.95, method="exact")
    permutation_summary = {
        "permutations": len(rows), "seed": args.seed,
        "permutation_scheme": "joint row permutation of the six sample-level sensory means; recipe rows stay fixed",
        "selection_rule": "repeat the direct Recipe->Sensory per-target selection over all installed candidate families in every permutation",
        "six_of_six_exceedances": int(six_events),
        "six_of_six_empirical_p": float((six_events + 1) / (len(rows) + 1)),
        "six_of_six_null_rate_95pct_exact_ci": [float(six_ci.low), float(six_ci.high)],
        "gate_b_exceedances": int(gate_events),
        "gate_b_empirical_p": float((gate_events + 1) / (len(rows) + 1)),
        "gate_b_null_rate_95pct_exact_ci": [float(gate_ci.low), float(gate_ci.high)],
        "null_distribution_n_targets_improved": {
            str(int(key)): int(value) for key, value in pd.Series([r["n_targets_improved"] for r in rows]).value_counts().sort_index().items()
        },
    }
    result = {
        "observed": observed,
        "permutation_test": permutation_summary,
        "fold_sensitivity": fold_summary,
        "interpretation": "Permutation evidence is conditional on exchangeability of sample-level outcome vectors under the no-association null. It does not replace an external confirmatory experiment.",
    }
    (out_dir / "gate_b_trustworthiness.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "gate_b_trustworthiness.md").write_text(_markdown_report(result), encoding="utf-8")
    print(f"[PERM] 6/6 empirical p={permutation_summary['six_of_six_empirical_p']:.6f}; Gate B empirical p={permutation_summary['gate_b_empirical_p']:.6f}", flush=True)
    print(f"[OUTPUT] {out_dir}", flush=True)
    print(f"[DONE] total elapsed={time.monotonic() - started:.1f}s", flush=True)


if __name__ == "__main__":
    main()
