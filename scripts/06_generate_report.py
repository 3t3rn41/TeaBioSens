#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from _common import ROOT, phase


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def metric(value, key):
    number = value.get(key)
    return "—" if number is None or pd.isna(number) else f"{number:.4f}"


def append_comparison(lines, title, data, baseline_names=("mean", "nearest_recipe")):
    lines.extend([f"### {title}", "", "| Target | Model | MAE | RMSE | R² | Spearman |", "|---|---|---:|---:|---:|---:|"])
    for target, info in data.items():
        models = info.get("models") or info.get("all_models") or {}
        if not models:
            selected = info.get("selected_metrics", info.get("selected", {}).get("metrics", {}))
            models = {info.get("selected_model", "selected"): selected}
        baseline = info.get("baseline", {})
        baseline_row = {"mean": baseline}
        if "nearest_recipe" in info:
            baseline_row["nearest_recipe"] = info["nearest_recipe"]
        if "nearest_chemistry" in info:
            baseline_row["nearest_chemistry"] = info["nearest_chemistry"]
        for name, scores in {**baseline_row, **models}.items():
            lines.append(f"| `{target}` | `{name}` | {metric(scores, 'mae')} | {metric(scores, 'rmse')} | {metric(scores, 'r2')} | {metric(scores, 'spearman')} |")
    lines.append("")


def selected_oof_errors(metrics, predictions_path, task):
    rows = pd.read_csv(predictions_path)
    selected_rows = []
    for target, info in metrics["by_target"].items():
        chosen = info.get("selected_model")
        subset = rows[rows["target"] == target]
        if task == "chemistry_to_sensory":
            feature_set, model = chosen.split(":", 1)
            subset = subset[(subset["feature_set"] == feature_set) & (subset["model"] == model)]
        else:
            subset = subset[subset["model"] == chosen]
        for row in subset.to_dict("records"):
            row["task"] = task
            selected_rows.append(row)
    return selected_rows


def main():
    audit = load_json(ROOT / "artifacts/reports/data_audit.json")
    chem = load_json(ROOT / "artifacts/reports/recipe_chemistry_metrics.json")
    sens = load_json(ROOT / "artifacts/reports/chemistry_sensory_metrics.json")
    direct = load_json(ROOT / "artifacts/reports/recipe_sensory_metrics.json")
    opt = load_json(ROOT / "artifacts/optimization/optimization_summary.json")
    top = pd.read_csv(ROOT / "artifacts/optimization/top_candidates.csv")
    next_exp = pd.read_csv(ROOT / "artifacts/optimization/next_experiments.csv")
    combined_oof = []
    combined_oof.extend(selected_oof_errors(chem, ROOT / "artifacts/predictions/recipe_chemistry_oof.csv", "recipe_to_chemistry"))
    combined_oof.extend(selected_oof_errors(sens, ROOT / "artifacts/predictions/chemistry_sensory_oof.csv", "chemistry_to_sensory"))
    combined_oof.extend(selected_oof_errors(direct, ROOT / "artifacts/predictions/recipe_sensory_oof.csv", "recipe_to_sensory"))
    (ROOT / "artifacts/predictions").mkdir(parents=True, exist_ok=True)
    pd.DataFrame(combined_oof).to_csv(ROOT / "artifacts/predictions/prediction_error_by_sample.csv", index=False)
    coverage = audit["design_space"]
    lines = [
        "# TeaBioSens 茶叶智能拼配 V0.4 原型报告", "",
        f"生成日期：{pd.Timestamp.now(tz='UTC').strftime('%Y-%m-%d %H:%M UTC')}", "",
        "> 本报告中的预测均为当前公开数据和当前实验设计内的模型估计。配方仅为建模/实验候选，未经食品研发实验和法规验证，不用于直接生产。", "",
        "## 1. 数据审计与样本量", "",
        f"- 来源：`{audit['input_file']}`；SHA256：`{audit['input_sha256']}`。",
        f"- Sheet1：{audit['data_rows']} 行评分记录、{audit['columns']} 列、{audit['unique_sample_codes']} 个独立样品，无缺失。",
        f"- 完全重复评分记录：{audit['exact_duplicate_rows']} 行，作为源数据保留；评分重复不改变独立配方数。",
        "- 独立实验配方数为 30。S1–S29 各有 20 条评分，S30 有 17 条。",
        "- 四种茶配方总质量均为 4.0 g，19 个理化字段在同一 `sample_code` 内恒定。4 个派生比值经逐项公式核对。", "",
        "### 离散设计空间", "",
        f"- 程序从原料用量水平与 4.0 g 总质量约束中重新枚举出 {coverage['valid_point_count']} 个合法格点。",
        f"- 当前观测 {coverage['observed_point_count']} 点，覆盖率 {coverage['coverage']:.2%}；这是当前定义离散空间的覆盖率，不代表工业配方范围。",
        f"- 缺失合法点：`{coverage['unobserved_points_g']}` g。", "",
        "## 2. 验证含义与泄漏控制", "",
        "597 行数据没有按行随机拆分。Recipe→Chemistry 和 Recipe→Sensory 使用 30 个独立配方的 Leave-One-Out；Chemistry→Sensory 按 `sample_code` 分组，每折留出整组。",
        "所有指标均来自合并后的 OOF 预测。标准化通过 sklearn Pipeline 在训练折内拟合；Recipe→Chemistry 的 GPR 不确定性模型和 Chemistry→Sensory 的 GPR 使用每个独立配方的聚合均值。",
        "这些结果评估的是 `within-design reconstruction`：在当前合法离散空间内留出已观测格点后的重建能力，不证明对任意连续新配方或工业配方的泛化。", "",
        "## 3. Recipe → Chemistry", "",
        f"验证：{chem['cv_method']}。主目标为 15 个基础理化指标；4 个派生 ratio 在推理时由预测分子和分母重建。",
    ]
    append_comparison(lines, "按目标比较的 OOF 指标", chem["by_target"])
    lines.extend([f"M3 Gate：**{chem['gate']['status']}** — {chem['gate']['summary']}", "", "最近配方基线与 Mean baseline、Ridge、PLS、GPR、Random Forest、XGBoost、CatBoost 一并比较。可选后端可用情况记录于 `recipe_chemistry_metrics.json`。", ""])

    lines.extend(["## 4. Chemistry → Sensory", "", f"验证：{sens['cv_method']}。源表含 {sens['rating_rows']} 评价记录、{sens['independent_blends']} 个独立配方。OOF 选择以每个配方感官均值为评价目标；另保存逐评价记录误差，未将评分行数描述为独立产品数。", ""])
    append_comparison(lines, "按目标与特征组比较的 OOF 指标", sens["by_target"])
    lines.extend([f"M4 Gate：**{sens['gate']['status']}** — {sens['gate']['summary']}", "", "Chemistry-A 使用 15 个基础理化变量；Chemistry-B 使用 15 个基础变量加 4 个派生比值。", ""])

    lines.extend(["## 5. Recipe → Sensory（直接模型）", "", f"验证：{direct['cv_method']}。保留 Mean、Nearest Recipe、Ridge、PLS、GPR、Random Forest，以及已安装时的 XGBoost/CatBoost。", ""])
    append_comparison(lines, "按目标的 OOF 比较", direct["by_target"])
    gate = direct["gate"]
    overall = direct["by_target"]["overall_score"]
    selected = overall["selected_metrics"]
    baseline = overall["baseline"]
    lines.extend([
        f"M5 / Gate B：**{gate['status']}** — {gate['summary']}",
        f"Overall score 选中模型 `{overall['selected_model']}`：MAE {selected['mae']:.4f}、RMSE {selected['rmse']:.4f}；Mean baseline：MAE {baseline['mae']:.4f}、RMSE {baseline['rmse']:.4f}。",
        "", "当 Gate B 未通过时，Demo 将关闭未测点的自动推荐资格，仍展示实测配方排序与补点实验计划。", "",
    ])

    lines.extend([
        "## 6. 双预测路径、不确定性与设计空间状态", "",
        "Path A：Recipe→Chemistry→Sensory；Path B：Recipe→Sensory。对每个目标同时保存两条路径预测和绝对差异。优化器对未测点的风险分数采用 `predicted objective − λ × uncertainty − γ × model disagreement`；已测点排序直接使用真实感官均值。",
        "GPR predictive standard deviation 是模型估计的 spread，不是经覆盖率校准的置信区间；不会声称 95%/98% 置信度。感官评价标准差用于描述已测评分离散程度。", "",
        "当前不以凸包作 OOD 主判定。候选被标记为 `OBSERVED`、`UNOBSERVED_VALID` 或 `INVALID_DESIGN_POINT`。合法设计空间外的配方不会进入候选；KNN 最近样品及距离用于解释当前合法点与实测数据的邻近关系。", "",
        "## 7. 32 点设计空间排序与下一次实验", "",
        f"排序器检查全部 {opt['valid_point_count']} 个合法点；其中 {opt['observed_point_count']} 个采用实测值，{opt['unobserved_valid_count']} 个采用带风险惩罚的预测。Gate B 自动推荐状态：**{'enabled' if opt['ai_recommendation_enabled'] else 'disabled'}**。", "",
        "### 当前 Top 候选", "",
        "| Rank | 证据 | 配方 (g: Green / White / Oolong / Black) | Objective | Uncertainty | Risk score | 样品 |", "|---:|---|---|---:|---:|---:|---|",
    ])
    for _, row in top.head(10).iterrows():
        recipe = " / ".join(f"{row[key]:g}" for key in ["green_g", "white_g", "oolong_g", "black_g"])
        sample = row.get("sample_code_if_observed", "")
        lines.append(f"| {int(row['rank'])} | {row['evidence_type']} | {recipe} | {row['objective_value']:.3f} | {row['objective_uncertainty']:.3f} | {row['ranking_score']:.3f} | {sample if pd.notna(sample) else '—'} |")
    lines.extend(["", "### 建议优先打样的未观测格点", "", "| 优先级 | 配方 (g: Green / White / Oolong / Black) | 预测目标 | GPR spread | 最近实测样品 |", "|---:|---|---:|---:|---|"])
    for _, row in next_exp.iterrows():
        recipe = " / ".join(f"{row[key]:g}" for key in ["green_g", "white_g", "oolong_g", "black_g"])
        lines.append(f"| {int(row['experiment_priority'])} | {recipe} | {row['predicted_objective']:.3f} | {row['objective_uncertainty']:.3f} | {row['nearest_sample']} |")
    lines.extend(["", "补测这两个点会使当前固定离散设计空间达到 100% 实测覆盖；这不扩大到更细步长或其他原料。", ""])

    lines.extend([
        "## 8. 主要局限与厂家下一步数据", "",
        "1. 独立实测配方只有 30 个；当前定义的 32 点离散设计空间覆盖率为 93.75%，尚差 2 点。",
        "2. 当前设计空间狭窄：四种茶、固定 4.0 g 总量、固定 0.5 g 称量步长；不能推断 0.25 g、0.1 g 或任意连续比例。",
        "3. 不包含第五种原料、原料批次、生产工艺、成本、库存、稳定性/货架期或消费者偏好。",
        "4. 597 条感官记录并非 597 个独立产品；S30 的评分次数为 17，其余为 20。缺少评价者 ID，无法建模评价者偏差。",
        "5. Leave-One-Blend-Out 只验证当前离散空间内部重建；两个缺失点的预测在实际实验前未经直接验证。所有候选均需真实研发与法规验证。",
        "6. 厂家下一步优先提供两个缺失格点的完整理化和感官结果，随后补充原料批次、工艺参数、标准化感官评价、成本、库存和稳定性记录。", "",
        "## 9. 交付物索引", "",
        "- 数据：`data/processed/`；审计：`artifacts/reports/data_audit.*`。",
        "- OOF 预测：`artifacts/predictions/`；综合已选模型误差表：`prediction_error_by_sample.csv`；模型与字段顺序：`artifacts/models/`。",
        "- 32 点全表、下一次实验、Top 候选：`artifacts/optimization/`。",
        "- Streamlit 页面：`app/app.py`；启动：`streamlit run app/app.py`。",
        "- 完整复现：`python scripts/07_run_full_pipeline.py`；测试：`pytest -q`。", "",
        f"**Demo 判定：** 可演示。 **自动推荐 Gate：** {'通过' if gate['status'] == 'PASS' else '未通过；仅实测排序和补点估计可用'}。 **指导实验判定：** 预测点仅用于安排两项验证实验，不作为生产依据。", "",
    ])
    output = ROOT / "artifacts/reports/final_report.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    phase("M9 final report", "PASS", "audit, grouped OOF metrics, model gates and 32-point ranker outputs", str(output.relative_to(ROOT)), f"Gate B={gate['status']}; coverage={coverage['coverage']:.2%}; next experiments={len(next_exp)}", "predicted points remain unvalidated until measured", "Run pytest and launch Streamlit")


if __name__ == "__main__":
    main()
