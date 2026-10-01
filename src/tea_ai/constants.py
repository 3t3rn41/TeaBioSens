"""Dataset schema and stable model feature definitions."""

from __future__ import annotations

RAW_TO_CLEAN = {
    "Sample code": "sample_code",
    "Green tea": "green_g",
    "White tea": "white_g",
    "Oolong tea": "oolong_g",
    "Black tea": "black_g",
    "Protein (μg/g)": "protein_ug_g",
    "TSS (μg/g)": "tss_ug_g",
    "TP (mgGAE/g)": "tp_mggae_g",
    "Caffeine %": "caffeine_pct",
    "Catechin %": "catechin_pct",
    "TP/theanine": "tp_theanine",
    "CAF/TP": "caf_tp",
    "Protein/TP": "protein_tp",
    "TF %": "tf_pct",
    "TR %": "tr_pct",
    "TF/TR": "tf_tr",
    "pH": "ph",
    "Malic acid (mg/g)": "malic_acid_mg_g",
    "Citric acid (mg/g)": "citric_acid_mg_g",
    "Ascorbic acid (mg/g)": "ascorbic_acid_mg_g",
    "Oxalic acid (mg/g)": "oxalic_acid_mg_g",
    "Galic acid (mg/g)": "galic_acid_mg_g",
    "Succinic acid (mg/g)": "succinic_acid_mg_g",
    "L-theanine (mg/g)": "l_theanine_mg_g",
    "Appearance": "appearance",
    "Infusion color": "infusion_color",
    "Aroma": "aroma",
    "Taste": "taste",
    "Solubility": "solubility",
    "Overall score": "overall_score",
}

RECIPE_G = ["green_g", "white_g", "oolong_g", "black_g"]
RECIPE_FEATURES = ["green_pct", "white_pct", "oolong_pct", "black_pct"]
LINEAR_RECIPE_FEATURES = ["green_pct", "white_pct", "oolong_pct"]
CHEMISTRY_BASE = [
    "protein_ug_g", "tss_ug_g", "tp_mggae_g", "caffeine_pct", "catechin_pct",
    "tf_pct", "tr_pct", "ph", "malic_acid_mg_g", "citric_acid_mg_g",
    "ascorbic_acid_mg_g", "oxalic_acid_mg_g", "galic_acid_mg_g",
    "succinic_acid_mg_g", "l_theanine_mg_g",
]
CHEMISTRY_RATIOS = ["tp_theanine", "caf_tp", "protein_tp", "tf_tr"]
CHEMISTRY_ALL = CHEMISTRY_BASE + CHEMISTRY_RATIOS
SENSORY_TARGETS = [
    "appearance", "infusion_color", "aroma", "taste", "solubility", "overall_score",
]
SENSORY_SCORE_COLUMNS = [f"{name}_mean" for name in SENSORY_TARGETS]
SAMPLE_COUNTS = {f"S{i}": 20 for i in range(1, 30)} | {"S30": 17}
DATA_VERSION = "1.0.0"
RANDOM_STATE = 42

RATIO_FORMULAS = {
    "tp_theanine": ("tp_mggae_g", "l_theanine_mg_g"),
    "caf_tp": ("caffeine_pct", "tp_mggae_g"),
    "protein_tp": ("protein_ug_g", "tp_mggae_g"),
    "tf_tr": ("tf_pct", "tr_pct"),
}

