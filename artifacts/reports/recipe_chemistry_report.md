# Recipe → Chemistry model report

CV: `LeaveOneOut by unique sample_code (n=30; within-design reconstruction)`. OOF metrics below are calculated across held-out samples.

| Target | Selected model | OOF MAE | Mean baseline MAE | OOF RMSE | Mean baseline RMSE |
|---|---|---:|---:|---:|---:|
| `protein_ug_g` | `gpr` | 16.6078 | 16.6078 | 21.3373 | 21.3372 |
| `tss_ug_g` | `ridge_a` / linear_A | 416.2228 | 408.5857 | 488.1049 | 464.3661 |
| `tp_mggae_g` | `gpr` | 4.3319 | 4.3319 | 5.6741 | 5.6741 |
| `caffeine_pct` | `pls` | 0.9728 | 1.0677 | 1.2315 | 1.2504 |
| `catechin_pct` | `random_forest` | 0.0685 | 0.0769 | 0.0822 | 0.0881 |
| `tf_pct` | `ridge_a` / linear_A | 0.0666 | 0.0832 | 0.0855 | 0.1006 |
| `tr_pct` | `ridge_a` / linear_A | 0.5534 | 0.5771 | 0.6560 | 0.6612 |
| `ph` | `ridge_a` / linear_A | 0.1407 | 0.1487 | 0.1683 | 0.1779 |
| `malic_acid_mg_g` | `gpr` | 0.3681 | 0.3664 | 0.4997 | 0.4978 |
| `citric_acid_mg_g` | `pls` | 1.3620 | 1.4520 | 1.6440 | 1.7048 |
| `ascorbic_acid_mg_g` | `ridge_b_no_intercept` | 2.1920 | 2.2047 | 2.3591 | 2.2974 |
| `oxalic_acid_mg_g` | `ridge_a` / linear_A | 0.3808 | 0.3716 | 0.5054 | 0.5123 |
| `galic_acid_mg_g` | `ridge_a` / linear_A | 0.0889 | 0.0959 | 0.1121 | 0.1227 |
| `succinic_acid_mg_g` | `ridge_b_no_intercept` | 1.8810 | 1.9252 | 2.5392 | 2.5340 |
| `l_theanine_mg_g` | `ridge_a` / linear_A | 0.2859 | 0.2840 | 0.3563 | 0.3550 |

Reliability gate: **PASS**.

7/15 base chemistry targets improved both OOF MAE and RMSE over the mean baseline.

Models are compared on grouped out-of-fold predictions. Fold-level R² is not used; R² is calculated on the combined OOF vector.

Validation evaluates `within-design reconstruction` on a held-out observed legal blend. It does not establish performance on arbitrary continuous or industrial recipes.

Feature scaling is fitted inside each fold through sklearn Pipelines.
