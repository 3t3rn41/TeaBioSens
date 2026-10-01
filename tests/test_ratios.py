import numpy as np
import pandas as pd

from tea_ai.constants import RATIO_FORMULAS
from tea_ai.features import recompute_ratios


def test_ratio_reconstruction_matches_source_values():
    master = pd.read_csv("data/processed/blend_master.csv")
    for ratio, (num, den) in RATIO_FORMULAS.items():
        recomputed = master[num] / master[den]
        assert np.allclose(recomputed, master[f"ratio_recomputed_{ratio}"], rtol=1e-10, atol=1e-12)
        assert np.allclose(recomputed, master[ratio], rtol=1e-10, atol=1e-12)


def test_ratio_zero_denominator_is_safe():
    result = recompute_ratios({"tp_mggae_g": 0.0, "l_theanine_mg_g": 0.0, "caffeine_pct": 1.0, "protein_ug_g": 1.0, "tf_pct": 0.2, "tr_pct": 0.0})
    assert np.isnan(result["tp_theanine"])
    assert np.isnan(result["caf_tp"])
    assert np.isnan(result["protein_tp"])
    assert np.isnan(result["tf_tr"])

