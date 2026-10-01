"""Grouped OOF training, comparison, serialization, and run metadata."""

from __future__ import annotations

import json
import platform
import subprocess
import uuid
import warnings
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.exceptions import ConvergenceWarning

from ..constants import (
    CHEMISTRY_ALL, CHEMISTRY_BASE, CHEMISTRY_RATIOS, DATA_VERSION,
    LINEAR_RECIPE_FEATURES, RANDOM_STATE, RECIPE_FEATURES, RATIO_FORMULAS,
    SENSORY_TARGETS,
)
from ..cv import leave_one_group_out, leave_one_out
from ..io import project_root, sha256_file, utc_now, write_json
from ..metrics import regression_metrics
from ..uncertainty import gaussian_process, predict_mean_std
from .common import candidate_estimators
from .mixture import scheffe_quadratic_estimator

warnings.filterwarnings("ignore", category=ConvergenceWarning, module="sklearn.gaussian_process")


def _array_prediction(estimator, X):
    value = np.asarray(estimator.predict(X), dtype=float)
    return value.reshape(-1)


def _fit_predict_fold(name, estimator, X_train, y_train, X_test):
    # Chemistry feature rows are identical within a recipe. Fit GPR to recipe means
    # to preserve its intended small-sample regime, while evaluating each held rating.
    if name == "gpr" and "sample_code" in X_train.columns:
        raise RuntimeError("Internal error: sample_code must not be passed as a model feature")
    estimator.fit(X_train, y_train)
    prediction = _array_prediction(estimator, X_test)
    return prediction


def _fit_gpr_group_means(X_train: pd.DataFrame, y_train: pd.Series, groups: pd.Series):
    data = X_train.copy()
    data["__y"] = np.asarray(y_train)
    data["__group"] = np.asarray(groups)
    grouped = data.groupby("__group", sort=True)
    Xg = grouped[X_train.columns].mean()
    yg = grouped["__y"].mean()
    model = gaussian_process(RANDOM_STATE)
    model.fit(Xg, yg)
    return model


def _fit_final(model_name: str, X, y, groups=None):
    if model_name == "gpr" and groups is not None:
        return _fit_gpr_group_means(X, pd.Series(np.asarray(y)), pd.Series(np.asarray(groups)))
    if model_name == "scheffe_quadratic":
        return scheffe_quadratic_estimator().fit(X, y)
    estimators = candidate_estimators(X.shape[1])
    estimator = estimators[model_name]
    estimator.fit(X, y)
    return estimator


def _write_run_metadata(task: str, input_path: Path, selected_models: dict, metrics: dict, cv_method: str):
    root = project_root()
    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{task}_{uuid.uuid4().hex[:8]}"
    run_dir = root / "artifacts" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=True).stdout.strip()
    except Exception:
        commit = None
    environment = {"python": platform.python_version()}
    for module_name in ["numpy", "pandas", "sklearn", "scipy", "xgboost", "catboost"]:
        try:
            module = __import__(module_name)
            environment[module_name] = getattr(module, "__version__", "installed")
        except ImportError:
            environment[module_name] = "not_installed"
    write_json(run_dir / "run.json", {
        "run_id": run_id, "timestamp_utc": utc_now(), "git_commit_if_available": commit,
        "config": {"random_state": RANDOM_STATE, "data_version": DATA_VERSION},
        "environment": environment,
        "input_sha256": sha256_file(input_path), "model_name": selected_models,
        "cv_method": cv_method, "metrics": metrics,
    })
    return run_id


def _write_feature_order(model_dir: Path, features: list[str]):
    write_json(model_dir / "feature_order.json", {"features": features, "random_state": RANDOM_STATE})


def _training_report_text(task, metrics, best_by_target, gate):
    title = {
        "chemistry": "Recipe → Chemistry",
        "sensory": "Chemistry → Sensory",
        "direct_recipe": "Recipe → Sensory",
    }[task]
    lines = [f"# {title} model report", "", f"CV: `{metrics['cv_method']}`. OOF metrics below are calculated across held-out samples.", "", "| Target | Selected model | OOF MAE | Mean baseline MAE | OOF RMSE | Mean baseline RMSE |", "|---|---|---:|---:|---:|---:|"]
    for target, info in best_by_target.items():
        chosen = info["selected"]
        baseline = info["baseline"]
        feature_suffix = f" / {chosen['feature_set']}" if chosen.get("feature_set") else ""
        lines.append(f"| `{target}` | `{chosen['model']}`{feature_suffix} | {chosen['metrics']['mae']:.4f} | {baseline['mae']:.4f} | {chosen['metrics']['rmse']:.4f} | {baseline['rmse']:.4f} |")
    lines.extend(["", f"Reliability gate: **{gate['status']}**.", "", gate["summary"], "", "Models are compared on grouped out-of-fold predictions. Fold-level R² is not used; R² is calculated on the combined OOF vector."])
    lines.extend(["", "Validation evaluates `within-design reconstruction` on a held-out observed legal blend. It does not establish performance on arbitrary continuous or industrial recipes."])
    if task == "sensory":
        lines.append("The source has 597 rating rows, but only 30 independent blend recipes. Validation holds out complete `sample_code` groups.")
    if task in {"chemistry", "direct_recipe"}:
        lines.extend(["", "Any learned feature scaling is fitted inside each fold through sklearn Pipelines."])
    if task == "chemistry":
        lines.append("The quadratic Scheffe expansion is deterministic: four mixture-linear terms plus six pairwise interactions, fit without an intercept.")
    return "\n".join(lines) + "\n"


def train_recipe_chemistry(master_path: str | Path | None = None) -> dict:
    root = project_root()
    master_path = Path(master_path or root / "data/processed/blend_master.csv")
    frame = pd.read_csv(master_path)
    X_all = frame[RECIPE_FEATURES]
    X_linear = frame[LINEAR_RECIPE_FEATURES]
    groups = frame["sample_code"].to_numpy()
    model_specs = {
        "scheffe_quadratic": ("scheffe_quadratic", X_all),
        "ridge_a": ("ridge", X_linear),
        "ridge_b_no_intercept": ("ridge_b_no_intercept", X_all),
        "pls": ("pls", X_all),
        "gpr": ("gpr", X_all),
        "random_forest": ("random_forest", X_all),
    }
    # optional learners are included when installed; absent backends appear in metadata.
    optional = candidate_estimators(4)
    for key in ("xgboost", "catboost"):
        if key in optional:
            model_specs[key] = (key, X_all)
    model_names = list(model_specs)
    all_records = []
    best_by_target = {}
    selected_estimators = {}
    selected_features = {}
    uncertainty_estimators = {}
    summaries = {}

    for target in CHEMISTRY_BASE:
        y = frame[target].to_numpy(dtype=float)
        predictions = {name: np.full(len(frame), np.nan) for name in model_names}
        nearest_predictions = np.full(len(frame), np.nan)
        for train_idx, test_idx in leave_one_out(len(frame)):
            train_codes = set(groups[train_idx])
            test_codes = set(groups[test_idx])
            if train_codes & test_codes:
                raise AssertionError("Recipe chemistry LOO unexpectedly has group leakage")
            y_train = y[train_idx]
            baseline = np.full(len(test_idx), float(np.mean(y_train)))
            predictions.setdefault("mean", np.full(len(frame), np.nan))[test_idx] = baseline
            train_recipes = X_all.iloc[train_idx].to_numpy(dtype=float)
            for row_index in test_idx:
                distances = np.linalg.norm(train_recipes - X_all.iloc[row_index].to_numpy(dtype=float), axis=1)
                nearest_predictions[row_index] = y[train_idx[int(np.argmin(distances))]]
            for name, (family, X) in model_specs.items():
                if family == "ridge_b_no_intercept":
                    from sklearn.linear_model import Ridge
                    estimator = Ridge(alpha=1.0, fit_intercept=False)
                elif family == "scheffe_quadratic":
                    estimator = scheffe_quadratic_estimator()
                else:
                    estimator = candidate_estimators(X.shape[1]).get(family)
                if estimator is None:
                    continue
                estimator.fit(X.iloc[train_idx], y_train)
                predictions[name][test_idx] = _array_prediction(estimator, X.iloc[test_idx])
        y_oof_mean = predictions["mean"]
        metric_by_name = {name: regression_metrics(y, pred) for name, pred in predictions.items() if np.isfinite(pred).all()}
        metric_by_name["nearest_recipe"] = regression_metrics(y, nearest_predictions)
        baseline_metrics = metric_by_name["mean"]
        eligible = [name for name in model_names if name in metric_by_name]
        selected_name = min(eligible, key=lambda name: (metric_by_name[name]["mae"], metric_by_name[name]["rmse"]))
        selected_family, X_selected = model_specs[selected_name]
        best_by_target[target] = {
            "selected": {"model": selected_name, "feature_set": "linear_A" if selected_name == "ridge_a" else None, "metrics": metric_by_name[selected_name]},
            "baseline": baseline_metrics,
            "all_models": metric_by_name,
        }
        model = _fit_final(selected_family, X_selected, y, groups if selected_name == "gpr" else None) if selected_family != "ridge_b_no_intercept" else _fit_final("ridge", X_selected, y)
        if selected_name == "ridge_b_no_intercept":
            from sklearn.linear_model import Ridge
            model = Ridge(alpha=1.0, fit_intercept=False).fit(X_selected, y)
        selected_estimators[target] = model
        selected_features[target] = list(X_selected.columns)
        # Preserve a GP uncertainty model even when another estimator wins on MAE.
        uncertainty_estimators[target] = _fit_gpr_group_means(X_all, pd.Series(y), pd.Series(groups))
        for model_name, pred in {**predictions, "nearest_recipe": nearest_predictions}.items():
            for index, sample_code in enumerate(groups):
                all_records.append({"sample_code": sample_code, "target": target, "model": model_name, "y_true": y[index], "y_pred": pred[index], "abs_error": abs(y[index] - pred[index]), "signed_error": pred[index] - y[index]})
        summaries[target] = {"baseline": baseline_metrics, "selected_model": selected_name, "selected_metrics": metric_by_name[selected_name], "models": metric_by_name}

    gate_targets = [name for name, info in best_by_target.items() if info["selected"]["metrics"]["mae"] < info["baseline"]["mae"] and info["selected"]["metrics"]["rmse"] < info["baseline"]["rmse"]]
    gate = {"status": "PASS" if gate_targets else "FAIL", "improved_targets": gate_targets, "summary": f"{len(gate_targets)}/{len(CHEMISTRY_BASE)} base chemistry targets improved both OOF MAE and RMSE over the mean baseline."}
    metrics = {"task": "recipe_to_chemistry", "cv_method": "LeaveOneOut by unique sample_code (n=30; within-design reconstruction)", "features": RECIPE_FEATURES, "targets": CHEMISTRY_BASE, "candidate_model_notes": {"scheffe_quadratic": "Second-order Scheffe mixture model: no intercept, all ingredient proportions plus all pairwise interactions; fit inside each LOO fold."}, "by_target": summaries, "gate": gate, "optional_models_available": [name for name in ("xgboost", "catboost") if name in model_specs]}
    model_dir = root / "artifacts/models/chemistry"
    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump({"estimators": selected_estimators, "uncertainty_estimators": uncertainty_estimators, "feature_order": RECIPE_FEATURES, "feature_order_by_target": selected_features, "selected_models": {k: v["selected"]["model"] for k, v in best_by_target.items()}}, model_dir / "model.joblib")
    _write_feature_order(model_dir, RECIPE_FEATURES)
    write_json(model_dir / "metadata.json", {"task": metrics["task"], "features": RECIPE_FEATURES, "targets": CHEMISTRY_BASE, "selected_models": {k: v["selected"]["model"] for k, v in best_by_target.items()}, "data_version": DATA_VERSION, "random_state": RANDOM_STATE})
    write_json(model_dir / "metrics.json", metrics)
    pred_path = root / "artifacts/predictions/recipe_chemistry_oof.csv"
    pd.DataFrame(all_records).to_csv(pred_path, index=False)
    write_json(root / "artifacts/reports/recipe_chemistry_metrics.json", metrics)
    (root / "artifacts/reports/recipe_chemistry_report.md").write_text(_training_report_text("chemistry", metrics, best_by_target, gate), encoding="utf-8")
    _write_run_metadata("recipe_chemistry", master_path, {k: v["selected"]["model"] for k, v in best_by_target.items()}, metrics, metrics["cv_method"])
    return metrics


def train_chemistry_sensory(observations_path: str | Path | None = None, master_path: str | Path | None = None) -> dict:
    root = project_root()
    observations_path = Path(observations_path or root / "data/processed/sensory_observations.csv")
    master_path = Path(master_path or root / "data/processed/blend_master.csv")
    obs = pd.read_csv(observations_path)
    master = pd.read_csv(master_path)
    # Fit non-GP estimators to the 597 ratings while leaving complete sample_code
    # groups out. Score blend means over 30 held-out groups; retain rating-level OOF
    # errors separately. GPR is fit to the 30 blend means for its small-n regime.
    codes = master["sample_code"].astype(str).to_numpy()
    means = master.set_index("sample_code")
    X_by_group = {
        "chemistry_a": master.set_index("sample_code").loc[codes, CHEMISTRY_BASE],
        "chemistry_b": master.set_index("sample_code").loc[codes, CHEMISTRY_ALL],
    }
    X_by_rating = {
        key: obs[columns].reset_index(drop=True)
        for key, columns in {"chemistry_a": CHEMISTRY_BASE, "chemistry_b": CHEMISTRY_ALL}.items()
    }
    rating_groups = obs["sample_code"].astype(str).to_numpy()
    model_variants = []
    for feature_set, X in X_by_group.items():
        for family in ["ridge", "pls", "gpr", "random_forest", "xgboost", "catboost"]:
            if family in candidate_estimators(X.shape[1]):
                model_variants.append((feature_set, family))
    all_records = []
    per_target = {}
    selected = {}
    selected_estimators = {}
    uncertainty_estimators = {}
    rating_errors = []
    for target in SENSORY_TARGETS:
        y_group = means.loc[codes, f"{target}_mean"].to_numpy(dtype=float)
        y_rating = obs[target].to_numpy(dtype=float)
        by_model = {f"{feature_set}:{family}": np.full(len(codes), np.nan) for feature_set, family in model_variants}
        mean_pred = np.full(len(codes), np.nan)
        nearest_pred = np.full(len(codes), np.nan)
        rating_prediction_by_model = {key: np.full(len(obs), np.nan) for key in by_model}
        for train_group_idx, test_group_idx in leave_one_group_out(codes):
            train_codes = set(codes[train_group_idx])
            test_codes = set(codes[test_group_idx])
            if train_codes & test_codes:
                raise AssertionError("Leakage: Chemistry -> Sensory fold split a sample_code")
            train_rating_idx = np.flatnonzero(np.isin(rating_groups, list(train_codes)))
            test_rating_idx = np.flatnonzero(np.isin(rating_groups, list(test_codes)))
            mean_pred[test_group_idx] = float(np.mean(y_rating[train_rating_idx]))
            base_X = X_by_group["chemistry_a"]
            scaler = StandardScaler().fit(base_X.iloc[train_group_idx])
            train_scaled = scaler.transform(base_X.iloc[train_group_idx])
            test_scaled = scaler.transform(base_X.iloc[test_group_idx])
            for test_position, group_index in enumerate(test_group_idx):
                neighbor = int(np.argmin(np.linalg.norm(train_scaled - test_scaled[test_position], axis=1)))
                nearest_pred[group_index] = y_group[train_group_idx[neighbor]]

            for feature_set, family in model_variants:
                name = f"{feature_set}:{family}"
                model = candidate_estimators(X_by_group[feature_set].shape[1])[family]
                if family == "gpr":
                    model.fit(X_by_group[feature_set].iloc[train_group_idx], y_group[train_group_idx])
                else:
                    model.fit(X_by_rating[feature_set].iloc[train_rating_idx], y_rating[train_rating_idx])
                rating_prediction = _array_prediction(model, X_by_rating[feature_set].iloc[test_rating_idx])
                rating_prediction_by_model[name][test_rating_idx] = rating_prediction
                for group_index, code in zip(test_group_idx, test_codes):
                    local = np.flatnonzero(rating_groups[test_rating_idx] == code)
                    by_model[name][group_index] = float(np.mean(rating_prediction[local]))

        base_metric = regression_metrics(y_group, mean_pred)
        nearest_metric = regression_metrics(y_group, nearest_pred)
        model_metrics = {name: regression_metrics(y_group, pred) for name, pred in by_model.items() if np.isfinite(pred).all()}
        chosen_name = min(model_metrics, key=lambda name: (model_metrics[name]["mae"], model_metrics[name]["rmse"]))
        feature_set, family = chosen_name.split(":", 1)
        final_model = candidate_estimators(X_by_group[feature_set].shape[1])[family]
        if family == "gpr":
            final_model.fit(X_by_group[feature_set], y_group)
        else:
            final_model.fit(X_by_rating[feature_set], y_rating)
        selected_estimators[target] = final_model
        selected[target] = {"model": family, "feature_set": feature_set, "metrics": model_metrics[chosen_name]}
        uncertainty_estimators[target] = candidate_estimators(X_by_group["chemistry_a"].shape[1])["gpr"].fit(X_by_group["chemistry_a"], y_group)

        for name, pred in by_model.items():
            feature_set, family = name.split(":", 1)
            for index, sample_code in enumerate(codes):
                all_records.append({"sample_code": sample_code, "target": target, "model": family, "feature_set": feature_set, "y_true": y_group[index], "y_pred": pred[index], "abs_error": abs(y_group[index] - pred[index]), "signed_error": pred[index] - y_group[index]})
        for model_name, pred in [("mean", mean_pred), ("nearest_chemistry", nearest_pred)]:
            for index, sample_code in enumerate(codes):
                all_records.append({"sample_code": sample_code, "target": target, "model": model_name, "feature_set": "baseline", "y_true": y_group[index], "y_pred": pred[index], "abs_error": abs(y_group[index] - pred[index]), "signed_error": pred[index] - y_group[index]})
        chosen_rating_pred = rating_prediction_by_model[chosen_name]
        for index, row in obs.iterrows():
            prediction = float(chosen_rating_pred[index])
            rating_errors.append({"sample_code": row["sample_code"], "target": target, "y_true": y_rating[index], "y_pred": prediction, "abs_error": abs(y_rating[index] - prediction), "signed_error": prediction - y_rating[index]})
        selected_metrics = model_metrics[chosen_name]
        per_target[target] = {
            "baseline": base_metric,
            "nearest_chemistry": nearest_metric,
            "selected_model": chosen_name,
            "selected_metrics": selected_metrics,
            "rating_level_selected_model": regression_metrics(y_rating, chosen_rating_pred),
            "models": model_metrics,
        }

    gate_targets = [name for name in SENSORY_TARGETS if selected[name]["metrics"]["mae"] < per_target[name]["baseline"]["mae"] and selected[name]["metrics"]["rmse"] < per_target[name]["baseline"]["rmse"]]
    gate = {"status": "PASS" if gate_targets else "FAIL", "improved_targets": gate_targets, "summary": f"{len(gate_targets)}/{len(SENSORY_TARGETS)} blend-mean targets improved both OOF MAE and RMSE over the mean baseline."}
    metrics = {"task": "chemistry_to_sensory", "cv_method": "LeaveOneGroupOut by sample_code (30 independent blend means; within-design reconstruction); models also fit on 597 ratings", "rating_rows": int(len(obs)), "independent_blends": int(len(codes)), "feature_sets": {key: list(value.columns) for key, value in X_by_group.items()}, "by_target": per_target, "gate": gate, "optional_models_available": sorted({family for _, family in model_variants} & {"xgboost", "catboost"})}
    model_dir = root / "artifacts/models/sensory"
    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump({"estimators": selected_estimators, "uncertainty_estimators": uncertainty_estimators, "features_by_target": {k: X_by_group[v["feature_set"]].columns.tolist() for k, v in selected.items()}, "selected_models": selected}, model_dir / "model.joblib")
    _write_feature_order(model_dir, CHEMISTRY_ALL)
    write_json(model_dir / "metadata.json", {"task": metrics["task"], "targets": SENSORY_TARGETS, "selected_models": selected, "data_version": DATA_VERSION, "random_state": RANDOM_STATE})
    write_json(model_dir / "metrics.json", metrics)
    pd.DataFrame(all_records).to_csv(root / "artifacts/predictions/chemistry_sensory_oof.csv", index=False)
    pd.DataFrame(rating_errors).to_csv(root / "artifacts/predictions/chemistry_sensory_rating_errors.csv", index=False)
    write_json(root / "artifacts/reports/chemistry_sensory_metrics.json", metrics)
    (root / "artifacts/reports/chemistry_sensory_report.md").write_text(_training_report_text("sensory", metrics, {k: {"selected": selected[k], "baseline": per_target[k]["baseline"]} for k in SENSORY_TARGETS}, gate), encoding="utf-8")
    _write_run_metadata("chemistry_sensory", observations_path, {k: v["model"] for k, v in selected.items()}, metrics, metrics["cv_method"])
    return metrics


def train_direct_recipe_sensory(master_path: str | Path | None = None) -> dict:
    root = project_root()
    master_path = Path(master_path or root / "data/processed/blend_master.csv")
    frame = pd.read_csv(master_path)
    X_all = frame[RECIPE_FEATURES]
    X_linear = frame[LINEAR_RECIPE_FEATURES]
    codes = frame["sample_code"].to_numpy()
    model_specs = {"ridge_a": ("ridge", X_linear), "pls": ("pls", X_all), "gpr": ("gpr", X_all), "random_forest": ("random_forest", X_all)}
    optional = candidate_estimators(4)
    for family in ["xgboost", "catboost"]:
        if family in optional:
            model_specs[family] = (family, X_all)
    all_records = []
    best_by_target = {}
    selected_estimators = {}
    interpretable_estimators = {}
    uncertainty_estimators = {}
    for target in SENSORY_TARGETS:
        y = frame[f"{target}_mean"].to_numpy(dtype=float)
        predictions = {name: np.full(len(frame), np.nan) for name in model_specs}
        mean_pred = np.full(len(frame), np.nan)
        nearest_pred = np.full(len(frame), np.nan)
        for train_idx, test_idx in leave_one_out(len(frame)):
            mean_pred[test_idx] = float(y[train_idx].mean())
            train_recipes = X_all.iloc[train_idx].to_numpy()
            for i in test_idx:
                distances = np.linalg.norm(train_recipes - X_all.iloc[i].to_numpy(), axis=1)
                nearest_index = train_idx[int(np.argmin(distances))]
                nearest_pred[i] = y[nearest_index]
            for name, (family, X) in model_specs.items():
                estimator = candidate_estimators(X.shape[1])[family]
                estimator.fit(X.iloc[train_idx], y[train_idx])
                predictions[name][test_idx] = _array_prediction(estimator, X.iloc[test_idx])
        metrics_by_name = {"mean": regression_metrics(y, mean_pred), "nearest_recipe": regression_metrics(y, nearest_pred)}
        metrics_by_name.update({name: regression_metrics(y, pred) for name, pred in predictions.items()})
        passing_models = [
            name for name in model_specs
            if metrics_by_name[name]["mae"] < metrics_by_name["mean"]["mae"]
            and metrics_by_name[name]["rmse"] < metrics_by_name["mean"]["rmse"]
        ]
        selection_pool = passing_models if target == "overall_score" and passing_models else list(model_specs)
        selected_name = min(selection_pool, key=lambda name: (metrics_by_name[name]["mae"], metrics_by_name[name]["rmse"]))
        selected_family, X_selected = model_specs[selected_name]
        if selected_name == "ridge_a":
            model = candidate_estimators(3)["ridge"].fit(X_selected, y)
        else:
            model = candidate_estimators(X_selected.shape[1])[selected_family].fit(X_selected, y)
        selected_estimators[target] = model
        interpretable_estimators[target] = candidate_estimators(X_linear.shape[1])["ridge"].fit(X_linear, y)
        uncertainty_estimators[target] = candidate_estimators(4)["gpr"].fit(X_all, y)
        best_by_target[target] = {"selected": {"model": selected_name, "feature_set": "linear_A" if selected_name == "ridge_a" else None, "metrics": metrics_by_name[selected_name]}, "baseline": metrics_by_name["mean"], "nearest_recipe": metrics_by_name["nearest_recipe"], "all_models": metrics_by_name}
        for model_name, pred in {"mean": mean_pred, "nearest_recipe": nearest_pred, **predictions}.items():
            for index, sample_code in enumerate(codes):
                all_records.append({"sample_code": sample_code, "target": target, "model": model_name, "y_true": y[index], "y_pred": pred[index], "abs_error": abs(y[index] - pred[index]), "signed_error": pred[index] - y[index]})
    gate_targets = [
        target for target, info in best_by_target.items()
        if any(
            model != "mean" and model != "nearest_recipe"
            and scores["mae"] < info["baseline"]["mae"]
            and scores["rmse"] < info["baseline"]["rmse"]
            for model, scores in info["all_models"].items()
        )
    ]
    overall_improved = "overall_score" in gate_targets
    gate = {"status": "PASS" if overall_improved else "FAIL", "primary_target": "overall_score", "improved_targets": gate_targets, "summary": f"Overall-score OOF MAE/RMSE {'both improve' if overall_improved else 'do not both improve'} over the mean baseline; {len(gate_targets)}/{len(SENSORY_TARGETS)} targets improved both metrics."}
    metrics = {"task": "recipe_to_sensory", "cv_method": "LeaveOneOut by unique sample_code (n=30; within-design reconstruction)", "features": RECIPE_FEATURES, "targets": SENSORY_TARGETS, "by_target": {k: {"selected_model": v["selected"]["model"], "selected_metrics": v["selected"]["metrics"], "baseline": v["baseline"], "nearest_recipe": v["nearest_recipe"], "models": v["all_models"]} for k, v in best_by_target.items()}, "gate": gate, "optional_models_available": [name for name in ("xgboost", "catboost") if name in model_specs]}
    model_dir = root / "artifacts/models/direct_recipe"
    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump({"estimators": selected_estimators, "uncertainty_estimators": uncertainty_estimators, "interpretable_estimators": interpretable_estimators, "feature_order": RECIPE_FEATURES, "feature_order_by_target": {target: list(model_specs[best_by_target[target]["selected"]["model"]][1].columns) for target in SENSORY_TARGETS}, "interpretable_feature_order": LINEAR_RECIPE_FEATURES, "selected_models": {k: v["selected"]["model"] for k, v in best_by_target.items()}}, model_dir / "model.joblib")
    _write_feature_order(model_dir, RECIPE_FEATURES)
    write_json(model_dir / "metadata.json", {"task": metrics["task"], "features": RECIPE_FEATURES, "targets": SENSORY_TARGETS, "selected_models": {k: v["selected"]["model"] for k, v in best_by_target.items()}, "interpretable_model": "scaled Ridge on representation A", "interpretable_feature_order": LINEAR_RECIPE_FEATURES, "uncertainty_model": "GaussianProcessRegressor", "data_version": DATA_VERSION, "random_state": RANDOM_STATE})
    write_json(model_dir / "metrics.json", metrics)
    pd.DataFrame(all_records).to_csv(root / "artifacts/predictions/recipe_sensory_oof.csv", index=False)
    write_json(root / "artifacts/reports/recipe_sensory_metrics.json", metrics)
    (root / "artifacts/reports/recipe_sensory_report.md").write_text(_training_report_text("direct_recipe", metrics, best_by_target, gate), encoding="utf-8")
    _write_run_metadata("recipe_sensory", master_path, {k: v["selected"]["model"] for k, v in best_by_target.items()}, metrics, metrics["cv_method"])
    return metrics
