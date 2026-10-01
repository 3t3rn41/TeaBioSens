# Chemistry → Sensory model report

CV: `LeaveOneGroupOut by sample_code (30 independent blend means; within-design reconstruction); models also fit on 597 ratings`. OOF metrics below are calculated across held-out samples.

| Target | Selected model | OOF MAE | Mean baseline MAE | OOF RMSE | Mean baseline RMSE |
|---|---|---:|---:|---:|---:|
| `appearance` | `pls` / chemistry_a | 3.0653 | 4.2463 | 4.0555 | 5.2208 |
| `infusion_color` | `gpr` / chemistry_a | 3.9644 | 5.5169 | 4.9194 | 6.3850 |
| `aroma` | `pls` / chemistry_a | 4.0386 | 7.1712 | 5.4223 | 8.2724 |
| `taste` | `pls` / chemistry_a | 5.3475 | 10.2998 | 6.5002 | 11.5695 |
| `overall_score` | `pls` / chemistry_a | 3.3575 | 6.6530 | 4.1532 | 7.3143 |

Reliability gate: **PASS**.

5/5 modeled blend-mean targets improved both OOF MAE and RMSE over the mean baseline.

Models are compared on grouped out-of-fold predictions. Fold-level R² is not used; R² is calculated on the combined OOF vector.

Validation evaluates `within-design reconstruction` on a held-out observed legal blend. It does not establish performance on arbitrary continuous or industrial recipes.
The source has 597 rating rows, but only 30 independent blend recipes. Validation holds out complete `sample_code` groups.
