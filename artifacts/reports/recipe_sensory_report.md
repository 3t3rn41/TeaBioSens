# Recipe → Sensory model report

CV: `LeaveOneOut by unique sample_code (n=30; within-design reconstruction)`. OOF metrics below are calculated across held-out samples.

| Target | Selected model | OOF MAE | Mean baseline MAE | OOF RMSE | Mean baseline RMSE |
|---|---|---:|---:|---:|---:|
| `appearance` | `catboost` | 3.1377 | 4.2451 | 3.9134 | 5.2201 |
| `infusion_color` | `pls` | 4.2985 | 5.5172 | 5.6938 | 6.3852 |
| `aroma` | `catboost` | 5.6827 | 7.1711 | 7.3737 | 8.2718 |
| `taste` | `ridge_a` / linear_A | 7.5020 | 10.3096 | 9.0683 | 11.5702 |
| `overall_score` | `pls` | 4.5911 | 6.6587 | 5.9042 | 7.3145 |

Reliability gate: **PASS**.

Overall-score OOF MAE/RMSE both improve over the mean baseline; 5/5 modeled targets improved both metrics.

Models are compared on grouped out-of-fold predictions. Fold-level R² is not used; R² is calculated on the combined OOF vector.

Validation evaluates `within-design reconstruction` on a held-out observed legal blend. It does not establish performance on arbitrary continuous or industrial recipes.

Any learned feature scaling is fitted inside each fold through sklearn Pipelines.
