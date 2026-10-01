# TeaBioSens 茶叶智能拼配原型项目说明书（Agent 执行版）

> 文档用途：本文件作为代码 Agent / 编程 Agent 的主执行说明书。  
> 项目阶段：V0.1–V0.4 原型验证。  
> 当前数据源：`TeaBioSens.xlsx`。  
> 当前硬件：单张 NVIDIA RTX 4090 24GB。  
> 总原则：**先完成结构化数据建模、品质预测和受约束配方优化，再考虑大语言模型微调。**

---

## 0. Agent 总指令

Agent 必须按照本说明书从上到下执行，不得跳过数据审计、分组验证、基线模型和分布外检测。

项目的第一目标不是训练一个“会聊天的茶叶大模型”，而是完成一个可验证的：

**配方 → 理化指标 → 感官品质 → 受约束配方推荐**

原型系统。

Agent 应以“可复现、无数据泄漏、有基线、有不确定性、有测试、有可视化 Demo”为完成标准。

### 0.1 必须遵守

1. 原始文件 `TeaBioSens.xlsx` 只读，禁止覆盖、修改或另存为原文件。
2. 所有数据清洗结果必须写入 `data/processed/`。
3. 所有训练/测试划分必须以 `Sample code` 为组，禁止对597行直接随机拆分。
4. 任何标准化、特征选择、超参数搜索必须在交叉验证折内部完成，禁止提前在全量数据上拟合。
5. `S1` 的不同感官记录不能同时出现在训练集和测试集；其他样品同理。
6. 报告必须同时给出简单基线，不允许只展示最佳模型。
7. 不能将训练集分数作为模型有效性的证据。
8. 不能把模型外推结果描述成“可生产配方”。
9. 对训练数据凸包之外的配方，必须标记为 `OOD / out-of-domain`，默认不得进入 Top 推荐。
10. 自动推荐必须输出不确定性或风险标记。
11. 比例优化必须满足四种茶比例之和为100%。
12. 任何配方推荐都必须明确注明：**仅为建模/实验候选，未经食品研发实验和法规验证，不用于直接生产。**
13. 所有随机过程统一使用 `random_state=42`，除非算法不支持。
14. 每一个阶段完成后先执行测试和验收，再进入下一阶段。
15. 若某一模型不能稳定优于简单基线，必须如实记录，不得通过重新随机划分“刷高结果”。

---

# 1. 项目目标

## 1.1 当前阶段目标

基于 TeaBioSens 数据建立一个茶叶智能拼配 Proof of Concept：

```text
四种茶的配比
    ↓
理化成分预测模型
    ↓
感官品质预测模型
    ↓
不确定性 / OOD 判断
    ↓
约束优化器
    ↓
Top-K 候选配方
    ↓
Streamlit 可操作 Demo
```

用户最终可以在页面上：

1. 设置 Green / White / Oolong / Black Tea 的允许比例范围；
2. 设置目标，例如最大化 `Overall score`；
3. 可选设置理化成分约束；
4. 点击“开始优化”；
5. 获得若干候选配方；
6. 查看预测感官结果、预测理化指标、不确定性、距离已知实验数据的远近；
7. 查看最相近的已知样品；
8. 导出候选配方 CSV。

## 1.2 当前阶段非目标

以下内容不属于 V0.1–V0.4 的必须交付：

- 从零训练大语言模型；
- 用4090训练几十亿参数茶叶基础模型；
- 工业生产级配方；
- 食品法规自动合规结论；
- 真实成本优化；
- 供应商/库存优化；
- 液态茶饮生产工艺优化；
- 香精、糖、酸、稳定剂等辅料优化；
- 真实消费者偏好模型；
- 多模态视觉/光谱模型。

这些能力留到获得厂家数据后进入 V1.x。

---

# 2. 已核验的数据集事实

输入文件：

```text
TeaBioSens.xlsx
```

工作表：

```text
Sheet1
```

实际尺寸：

```text
598 行 × 30 列
```

其中：

- 第1行为表头；
- 实际观测：597行；
- 独立配方样品：30个，`S1`–`S30`；
- `S1`–`S29`：每个样品20条感官评价；
- `S30`：17条感官评价；
- 当前文件无空单元格；
- 不能将597行视为597个独立配方。

## 2.1 字段结构

### A. 样品ID

```text
Sample code
```

### B. 配方输入，共4列

```text
Green tea
White tea
Oolong tea
Black tea
```

当前数据中每个独立样品四种茶用量总和均为：

```text
4.0 g
```

因此必须额外生成标准化比例：

```text
green_pct
white_pct
oolong_pct
black_pct
```

公式：

```text
pct = ingredient_g / 4.0
```

当前独立配方范围：

| 原料 | 最小 | 最大 | 已出现离散用量 |
|---|---:|---:|---|
| Green tea | 0.5 g / 12.5% | 2.0 g / 50% | 0.5, 1.0, 1.5, 2.0 |
| White tea | 0.5 g / 12.5% | 2.0 g / 50% | 0.5, 1.0, 1.5, 2.0 |
| Oolong tea | 0.5 g / 12.5% | 2.0 g / 50% | 0.5, 1.0, 1.5, 2.0 |
| Black tea | 0.5 g / 12.5% | 2.5 g / 62.5% | 0.5, 1.0, 1.5, 2.0, 2.5 |

### C. 理化指标，共19列

```text
Protein (μg/g)
TSS (μg/g)
TP (mgGAE/g)
Caffeine %
Catechin %
TP/theanine
CAF/TP
Protein/TP
TF %
TR %
TF/TR
pH
Malic acid (mg/g)
Citric acid (mg/g)
Ascorbic acid (mg/g)
Oxalic acid (mg/g)
Galic acid (mg/g)
Succinic acid (mg/g)
L-theanine (mg/g)
```

已经核验：

**同一 `Sample code` 内上述19个理化指标完全相同。**

因此这些理化指标不是597个独立实验点，而是30组配方级实验数据重复到各个感官评价行。

### D. 感官指标，共6列

```text
Appearance
Infusion color
Aroma
Taste
Solubility
Overall score
```

前5项及 `Overall score` 会在同一个 `Sample code` 的不同评价行中变化。

当前全体597条观测的大致范围：

| 指标 | Min | Max | Mean |
|---|---:|---:|---:|
| Appearance | 40.0 | 100.0 | 75.45 |
| Infusion color | 35.0 | 100.0 | 74.71 |
| Aroma | 24.3 | 100.0 | 70.93 |
| Taste | 20.0 | 100.0 | 64.97 |
| Solubility | 46.1 | 100.0 | 82.26 |
| Overall score | 45.1 | 100.0 | 71.82 |

注意：

`Overall score` 不应在项目中擅自当作前5项的简单平均值重新计算。应保留原始 `Overall score` 作为独立观测目标。

---

# 3. 数据中的派生变量

以下4个字段已经核验为精确派生字段：

```text
TP/theanine = TP (mgGAE/g) / L-theanine (mg/g)
CAF/TP      = Caffeine % / TP (mgGAE/g)
Protein/TP  = Protein (μg/g) / TP (mgGAE/g)
TF/TR       = TF % / TR %
```

因此建模时必须区分：

## 3.1 基础理化指标

共15个：

```text
Protein (μg/g)
TSS (μg/g)
TP (mgGAE/g)
Caffeine %
Catechin %
TF %
TR %
pH
Malic acid (mg/g)
Citric acid (mg/g)
Ascorbic acid (mg/g)
Oxalic acid (mg/g)
Galic acid (mg/g)
Succinic acid (mg/g)
L-theanine (mg/g)
```

## 3.2 派生比例指标

共4个：

```text
TP/theanine
CAF/TP
Protein/TP
TF/TR
```

### 建模原则

对于 `recipe -> chemistry` 模型：

**优先预测15个基础理化指标，再根据预测结果重新计算4个派生比例。**

禁止默认训练19个完全独立的回归器后让4个比例字段与其分子/分母产生逻辑冲突。

可以额外进行“19个直接预测”的实验，但只能作为比较实验，不得作为默认生产链路。

---

# 4. 核心统计学约束

## 4.1 真正的独立配方只有30个

这是整个项目最重要的事实。

虽然数据表中有597行，但：

- 配方相同；
- 理化指标相同；
- 只有感官评分重复。

因此：

```text
597 rows ≠ 597 independent recipes
```

实际可用于：

```text
Recipe -> Chemistry
```

的独立样本量只有：

```text
n = 30
```

## 4.2 严禁普通随机 train_test_split

以下代码禁止出现于正式训练脚本：

```python
train_test_split(df, test_size=0.2, random_state=42)
```

如果作用对象是597行原始数据，这会造成严重的数据泄漏。

例如：

```text
S1 evaluator 01 -> train
S1 evaluator 02 -> train
S1 evaluator 03 -> test
```

模型测试时已经间接见过 S1 的配方及理化数据。

### 正确策略

对597行感官数据：

```python
groups = df["Sample code"]
```

使用：

```text
GroupKFold
LeaveOneGroupOut
```

最终验收优先采用：

```text
Leave-One-Blend-Out
```

即每次完整留出一个 Sample code。

对30行 `blend_master`：

使用：

```text
LeaveOneOut
```

或等价的 `LeaveOneGroupOut`。

---

# 5. 项目目录

Agent 必须创建以下项目结构：

```text
tea-ai/
├── README.md
├── PROJECT_SPEC.md
├── requirements.txt
├── pyproject.toml                 # 可选，但推荐
├── .gitignore
│
├── data/
│   ├── raw/
│   │   └── TeaBioSens.xlsx
│   └── processed/
│       ├── teabiosens_clean.csv
│       ├── blend_master.csv
│       ├── sensory_observations.csv
│       └── dataset_manifest.json
│
├── configs/
│   ├── default.yaml
│   └── feature_schema.yaml
│
├── src/
│   └── tea_ai/
│       ├── __init__.py
│       ├── constants.py
│       ├── io.py
│       ├── validation.py
│       ├── preprocessing.py
│       ├── features.py
│       ├── metrics.py
│       ├── cv.py
│       ├── uncertainty.py
│       ├── ood.py
│       ├── optimization.py
│       ├── inference.py
│       └── models/
│           ├── chemistry.py
│           ├── sensory.py
│           └── direct_recipe.py
│
├── scripts/
│   ├── 00_audit_data.py
│   ├── 01_build_datasets.py
│   ├── 02_train_recipe_chemistry.py
│   ├── 03_train_chemistry_sensory.py
│   ├── 04_train_recipe_sensory.py
│   ├── 05_build_optimizer.py
│   ├── 06_generate_report.py
│   └── 07_run_full_pipeline.py
│
├── artifacts/
│   ├── models/
│   ├── predictions/
│   ├── optimization/
│   └── reports/
│
├── app/
│   ├── app.py
│   └── components.py
│
├── notebooks/
│   └── exploratory_analysis.ipynb
│
└── tests/
    ├── test_dataset_contract.py
    ├── test_no_leakage.py
    ├── test_features.py
    ├── test_ratios.py
    ├── test_ood.py
    ├── test_optimizer.py
    └── test_inference.py
```

---

# 6. 环境要求

推荐：

```text
Python 3.11
```

基础依赖：

```text
numpy
pandas
openpyxl
scikit-learn
scipy
xgboost
catboost
shap
matplotlib
plotly
streamlit
joblib
pyyaml
pydantic
pytest
```

可选：

```text
optuna
pymoo
```

4090 在当前阶段不是必要条件。

优先保证小数据集验证正确，不要为了使用GPU而使用深度学习。

如果 XGBoost GPU 可用，可作为附加实验：

```text
device="cuda"
tree_method="hist"
```

但 CPU 结果必须能够完整复现。

---

# 7. 阶段 M0：环境和原始数据审计

执行脚本：

```bash
python scripts/00_audit_data.py --input data/raw/TeaBioSens.xlsx
```

## 7.1 必须检查

自动验证：

```text
sheet == "Sheet1"
rows_with_header == 598
data_rows == 597
columns == 30
unique_sample_codes == 30
```

样品计数：

```text
S1-S29 = 20 rows each
S30    = 17 rows
```

检查：

- 缺失值；
- Inf / -Inf；
- 非数值；
- 重复整行；
- Sample code 格式；
- 四个原料列是否非负；
- 四种茶用量和是否为4.0；
- 同一样品配方是否恒定；
- 同一样品19个理化指标是否恒定；
- 感官列范围；
- 派生比值是否满足公式。

## 7.2 数据契约测试

`tests/test_dataset_contract.py` 必须包含至少：

```python
assert len(df) == 597
assert df.shape[1] == 30
assert df["Sample code"].nunique() == 30
assert df.isna().sum().sum() == 0
```

并验证：

```text
S1-S29 == 20
S30 == 17
```

以及：

```python
np.allclose(
    df[["Green tea", "White tea", "Oolong tea", "Black tea"]].sum(axis=1),
    4.0
)
```

## 7.3 输出

生成：

```text
artifacts/reports/data_audit.json
artifacts/reports/data_audit.md
```

### M0 验收条件

```bash
pytest tests/test_dataset_contract.py -q
```

必须通过。

---

# 8. 阶段 M1：构建标准建模数据

执行：

```bash
python scripts/01_build_datasets.py
```

## 8.1 `teabiosens_clean.csv`

597行，保留全部原始信息，字段重命名为代码友好的 snake_case。

建议映射：

```text
Sample code               -> sample_code
Green tea                 -> green_g
White tea                 -> white_g
Oolong tea                -> oolong_g
Black tea                 -> black_g

Protein (μg/g)            -> protein_ug_g
TSS (μg/g)                -> tss_ug_g
TP (mgGAE/g)              -> tp_mggae_g
Caffeine %                -> caffeine_pct
Catechin %                -> catechin_pct
TF %                      -> tf_pct
TR %                      -> tr_pct
pH                        -> ph
Malic acid (mg/g)         -> malic_acid_mg_g
Citric acid (mg/g)        -> citric_acid_mg_g
Ascorbic acid (mg/g)      -> ascorbic_acid_mg_g
Oxalic acid (mg/g)        -> oxalic_acid_mg_g
Galic acid (mg/g)         -> galic_acid_mg_g
Succinic acid (mg/g)      -> succinic_acid_mg_g
L-theanine (mg/g)         -> l_theanine_mg_g

Appearance                -> appearance
Infusion color            -> infusion_color
Aroma                     -> aroma
Taste                     -> taste
Solubility                -> solubility
Overall score             -> overall_score
```

保留4个原始ratio字段，同时生成代码名。

再新增：

```text
green_pct
white_pct
oolong_pct
black_pct
```

范围采用0–1，不采用0–100：

```text
0.125 = 12.5%
```

## 8.2 `blend_master.csv`

每个 `sample_code` 一行，总计30行。

字段包含：

### 配方

```text
sample_code
green_g
white_g
oolong_g
black_g
green_pct
white_pct
oolong_pct
black_pct
```

### 15个基础理化指标

保留每个样品唯一值。

### 4个派生理化比值

保留原值，并同时计算：

```text
ratio_recomputed_*
```

用于一致性验证。

### 感官聚合

每个感官指标至少生成：

```text
appearance_mean
appearance_std
appearance_median

infusion_color_mean
infusion_color_std
infusion_color_median

aroma_mean
aroma_std
aroma_median

taste_mean
taste_std
taste_median

solubility_mean
solubility_std
solubility_median

overall_score_mean
overall_score_std
overall_score_median

n_ratings
```

## 8.3 `sensory_observations.csv`

597行。

用于：

```text
Chemistry -> Sensory
```

训练。

必须保留：

```text
sample_code
4 recipe proportions
19 chemistry fields
6 sensory fields
```

## 8.4 `dataset_manifest.json`

记录：

- 原始文件 SHA256；
- 生成时间；
- 原始行列数；
- 样品数量；
- 字段列表；
- 数据处理版本；
- random seed；
- 每个输出文件行数。

### M1 验收

```text
blend_master rows == 30
sensory_observations rows == 597
```

`blend_master` 每个 `sample_code` 只能出现一次。

---

# 9. 配方特征表示

四个配方比例满足：

```text
green + white + oolong + black = 1
```

因此存在严格线性依赖。

## 9.1 线性模型

Ridge / ElasticNet / PLS 等线性方法，不要默认使用：

```text
4 proportions + intercept
```

作为唯一实验。

至少比较两种表示：

### Representation A

仅使用：

```text
green_pct
white_pct
oolong_pct
```

其中：

```text
black_pct = 1 - green - white - oolong
```

### Representation B

使用全部4个比例，但明确处理共线性，例如：

- 无截距模型；
- PLS；
- 其他适合混合设计的方法。

默认报告中优先使用 Representation A 作为线性模型结果。

## 9.2 树模型

Random Forest / XGBoost / CatBoost 可以直接使用全部4个比例。

---

# 10. 阶段 M2：建立基线和验证框架

在训练复杂模型前必须完成。

## 10.1 Baseline

必须至少有：

### Baseline 1：全局均值

对感官：

```text
预测 = 训练样品的平均目标值
```

### Baseline 2：Nearest Recipe

寻找训练集中欧氏距离最近的配方，直接使用其目标均值。

### Baseline 3：线性/Ridge

作为最低复杂度监督学习基线。

## 10.2 验证方式

### Recipe -> Chemistry

数据：

```text
blend_master, n=30
```

验证：

```text
LeaveOneOut
```

每次：

```text
29 train + 1 held-out recipe
```

### Chemistry -> Sensory

数据：

```text
sensory_observations, n=597
```

验证：

```text
LeaveOneGroupOut
groups = sample_code
```

即测试集是完整未见过的配方。

可以额外使用：

```text
GroupKFold(n_splits=5)
```

用于超参数选择，但最终报告必须包含 Leave-One-Blend-Out 结果。

### Recipe -> Sensory

推荐主任务采用：

```text
blend_master 的感官均值
n=30
LeaveOneOut
```

同时可做597行版本的辅助实验，但必须按 `sample_code` 分组。

---

# 11. 评估指标

所有回归任务至少输出：

```text
MAE
RMSE
R²
Spearman correlation
```

注意：

单个 Leave-One-Out fold 只有一个样品时，不计算 fold-level R²。

正确方式：

1. 收集所有 held-out prediction；
2. 形成完整 out-of-fold prediction；
3. 在全部 OOF predictions 上统一计算 R²。

还应输出：

```text
prediction_error_by_sample.csv
```

字段至少：

```text
sample_code
y_true
y_pred
abs_error
signed_error
```

---

# 12. 阶段 M3：Recipe -> Chemistry

执行：

```bash
python scripts/02_train_recipe_chemistry.py
```

## 12.1 输入

```text
green_pct
white_pct
oolong_pct
black_pct
```

## 12.2 默认预测目标

优先预测15个基础理化指标。

不要把4个ratio作为独立主目标。

## 12.3 必须比较的模型

至少：

```text
Mean baseline
Ridge
PLSRegression
RandomForestRegressor
GaussianProcessRegressor
XGBoost
CatBoost
```

因样本只有30个：

- 模型参数应保守；
- 树深必须小；
- 不进行超大范围超参数搜索；
- 不使用深度神经网络作为默认方案。

## 12.4 多输出策略

可比较：

```text
一个 MultiOutput 模型
```

与：

```text
每个 chemistry target 一个独立模型
```

最终采用 OOF 结果更稳的一种。

## 12.5 ratio 重建

推理阶段必须：

```python
tp_theanine = pred_tp / pred_l_theanine
caf_tp = pred_caffeine / pred_tp
protein_tp = pred_protein / pred_tp
tf_tr = pred_tf / pred_tr
```

必须处理分母接近0的安全逻辑。

### M3 输出

```text
artifacts/models/chemistry/
artifacts/predictions/recipe_chemistry_oof.csv
artifacts/reports/recipe_chemistry_metrics.json
artifacts/reports/recipe_chemistry_report.md
```

### M3 Gate

至少判断：

```text
模型是否在主要目标上优于 Mean Baseline？
```

若大量目标无法优于基线：

- 仍保留实验结果；
- 标注数据不足；
- 后续优化器不得把这些不可靠指标作为硬约束。

---

# 13. 阶段 M4：Chemistry -> Sensory

执行：

```bash
python scripts/03_train_chemistry_sensory.py
```

## 13.1 输入特征组

进行两个实验：

### Chemistry-A

只用15个基础理化指标。

### Chemistry-B

15个基础指标 + 4个ratio。

比较 OOF 结果。

不得默认认为ratio一定改善模型。

## 13.2 目标

分别预测：

```text
appearance
infusion_color
aroma
taste
solubility
overall_score
```

不要只训练 Overall。

## 13.3 模型

至少：

```text
Mean baseline
Ridge / ElasticNet
PLSRegression
RandomForest
Gaussian Process
XGBoost
CatBoost
```

小数据条件下优先：

```text
Ridge
PLS
Gaussian Process
小型Boosting
```

## 13.4 数据泄漏约束

若对理化指标做：

```text
StandardScaler
PCA
Feature selection
```

必须放到 sklearn `Pipeline` 中，由每个CV fold内部拟合。

## 13.5 597行的意义

597行可以用于学习感官评分的分布，但同一配方理化输入相同。

因此报告中必须明确：

```text
有效配方多样性仍然只有30。
```

不能把模型性能宣传为“基于597个独立产品”。

---

# 14. 阶段 M5：Recipe -> Sensory 直接模型

执行：

```bash
python scripts/04_train_recipe_sensory.py
```

目标是建立：

```text
配方比例 -> 感官均值
```

输入：

```text
4 tea proportions
```

目标来自 `blend_master`：

```text
appearance_mean
infusion_color_mean
aroma_mean
taste_mean
solubility_mean
overall_score_mean
```

必须比较：

```text
Mean baseline
Nearest Recipe baseline
Ridge
PLS
Gaussian Process
Random Forest
XGBoost / CatBoost
```

最终保留：

1. 最佳平均误差模型；
2. 最佳不确定性模型；
3. 最简单可解释模型。

---

# 15. 两条预测链必须同时保留

最终系统至少保留：

## Path A

```text
Recipe
  ↓
Chemistry Model
  ↓
Predicted Chemistry
  ↓
Sensory Model
  ↓
Predicted Sensory
```

## Path B

```text
Recipe
  ↓
Direct Recipe-to-Sensory Model
  ↓
Predicted Sensory
```

推理时输出：

```text
path_a_score
path_b_score
model_disagreement
```

其中：

```text
model_disagreement = abs(path_a_score - path_b_score)
```

当两条路径差异很大时，候选配方风险必须提高。

---

# 16. 不确定性

由于独立配方仅30个，不确定性必须是一等公民。

优先方案：

## 16.1 Gaussian Process

输出：

```text
pred_mean
pred_std
```

## 16.2 Ensemble

对多个可靠模型：

```text
Ridge
PLS
GPR
XGBoost
CatBoost
```

计算预测均值和模型间标准差。

## 16.3 风险调整目标

配方优化时默认目标：

```text
risk_adjusted_score
=
predicted_overall_mean
-
lambda * predicted_uncertainty
```

默认：

```text
lambda = 1.0
```

允许UI调整：

```text
Conservative / Balanced / Exploratory
```

例如：

```text
Conservative: lambda = 1.5
Balanced:     lambda = 1.0
Exploratory:  lambda = 0.5
```

---

# 17. OOD / 训练分布外检测

禁止仅用 min/max 判定。

至少实现两级检测。

## 17.1 Convex Hull

因为四个比例和为1，只保留前三个：

```text
green_pct
white_pct
oolong_pct
```

在3D空间建立30个训练配方的凸包。

候选点：

```text
inside_hull = True / False
```

默认 Top 推荐必须：

```text
inside_hull == True
```

## 17.2 KNN Recipe Distance

计算候选配方到最近训练配方的距离。

输出：

```text
nearest_sample_code
nearest_distance
```

根据训练样品彼此的最近邻距离建立经验阈值。

不得编造“98%置信度”。

建议输出语义标签：

```text
IN_DOMAIN
NEAR_EDGE
OUT_OF_DOMAIN
```

---

# 18. 阶段 M6：配方优化器

执行：

```bash
python scripts/05_build_optimizer.py
```

## 18.1 决策变量

```text
g = green_pct
w = white_pct
o = oolong_pct
b = black_pct
```

必须满足：

```text
g + w + o + b = 1.0
```

并默认：

```text
g,w,o,b >= 0
```

第一版默认还必须受训练域限制。

## 18.2 默认搜索范围

系统初始化时使用数据中观察到的范围：

```text
Green  : 0.125–0.500
White  : 0.125–0.500
Oolong : 0.125–0.500
Black  : 0.125–0.625
```

但范围限制不能代替凸包检测。

## 18.3 第一版搜索方式

先实现确定、易验证的 Grid Search。

建议比例步长：

```text
0.025
```

即2.5个百分点。

生成所有满足和为1的候选组合。

过滤：

1. 用户范围；
2. 训练总体范围；
3. 凸包；
4. 可选理化约束；
5. OOD；
6. 模型异常值。

计算：

```text
predicted chemistry
predicted sensory path A
predicted sensory path B
uncertainty
model disagreement
risk adjusted score
nearest training recipe
```

然后排序。

## 18.4 后续优化算法

Grid Search正确后再增加：

```text
Differential Evolution
Bayesian Optimization
NSGA-II
```

但不能替换 Grid Search 的回归测试用途。

---

# 19. 支持的目标函数

V0.4至少支持：

```text
maximize overall_score
maximize taste
maximize aroma
maximize weighted_sensory
```

weighted_sensory 示例：

```text
0.15 * appearance
+ 0.15 * infusion_color
+ 0.20 * aroma
+ 0.35 * taste
+ 0.15 * solubility
```

**该权重只是系统用户自定义目标函数，不允许声称是数据集中 Overall score 的计算公式。**

---

# 20. 理化约束

当对应 Recipe -> Chemistry 模型通过可靠性 Gate 后，可支持例如：

```text
caffeine_pct <= X
tp_mggae_g >= Y
l_theanine_mg_g >= Z
ph between [A, B]
```

如果某个理化目标模型未优于基线或误差过大：

UI 中必须：

```text
disabled
```

或标记：

```text
experimental
```

不能作为严格约束使用。

---

# 21. Top-K 去重

优化器不能返回5个几乎相同的配方。

Top-K选择时加入最小配方距离：

```text
L1 distance or Euclidean distance
```

例如默认要求任意两个Top候选至少有一个原料相差：

```text
>= 5 percentage points
```

否则跳过相近候选。

---

# 22. 阶段 M7：解释模块

必须输出两类解释。

## 22.1 数据邻居解释

每个候选显示：

```text
Nearest known blend: Sxx
Recipe distance: ...
```

并显示候选与最近已知样品的比例差。

## 22.2 模型解释

树模型可以使用：

```text
SHAP
```

线性模型输出系数。

GPR 不强制 SHAP。

对于模型解释必须使用：

```text
“模型关联”
```

而不是：

```text
“因果影响”
```

不得将SHAP值解释成生化因果关系。

---

# 23. 阶段 M8：Streamlit Demo

应用入口：

```bash
streamlit run app/app.py
```

页面名称：

```text
TeaBlend AI — 茶叶智能拼配实验平台
```

## 23.1 页面A：数据概览

展示：

```text
597 sensory observations
30 unique blends
4 tea ingredients
19 chemistry variables
6 sensory variables
```

并明确提示：

```text
有效独立配方数 = 30
```

## 23.2 页面B：已知配方

可查看30个配方：

```text
sample_code
4 tea proportions
chemistry
sensory mean ± std
n_ratings
```

## 23.3 页面C：单配方预测

4个输入框/滑块：

```text
Green
White
Oolong
Black
```

总和必须为100%。

输出：

```text
predicted chemistry
predicted sensory
uncertainty
OOD status
nearest known blend
Path A / Path B difference
```

## 23.4 页面D：智能优化

用户设置：

```text
Objective
Green min/max
White min/max
Oolong min/max
Black min/max
Risk preference
Top K
Optional chemistry constraints
```

按钮：

```text
开始搜索
```

输出表：

| Rank | Green | White | Oolong | Black | Pred Overall | Uncertainty | Risk Score | OOD | Nearest |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|

## 23.5 页面E：候选详情

显示：

```text
Recipe
Predicted Chemistry
Predicted Sensory
Model disagreement
Uncertainty
Nearest known sample
Distance from known data
Warnings
```

始终显示：

> 本结果是基于有限公开实验数据的机器学习候选配方，仅用于实验设计和算法验证，不等同于食品研发验证或可直接生产配方。

---

# 24. 阶段 M9：报告

执行：

```bash
python scripts/06_generate_report.py
```

生成：

```text
artifacts/reports/final_report.md
```

报告至少包含：

1. 数据集审计；
2. 真实独立样本量；
3. 数据泄漏风险说明；
4. 配方空间；
5. 理化变量；
6. 感官变量；
7. Baseline；
8. Recipe -> Chemistry OOF；
9. Chemistry -> Sensory OOF；
10. Recipe -> Sensory OOF；
11. 各模型比较；
12. 不确定性；
13. OOD方法；
14. 配方优化示例；
15. 已知局限；
16. 厂家下一步应提供的数据；
17. 是否达到“可演示”标准；
18. 是否达到“可用于指导实验”标准。

---

# 25. 模型选择规则

不要仅按 R² 排名。

建议评分顺序：

1. OOF MAE；
2. OOF RMSE；
3. 与Baseline相比的改善；
4. 不同样品误差稳定性；
5. 模型不确定性是否可获得；
6. 模型复杂度；
7. 解释性；
8. 推理速度。

如果复杂模型只比 Ridge 好极少：

```text
优先选择 Ridge / PLS / GPR
```

而不是为了“高级”选择 XGBoost。

---

# 26. 超参数搜索规则

由于30个独立配方极少：

禁止：

```text
几千次 Optuna Trial
几十层树
大型神经网络
大量人工筛结果
```

允许：

```text
小范围 GridSearchCV
RandomizedSearchCV
Optuna <= 50 trials
```

所有超参数选择必须使用 Group-aware CV。

最终性能必须来自外层未见数据。

如果实现嵌套CV成本过高：

- 固定保守参数；
- 使用Leave-One-Out评估；
- 不在测试结果上反复人工调参。

---

# 27. 防止过拟合的默认参数方向

仅作为 Agent 初始配置，不是最终结论。

### Ridge

```text
alpha ∈ [0.01, 0.1, 1, 10, 100]
```

### PLS

```text
n_components <= min(5, n_features)
```

### Random Forest

```text
n_estimators: 300–800
max_depth: 2–5
min_samples_leaf: 2–5
```

### XGBoost

偏保守：

```text
max_depth: 1–3
learning_rate: 0.02–0.1
n_estimators: 100–500
subsample < 1
colsample_bytree < 1
reg_alpha > 0
reg_lambda > 0
```

### CatBoost

偏保守：

```text
depth: 2–5
learning_rate: 0.02–0.1
l2_leaf_reg > 1
```

### Gaussian Process

至少比较：

```text
RBF
Matern
```

并包含噪声项：

```text
WhiteKernel
```

---

# 28. 测试要求

执行：

```bash
pytest -q
```

至少覆盖：

## 28.1 Dataset

- 597 rows；
- 30 samples；
- 无缺失；
- 四种茶合计4g；
- 比例合计1；
- 同sample chemistry恒定；
- ratio公式一致。

## 28.2 Leakage

测试CV中：

```text
train sample codes ∩ test sample codes == ∅
```

必须始终成立。

## 28.3 Optimizer

每个推荐：

```text
sum(recipe) == 1
all recipe >= 0
satisfy user constraints
inside hull by default
```

## 28.4 Inference

同一模型文件 + 同一输入：

```text
结果确定可复现
```

---

# 29. 日志和可复现性

每次训练创建：

```text
run_id
timestamp
git_commit_if_available
config
random_state
input_sha256
model_name
cv_method
metrics
```

保存到：

```text
artifacts/runs/<run_id>/
```

不要只保存 `.pkl` 而没有对应配置。

---

# 30. 模型文件

建议使用：

```text
joblib
```

每个模型目录保存：

```text
model.joblib
metadata.json
feature_order.json
metrics.json
```

推理时必须校验输入字段顺序。

---

# 31. README 必须包含的命令

Agent最终生成的 README 至少给出：

```bash
# 1. 安装
pip install -r requirements.txt

# 2. 审计数据
python scripts/00_audit_data.py --input data/raw/TeaBioSens.xlsx

# 3. 构建数据
python scripts/01_build_datasets.py

# 4. Recipe -> Chemistry
python scripts/02_train_recipe_chemistry.py

# 5. Chemistry -> Sensory
python scripts/03_train_chemistry_sensory.py

# 6. Recipe -> Sensory
python scripts/04_train_recipe_sensory.py

# 7. Optimizer
python scripts/05_build_optimizer.py

# 8. 报告
python scripts/06_generate_report.py

# 9. 全流程
python scripts/07_run_full_pipeline.py

# 10. 测试
pytest -q

# 11. Demo
streamlit run app/app.py
```

---

# 32. Agent 每阶段状态输出格式

每完成一个阶段，在终端/执行日志中打印：

```text
[PHASE] Mx
[STATUS] PASS / FAIL / PASS_WITH_WARNINGS
[INPUT]
[OUTPUT]
[KEY_METRICS]
[WARNINGS]
[NEXT]
```

如果失败，不得静默进入下一阶段。

---

# 33. 项目 Gate

## Gate A：数据有效

满足：

- 数据契约全部通过；
- 无泄漏；
- ratio一致；
- 30个独立配方正确构建。

失败则停止。

## Gate B：模型有效

至少有一个 Recipe -> Sensory 模型：

```text
OOF MAE < Mean Baseline MAE
```

同时：

```text
OOF RMSE < Mean Baseline RMSE
```

否则：

```text
项目仍可完成数据与Demo骨架
但默认关闭“AI推荐”
```

UI显示：

```text
当前数据不足以支持可靠自动推荐
```

## Gate C：优化器有效

必须满足：

- 所有候选比例和=1；
- 无负值；
- 满足约束；
- 默认在凸包内；
- 不返回NaN/Inf；
- Top-K有差异；
- 结果可重复。

## Gate D：Demo有效

新环境能够：

```text
pip install
run pipeline
streamlit run
```

无人工改代码。

---

# 34. 4090 的使用策略

当前数据规模下：

```text
GPU不是主要瓶颈
```

优先CPU经典机器学习。

RTX 4090 可用于：

1. XGBoost/CatBoost GPU实验；
2. 后续 SHAP 加速（如适用）；
3. V0.5之后本地运行8B级LLM；
4. 厂家获得更大数据后的神经网络实验。

禁止因为有4090就将项目改成深度学习优先。

---

# 35. V0.5：LLM 接入条件

只有当 V0.1–V0.4 完成后才进入。

LLM职责：

```text
自然语言理解
↓
转换成结构化配方约束
↓
调用 optimizer
↓
解释模型结果
```

LLM不负责直接“猜配比”。

示例：

用户：

```text
我想让乌龙茶做主体，红茶不要超过20%，整体评分尽量高。
```

LLM转换：

```json
{
  "objective": "maximize_overall",
  "constraints": {
    "oolong_pct": {"min": 0.4},
    "black_pct": {"max": 0.2}
  }
}
```

然后调用数值优化器。

V0.5 之前无需对 TeaBioSens 做 LLM 微调。

---

# 36. 厂家数据到来后的升级接口

当前代码必须预留通用Schema，不把四种茶写死在核心算法中。

未来厂家可能提供：

```text
ingredient_001
ingredient_002
...
ingredient_N
```

以及：

```text
batch_id
supplier
cost
inventory
processing_temperature
processing_time
ph
brix
tea_polyphenol
caffeine
theanine
color
aroma
bitterness
astringency
sweetness
umami
overall_score
accepted
```

因此：

- 配方向量应使用动态列；
- 优化器应支持N维；
- 约束应配置化；
- UI中的四种茶可以是当前数据集适配层，而不是底层硬编码。

---

# 37. 厂家数据采集后优先新增的能力

顺序：

```text
1. 原料批次
2. 历史成功配方
3. 历史失败配方
4. 工艺参数
5. 理化检测
6. 标准化感官评价
7. 成本
8. 库存
9. 稳定性
10. 是否量产
```

届时模型升级为：

```text
Ingredient batch
+ Ratio
+ Process
+ Chemistry
+ Sensory
+ Cost
+ Stability
↓
Enterprise Formula Model
```

---

# 38. 项目当前科学局限

最终报告和UI必须明确：

1. 独立配方只有30个；
2. 配方空间覆盖有限；
3. 原料只有四种茶类；
4. 缺少独立原料批次变化；
5. 缺少生产工艺变量；
6. 缺少成本；
7. 缺少库存；
8. 缺少货架期/稳定性；
9. 缺少消费者数据；
10. 597条感官记录并非597个独立产品；
11. S30评价次数为17，与其他样品不同；
12. 无评价者ID，无法建模评价者偏差；
13. 所有候选配方必须通过真实实验验证。

---

# 39. 最终 Definition of Done

只有以下全部完成，才算 V0.4 完成：

- [ ] 项目目录创建完成；
- [ ] 原始Excel只读保留；
- [ ] 数据审计脚本完成；
- [ ] 所有Dataset Contract测试通过；
- [ ] `blend_master.csv` 30行正确；
- [ ] `sensory_observations.csv` 597行正确；
- [ ] ratio重建逻辑正确；
- [ ] 分组CV无泄漏；
- [ ] Mean baseline完成；
- [ ] Nearest Recipe baseline完成；
- [ ] Recipe -> Chemistry完成；
- [ ] Chemistry -> Sensory完成；
- [ ] Recipe -> Sensory完成；
- [ ] OOF prediction全部保存；
- [ ] MAE/RMSE/R²/Spearman报告完成；
- [ ] GPR或ensemble不确定性完成；
- [ ] Convex Hull OOD完成；
- [ ] KNN距离完成；
- [ ] Grid配方优化器完成；
- [ ] Top-K去重完成；
- [ ] 风险调整目标完成；
- [ ] 测试全部通过；
- [ ] Streamlit单配方预测页面完成；
- [ ] Streamlit配方优化页面完成；
- [ ] 候选结果支持CSV导出；
- [ ] UI包含实验性免责声明；
- [ ] `final_report.md`生成；
- [ ] README可让新环境一键复现；
- [ ] `python scripts/07_run_full_pipeline.py`可完整执行；
- [ ] `pytest -q`通过。

---

# 40. Agent 最终交付清单

Agent 完工时只需向用户汇报：

```text
1. 项目路径
2. Pipeline是否全部通过
3. pytest结果
4. 最佳Recipe->Chemistry模型
5. 最佳Chemistry->Sensory模型
6. 最佳Recipe->Sensory模型
7. 与Baseline相比的提升
8. 当前最大的模型风险
9. Streamlit启动命令
10. 3个示例候选配方
11. 下一步厂家最应该补什么数据
```

不得只汇报训练集Accuracy/R²。

---

# 41. Agent 首次执行顺序

Agent 获取本说明书后，严格按以下顺序开始：

```text
STEP 1
创建项目目录和虚拟环境配置

STEP 2
复制 TeaBioSens.xlsx 到 data/raw/
保持原文件不修改

STEP 3
实现 00_audit_data.py
先验证本说明书中的数据事实

STEP 4
实现 Dataset Contract tests
运行 pytest

STEP 5
实现 01_build_datasets.py
构建 clean / blend_master / sensory_observations

STEP 6
再次运行 pytest

STEP 7
完成 baseline + Group-aware CV 工具

STEP 8
Recipe -> Chemistry

STEP 9
Chemistry -> Sensory

STEP 10
Recipe -> Sensory

STEP 11
保存全部 OOF predictions

STEP 12
比较模型并建立不确定性

STEP 13
建立 Convex Hull + KNN OOD

STEP 14
建立 Grid Optimizer

STEP 15
添加 Top-K、多样性和风险调整

STEP 16
完成 Streamlit

STEP 17
运行完整 Pipeline + pytest

STEP 18
生成 final_report.md

STEP 19
只有全部 Gate 通过后宣布 V0.4 完成
```

---

# 42. 当前最重要的判断原则

本项目不是为了让指标看起来漂亮。

第一阶段真正需要回答的是：

> **仅凭30个TeaBioSens独立拼配样品，能否学到一个在“未见过的拼配方案”上明显优于简单基线、且可以量化不确定性的关系？**

如果答案是“可以”，则继续把优化器作为厂家Demo。

如果答案是“目前不稳定”，也属于有价值的结果：

```text
说明算法管线已验证，
但公开数据不足，
下一步必须让厂家提供更多独立配方实验。
```

禁止通过随机拆分597行来人为制造高指标。

---

## 附：推荐的第一版系统数据流

```text
TeaBioSens.xlsx
       │
       ▼
Data Audit
       │
       ├───────────────┐
       ▼               ▼
blend_master       sensory_observations
30 recipes             597 ratings
       │               │
       ▼               ▼
Recipe→Chemistry   Chemistry→Sensory
       │               │
       └──────┬────────┘
              ▼
       Path-A Sensory

Recipe──────────────►Direct Sensory
                         │
                         ▼
                    Path-B Sensory

              Path A + Path B
                     │
                     ▼
           Uncertainty + OOD
                     │
                     ▼
              Recipe Optimizer
                     │
                     ▼
               Top-K Candidates
                     │
                     ▼
                Streamlit Demo
```

---

**执行优先级：正确验证 > 模型复杂度 > GPU利用率 > LLM微调。**
