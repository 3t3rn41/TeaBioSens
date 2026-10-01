from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

from tea_ai.constants import CHEMISTRY_ALL, CHEMISTRY_BASE, RECIPE_FEATURES, SENSORY_TARGETS
from tea_ai.inference import TeaPredictor
from tea_ai.optimization import DEFAULT_WEIGHTED_SENSORY, rank_design_space
from components import DISCLAIMER, display_recipe, recipes_for_display, warning_banner

st.set_page_config(page_title="TeaBlend AI — 茶叶智能拼配实验平台", page_icon="🍵", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: 1.5rem; max-width: 1450px;}
.hero {padding: 1.1rem 1.4rem; border-radius: 16px; background: linear-gradient(115deg,#123b2d,#267451); color: #fff; margin-bottom: 1rem;}
.hero h1 {margin: 0 0 .25rem 0; font-size: 2rem;}
.hero p {margin: .2rem 0; opacity: .9;}
.small-note {color: #64748b; font-size: .88rem;}
</style>
<div class="hero"><h1>🍵 TeaBlend AI</h1><p>茶叶智能拼配实验平台 · TeaBioSens discrete design prototype</p></div>
""", unsafe_allow_html=True)


@st.cache_resource
def load_predictor():
    return TeaPredictor(ROOT)


try:
    predictor = load_predictor()
except Exception as exc:
    st.error(f"模型和数据产物尚未准备好：{exc}")
    st.code("python scripts/07_run_full_pipeline.py", language="bash")
    st.stop()

master = predictor.master
design = predictor.design_space
direct_gate = predictor.direct_metrics.get("gate", {})
permutation_gate = predictor.trustworthiness_metrics.get("permutation_test", {})
gate_b_permutation_p = permutation_gate.get("gate_b_empirical_p")
ai_enabled = direct_gate.get("status") == "PASS" and gate_b_permutation_p is not None and gate_b_permutation_p < 0.05
warning_banner()
st.caption("当前系统只接受 4.0 g 总量、0.5 g 步长定义的 32 个合法离散格点。所有验证指标均为当前设计空间内部重建结果。")

tab_overview, tab_known, tab_predict, tab_rank, tab_detail = st.tabs([
    "A · 数据概览", "B · 已知配方", "C · 单配方预测", "D · 设计空间排序", "E · 候选详情"
])

with tab_overview:
    st.subheader("TeaBioSens 数据集")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("感官评分记录", "597")
    c2.metric("独立实测配方", "30")
    c3.metric("合法离散格点", "32")
    c4.metric("当前覆盖率", f"{design.coverage:.2%}")
    c5.metric("未测合法点", "2")
    st.info("有效独立配方数 = 30。597 条感官评价不是 597 个独立产品；每个配方的理化数据在其评价记录间重复。")
    fig = px.bar(
        pd.DataFrame({"状态": ["OBSERVED", "UNOBSERVED_VALID"], "配方数": [30, 2]}),
        x="状态", y="配方数", color="状态", color_discrete_sequence=["#21865b", "#ef9f35"],
        title="当前 32 点设计空间覆盖",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("#### 当前科学边界")
    st.markdown("""
- 当前离散设计空间覆盖 30/32 点（93.75%），但独立实测配方仍只有 30 个。
- 设计空间只涵盖四种茶、固定 4.0 g 总量和 0.5 g 称量步长。
- 不能据此推断更细步长、连续比例、第五种原料或工业批次的表现。
- S30 有 17 条评价，其余样品各有 20 条；没有评价者 ID，无法估计评价者偏差。
- 两个尚未观测的合法格点，在实际打样前仍未得到直接验证。
""")
    if not ai_enabled:
        st.error(f"自动推荐可信度尚未通过：Gate B 的标签置换 p={gate_b_permutation_p:.3f}（需 < 0.05）。页面仍展示实测配方排序和两个待验证格点的模型估计；预测点不会进入 Top 推荐。" if gate_b_permutation_p is not None else "自动推荐可信度尚未验证：缺少标签置换检验结果。页面仍展示实测配方排序和两个待验证格点的模型估计；预测点不会进入 Top 推荐。")
    else:
        st.success(f"Recipe → Sensory 的 Overall score OOF MAE/RMSE 优于均值基线，且置换检验 p={gate_b_permutation_p:.3f} < 0.05；预测排序可用于实验候选筛选。")

with tab_known:
    st.subheader("30 个已知配方 · 实测优先")
    view = master.copy()
    view["recipe"] = view.apply(lambda row: display_recipe({key: row[key] for key in ["green_g", "white_g", "oolong_g", "black_g"]}), axis=1)
    for target in SENSORY_TARGETS:
        view[f"{target} mean ± std"] = view.apply(lambda row: f"{row[f'{target}_mean']:.2f} ± {row[f'{target}_std']:.2f}", axis=1)
    columns = ["sample_code", "recipe", *CHEMISTRY_BASE, *[f"{target} mean ± std" for target in SENSORY_TARGETS], "n_ratings"]
    st.dataframe(view[columns], use_container_width=True, hide_index=True)
    st.download_button("导出已知配方 CSV", view[columns].to_csv(index=False).encode("utf-8-sig"), "known_blends.csv", "text/csv")

with tab_predict:
    st.subheader("单配方预测")
    st.caption("从当前实验设计定义的原料用量中选择；系统不会把离散空间外的组合当作推荐。")
    levels = {
        "green_g": [0.5, 1.0, 1.5, 2.0],
        "white_g": [0.5, 1.0, 1.5, 2.0],
        "oolong_g": [0.5, 1.0, 1.5, 2.0],
        "black_g": [0.5, 1.0, 1.5, 2.0, 2.5],
    }
    known_codes = master["sample_code"].astype(str).tolist()
    chosen_code = st.selectbox("从已知配方载入（可随后调整）", known_codes, index=0)
    known_row = master.loc[master["sample_code"] == chosen_code].iloc[0]
    columns = st.columns(4)
    names = ["Green tea (g)", "White tea (g)", "Oolong tea (g)", "Black tea (g)"]
    keys = ["green_g", "white_g", "oolong_g", "black_g"]
    recipe_g = []
    for col, name, key in zip(columns, names, keys):
        options = levels[key]
        default_index = options.index(float(known_row[key]))
        recipe_g.append(col.selectbox(name, options, index=default_index, key=f"predict_{key}"))
    total = float(sum(recipe_g))
    st.metric("总质量", f"{total:.1f} g", delta="合法" if np.isclose(total, 4.0) else "需为 4.0 g")
    if st.button("预测配方", key="run_single_prediction", type="primary"):
        if not np.isclose(total, 4.0):
            st.error("当前配方总量不是 4.0 g，因此不属于合法设计点。")
        else:
            result = predictor.predict_recipe(np.asarray(recipe_g) / 4.0)
            if result["design_status"] == "INVALID_DESIGN_POINT":
                st.error(result["warning"])
            else:
                st.session_state["single_result"] = result
    result = st.session_state.get("single_result")
    if result:
        st.write(f"状态：`{result['design_status']}` · 证据：`{result['evidence_type']}`")
        if result["design_status"] == "OBSERVED":
            st.success(f"{result.get('sample_code')} 有实测结果。下表保留模型估计作诊断，已知配方页显示真实数据。")
        if result.get("model_anomaly"):
            st.error("模型异常标记：" + "; ".join(result.get("model_anomaly_reasons", [])))
        left, right = st.columns(2)
        left.markdown("**Recipe → Chemistry → Sensory（Path A）**")
        left.dataframe(pd.DataFrame({"预测": result["path_a_sensory"], "GPR spread": result["path_a_uncertainty"]}), use_container_width=True)
        right.markdown("**Recipe → Sensory（Path B）**")
        right.dataframe(pd.DataFrame({"预测": result["path_b_sensory"], "GPR spread": result["path_b_uncertainty"]}), use_container_width=True)
        st.metric("Overall 路径差异", f"{result['model_disagreement']:.2f}")
        st.metric("最近已知样品", f"{result['nearest_sample_code']} · {result['nearest_distance_g']:.2f} g Euclidean")
        st.dataframe(pd.DataFrame({"预测理化指标": result["predicted_chemistry"], "GPR spread": result["chemistry_uncertainty"]}), use_container_width=True)
        st.caption(result["uncertainty_note"])

with tab_rank:
    st.subheader("32 点离散设计空间排序")
    if not ai_enabled:
        st.error("当前预测未通过标签置换可信度检查。系统仍会列出实测点的真实排序和两个待补实验点，但预测点不会进入 Top 推荐。")
    objective_options = {
        "最大化 Overall score": "maximize_overall",
        "最大化 Taste": "maximize_taste",
        "最大化 Aroma": "maximize_aroma",
        "加权感官目标": "weighted_sensory",
    }
    objective_label = st.selectbox("目标", list(objective_options))
    risk_label = st.select_slider("预测风险偏好", ["Conservative", "Balanced", "Exploratory"], value="Balanced")
    risk_lambda = {"Conservative": 1.5, "Balanced": 1.0, "Exploratory": 0.5}[risk_label]
    top_k = st.slider("Top K", 1, 20, 10)
    with st.expander("原料范围约束（仅过滤 32 个离散格点）"):
        bounds = {}
        for feature in RECIPE_FEATURES:
            column = st.columns([2, 1, 1])
            label = feature.replace("_pct", "").replace("_", " ").title()
            min_val = column[1].number_input(f"{label} min", 0.125, 0.625, 0.125, 0.125, key=f"min_{feature}")
            max_val = column[2].number_input(f"{label} max", 0.125, 0.625, 0.625, 0.125, key=f"max_{feature}")
            bounds[feature] = {"min": min_val, "max": max_val}
    weights = None
    if objective_options[objective_label] == "weighted_sensory":
        st.caption("以下权重由用户定义，不代表数据集 Overall score 的计算公式。")
        weights = {target: st.slider(target, 0.0, 1.0, DEFAULT_WEIGHTED_SENSORY[target], 0.05, key=f"weight_{target}") for target in DEFAULT_WEIGHTED_SENSORY}
    reliable_chem = [
        target for target in CHEMISTRY_BASE
        if target in predictor.chemistry_metrics.get("by_target", {})
        and predictor.chemistry_metrics["by_target"][target].get("selected_metrics", {}).get("mae", float("inf")) < predictor.chemistry_metrics["by_target"][target].get("baseline", {}).get("mae", -float("inf"))
        and predictor.chemistry_metrics["by_target"][target].get("selected_metrics", {}).get("rmse", float("inf")) < predictor.chemistry_metrics["by_target"][target].get("baseline", {}).get("rmse", -float("inf"))
    ]
    chemistry_constraints = {}
    with st.expander("可选理化约束"):
        if not reliable_chem:
            st.caption("当前没有同时优于 Mean baseline 的理化目标。理化约束已禁用。")
        else:
            use_chemistry_constraints = st.checkbox("启用可靠性 Gate 通过的理化约束")
            if use_chemistry_constraints:
                target = st.selectbox("理化指标", reliable_chem)
                mode = st.selectbox("条件", ["最小值", "最大值"])
                value = st.number_input("阈值", value=0.0)
                chemistry_constraints[target] = {"min" if mode == "最小值" else "max": value}
    if st.button("开始搜索", type="primary", key="rank_design_space"):
        if any(item["min"] > item["max"] for item in bounds.values()):
            st.error("每种原料的最小值必须小于或等于最大值。")
        else:
            try:
                result = rank_design_space(
                    predictor=predictor,
                    objective=objective_options[objective_label],
                    top_k=top_k,
                    risk_lambda=risk_lambda,
                    weighted_sensory=weights,
                    recipe_bounds=bounds,
                    chemistry_constraints=chemistry_constraints,
                )
                st.session_state["rank_result"] = result
            except ValueError as exc:
                st.error(str(exc))
    ranked = st.session_state.get("rank_result")
    if ranked:
        summary = ranked["summary"]
        st.caption(f"合法点 {summary['valid_point_count']} · 已观测 {summary['observed_point_count']} · 未观测 {summary['unobserved_valid_count']} · 约束内 {summary['eligible_count']}")
        top = ranked["top_candidates"]
        display_columns = ["rank", *RECIPE_FEATURES, "evidence_type", "objective_value", "objective_uncertainty", "ranking_score", "design_status", "nearest_sample"]
        if len(top):
            st.dataframe(top[display_columns], use_container_width=True, hide_index=True)
            st.session_state["ranked_points"] = top.to_dict("records")
        else:
            st.info("当前约束下没有可推荐的离散格点。")
        st.download_button("导出 32 点全表 CSV", ranked["table"].drop(columns=["prediction_detail"], errors="ignore").to_csv(index=False).encode("utf-8-sig"), "design_space_32.csv", "text/csv")
        st.download_button("导出待验证实验 CSV", ranked["next_experiments"].drop(columns=["prediction_detail"], errors="ignore").to_csv(index=False).encode("utf-8-sig"), "next_experiments.csv", "text/csv")

with tab_detail:
    st.subheader("候选配方详情与模型关联")
    point_labels = {}
    for _, row in pd.DataFrame([{"sample_code": row["sample_code"], **{key: row[key] for key in ["green_g", "white_g", "oolong_g", "black_g"]}} for _, row in master.iterrows()]).iterrows():
        label = f"{row['sample_code']} · {display_recipe({key: row[key] for key in ['green_g','white_g','oolong_g','black_g']})}"
        point_labels[label] = np.asarray([row[key] for key in ["green_g", "white_g", "oolong_g", "black_g"]])
    for point in sorted(design.missing_points):
        label = "UNOBSERVED · " + " / ".join(f"{value:g}g" for value in point)
        point_labels[label] = np.asarray(point)
    selected_label = st.selectbox("选择当前设计空间中的配方", list(point_labels))
    selected_g = point_labels[selected_label]
    detail = predictor.predict_recipe(selected_g / 4.0)
    st.write(f"设计状态：`{detail['design_status']}` · 证据类型：`{detail['evidence_type']}`")
    st.write(display_recipe(detail["recipe_g"]))
    if detail["design_status"] == "UNOBSERVED_VALID":
        st.warning("该点尚无真实实验结果。模型估计仅用于安排验证实验。")
    if detail.get("model_anomaly"):
        st.error("模型异常标记：" + "; ".join(detail.get("model_anomaly_reasons", [])))
    st.markdown("**Path A / Path B 与不确定性**")
    sensory_table = pd.DataFrame({
        "Path A": detail["path_a_sensory"],
        "Path B": detail["path_b_sensory"],
        "Path difference": detail["model_disagreement_by_target"],
        "Path B GPR spread": detail["path_b_uncertainty"],
    })
    st.dataframe(sensory_table, use_container_width=True)
    st.metric("Overall model disagreement", f"{detail['model_disagreement']:.2f}")
    nearest = pd.DataFrame(detail["nearest_samples"])
    nearest = nearest.rename(columns={"sample_code": "Nearest sample", "distance_g_euclidean": "Distance (g)", "recipe_delta_g": "Delta from known (g)"})
    st.markdown("**最近的已知样品**")
    st.dataframe(nearest, use_container_width=True, hide_index=True)
    if detail.get("measured_sensory"):
        st.markdown("**该点真实感官结果**")
        st.dataframe(pd.DataFrame(detail["measured_sensory"]).T, use_container_width=True)
    st.markdown("**模型特征关联（非因果）**")
    estimator = predictor.direct["estimators"]["overall_score"]
    selected_model_name = predictor.direct["selected_models"]["overall_score"]
    inner = estimator.named_steps.get("model") if hasattr(estimator, "named_steps") else estimator
    if hasattr(inner, "coef_"):
        coefficients = np.asarray(inner.coef_).reshape(-1)
        feature_names = predictor.direct["feature_order_by_target"]["overall_score"][:len(coefficients)]
        st.dataframe(pd.DataFrame({"配方比例特征": feature_names, "模型系数": coefficients, "解释": ["模型关联，不代表因果影响"] * len(feature_names)}), use_container_width=True, hide_index=True)
    elif hasattr(inner, "feature_importances_"):
        importances = np.asarray(inner.feature_importances_).reshape(-1)
        st.dataframe(pd.DataFrame({"配方比例特征": RECIPE_FEATURES[:len(importances)], "模型重要性": importances, "解释": ["模型关联，不代表因果影响"] * len(importances)}), use_container_width=True, hide_index=True)
    else:
        st.caption(f"当前 Overall score 模型 `{selected_model_name}` 不提供稳定的局部系数/特征重要性摘要；可结合邻近实测配方和两条预测链查看。")
    if selected_model_name != "ridge_a":
        simple = predictor.direct["interpretable_estimators"]["overall_score"]
        simple_model = simple.named_steps["model"]
        coefficients = np.asarray(simple_model.coef_).reshape(-1)
        feature_names = predictor.direct["interpretable_feature_order"]
        st.caption("独立 Ridge 线性参照模型（标准化特征系数），用于简洁关联解释；不代表因果影响。")
        st.dataframe(pd.DataFrame({"配方比例特征": feature_names[:len(coefficients)], "Ridge 系数": coefficients, "解释": ["模型关联，不代表因果影响"] * len(coefficients)}), use_container_width=True, hide_index=True)
    if detail["model_disagreement"] > 10 or detail["predicted_uncertainty"] > 5:
        st.warning("模型分歧或 GPR spread 较高，应优先安排实测验证。")
    st.warning(DISCLAIMER)
