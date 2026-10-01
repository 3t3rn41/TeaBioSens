#!/usr/bin/env python3
"""Decompose rating spread into between-recipe and within-recipe components."""

from __future__ import annotations

import json

import pandas as pd

from _common import ROOT, phase
from tea_ai.diagnostics import sensory_noise_decomposition


def main():
    observations = pd.read_csv(ROOT / "data/processed/sensory_observations.csv")
    result = sensory_noise_decomposition(observations)
    out = ROOT / "artifacts/reports/sensory_noise_decomposition"
    out.mkdir(parents=True, exist_ok=True)
    (out / "sensory_noise_decomposition.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = [{"target": target, **values} for target, values in result["targets"].items()]
    pd.DataFrame(rows).to_csv(out / "sensory_noise_decomposition.csv", index=False)
    priority = result["targets"]["overall_score"]
    print(f"[NOISE] recipes={result['n_independent_recipes']}, ratings={result['n_rating_rows']}, Overall-score within-recipe share={priority['within_recipe_variance_share']:.3f}, mean reliability={priority['mean_of_recipe_mean_reliability']:.3f}", flush=True)
    phase("M9 rating-noise decomposition", "PASS", "one-way random-effects ANOVA variance components for all six measured fields", str(out.relative_to(ROOT)), f"within-recipe variance share (Overall score)={priority['within_recipe_variance_share']:.2%}; mean reliability={priority['mean_of_recipe_mean_reliability']:.3f}", result["interpretation_limit"], "Prioritize independent recipe observations for model development")


if __name__ == "__main__":
    main()
