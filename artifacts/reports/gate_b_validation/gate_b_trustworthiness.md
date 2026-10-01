# Recipe → Sensory credibility checks

Permutation test: 200 joint row permutations, seed 42; row-wise permutation keeps all five modeled sensory outcomes together.
The model family selection rule is re-run inside every permutation. The empirical one-sided p-value uses (1 + exceedances) / (B + 1). This is a conditional null test assuming recipe-label exchangeability under no recipe/sensory association; it is not an external validation set.

- Observed modeled targets improving both OOF MAE and RMSE: 5/5.
- Null permutations with at least 5/5 targets improving: 30 / 200; empirical p = 0.154229.
- Null permutations with Overall-score Gate B passing: 96 / 200; empirical p = 0.482587.

## LOO fold sensitivity

Each row in `gate_b_fold_sensitivity.csv` is one held-out blend. `fold_deletion_sensitivity.csv` removes that evaluation row from the already-computed OOF vector and recomputes aggregate MAE/RMSE; it measures metric concentration and does not retrain folds.

| Target | Selected | MAE vs mean | RMSE vs mean | Absolute-error wins | Squared-error wins | Drop-one cases retaining both improvements | Worst fold |
|---|---|---:|---:|---:|---:|---:|---|
| `appearance` | `catboost` | 1.1074 | 1.3067 | 18/30 | 18/30 | 30/30 | S12 |
| `infusion_color` | `pls` | 1.2188 | 0.6914 | 20/30 | 20/30 | 30/30 | S11 |
| `aroma` | `catboost` | 1.4884 | 0.8981 | 21/30 | 21/30 | 30/30 | S11 |
| `taste` | `ridge_a` | 2.8075 | 2.5019 | 23/30 | 23/30 | 30/30 | S16 |
| `overall_score` | `pls` | 2.0676 | 1.4102 | 23/30 | 23/30 | 30/30 | S11 |

All scores are blend-mean outcomes over 30 independent recipes. Small-sample LOO comparisons remain descriptive and do not establish industrial generalization.
