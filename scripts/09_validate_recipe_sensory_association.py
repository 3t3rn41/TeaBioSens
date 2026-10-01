#!/usr/bin/env python3
"""Model-free Mantel association test between recipes and sensory profiles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from _common import ROOT, phase
from tea_ai.association import mantel_recipe_sensory_test


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--permutations", type=int, default=4_999)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    blends = pd.read_csv(ROOT / "data/processed/blend_master.csv")
    result = mantel_recipe_sensory_test(blends, permutations=args.permutations, seed=args.seed)
    out = ROOT / "artifacts/reports/recipe_sensory_mantel"
    out.mkdir(parents=True, exist_ok=True)
    (out / "recipe_sensory_mantel.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = [{"scope": "global_multivariate", "target": "all_five", **result["global_multivariate"]}]
    rows.extend({"scope": "per_target", "target": target, **values} for target, values in result["per_target_supplementary"].items())
    pd.DataFrame(rows).to_csv(out / "recipe_sensory_mantel.csv", index=False)
    global_result = result["global_multivariate"]
    print(f"[MANTEL] n={result['n_independent_recipes']}, B={args.permutations}, r={global_result['mantel_pearson_r']:.4f}, p={global_result['permutation_p_value']:.6f}", flush=True)
    phase("M9 model-free association", "PASS", "recipe distances vs five-dimensional sensory distances; joint row permutations", str(out.relative_to(ROOT)), f"Mantel r={global_result['mantel_pearson_r']:.4f}; p={global_result['permutation_p_value']:.6f}", result["interpretation_limit"], "Read the result with n=30 independent recipes")


if __name__ == "__main__":
    main()
