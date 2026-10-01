from __future__ import annotations

import pandas as pd
import streamlit as st

from tea_ai.constants import RECIPE_FEATURES, SENSORY_TARGETS

DISCLAIMER = "本结果是基于有限公开实验数据的机器学习候选配方，仅用于实验设计和算法验证，不等同于食品研发验证或可直接生产配方。"


def warning_banner():
    st.warning(DISCLAIMER, icon="⚠️")


def display_recipe(recipe_g: dict) -> str:
    names = ["Green", "White", "Oolong", "Black"]
    keys = ["green_g", "white_g", "oolong_g", "black_g"]
    return " / ".join(f"{name} {recipe_g[key]:g}g" for name, key in zip(names, keys))


def recipes_for_display(master: pd.DataFrame) -> pd.DataFrame:
    fields = ["sample_code", *RECIPE_FEATURES, "n_ratings"]
    for target in SENSORY_TARGETS:
        fields.extend([f"{target}_mean", f"{target}_std"])
    result = master[fields].copy()
    for target in SENSORY_TARGETS:
        result[f"{target}_mean±std"] = result.apply(
            lambda row: f"{row[f'{target}_mean']:.2f} ± {row[f'{target}_std']:.2f}", axis=1
        )
    return result
