# TeaBioSens · 茶叶智能拼配原型

TeaBlend AI is a reproducible, leakage-aware prototype for recipe-to-chemistry and sensory prediction over the TeaBioSens data. The **V2 discrete-design-space specification** is authoritative: the current experiment has 32 legal recipes at 0.5 g increments and 4.0 g total mass; 30 have measurements and two remain to be measured. This is a discrete design-space completion and ranking prototype, not a continuous recipe optimizer.

## Evidence and limitations

- The source sheet contains 597 sensory rating rows but only 30 independent recipe blends. All validation keeps each `sample_code` wholly within one fold.
- Current coverage is 30/32 = 93.75% of the enumerated discrete space. The model's Leave-One-Blend-Out scores measure within-design reconstruction, not arbitrary or industrial recipe generalization.
- Measured blend results are used directly for the 30 observed points. Model predictions, uncertainty estimates and path disagreement are used for the two legal but unobserved points.
- A Gaussian Process spread is a model-based uncertainty estimate, not a calibrated confidence interval. Gate B disables automated prediction-based recommendations when the direct Overall score model does not beat both mean-baseline OOF MAE and RMSE.
- All candidate blends are for modeling and experimental design only. They are not validated for production or food-regulatory compliance.

## Setup

Python 3.11 or newer is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Place the immutable source workbook at `data/raw/TeaBioSens.xlsx`. The repository copy is never modified by pipeline scripts.

## Required commands

```bash
# 1. Audit the source workbook
python scripts/00_audit_data.py --input data/raw/TeaBioSens.xlsx

# 2. Build standardized datasets under data/processed/
python scripts/01_build_datasets.py

# 3. Recipe -> Chemistry (15 base chemistry targets; Leave-One-Out)
python scripts/02_train_recipe_chemistry.py

# 4. Chemistry -> Sensory (Chemistry-A/B; grouped Leave-One-Blend-Out)
python scripts/03_train_chemistry_sensory.py

# 5. Recipe -> Sensory (Leave-One-Blend-Out)
python scripts/04_train_recipe_sensory.py

# 6. Enumerate, score and rank exactly the 32 legal design points
python scripts/05_build_optimizer.py

# 7. Generate the final report
python scripts/06_generate_report.py

# 8. Run all phases in order
python scripts/07_run_full_pipeline.py

# 9. Run the full contract, leakage, design-space, optimizer and inference tests
pytest -q

# 10. Launch the interactive demo
streamlit run app/app.py
```

If the optional XGBoost or CatBoost package is unavailable, training records that backend as skipped and still runs the required Ridge, PLS, Random Forest, Gaussian Process and baseline comparisons.

## Outputs

- `data/processed/`: row-level clean data, 30-row blend master, 597-row sensory observations and source manifest.
- `artifacts/reports/`: audit reports, per-task metrics and `final_report.md`.
- `artifacts/models/`: joblib estimators, metadata, feature order and metrics.
- `artifacts/predictions/`: OOF predictions and per-sample errors.
- `artifacts/optimization/design_space_32.csv`: one row for every legal design point.
- `artifacts/optimization/next_experiments.csv`: the two missing valid recipes, prioritized for physical measurement.
- `artifacts/optimization/top_candidates.csv`: measured-first candidate ranking under Gate B and user constraints.

## V2 legal design

The legal points are enumerated from these weighing levels and the fixed 4.0 g total. The resulting set and its missing points are checked against the source data on every audit.

| Ingredient | Legal masses |
|---|---|
| Green tea | 0.5, 1.0, 1.5, 2.0 g |
| White tea | 0.5, 1.0, 1.5, 2.0 g |
| Oolong tea | 0.5, 1.0, 1.5, 2.0 g |
| Black tea | 0.5, 1.0, 1.5, 2.0, 2.5 g |

Any blend outside those 32 points is `INVALID_DESIGN_POINT` and is not returned as a recommendation. The two missing points should be physically prepared and measured to bring the defined discrete design to 100% coverage.
