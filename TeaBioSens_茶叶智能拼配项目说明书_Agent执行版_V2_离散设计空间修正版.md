# TeaBioSens 茶叶智能拼配原型项目说明书（Agent 执行版 V2：离散设计空间修正版）

> 文档用途：本文件作为代码 Agent / 编程 Agent 的主执行说明书。  
> 项目阶段：V0.1–V0.4 原型验证。  
> 当前数据源：`TeaBioSens.xlsx`。  
> 当前硬件：单张 NVIDIA RTX 4090 24GB。  
> 总原则：**先完成结构化数据建模、品质预测和受约束配方优化，再考虑大语言模型微调。**

> **V2关键修正**：经对原始数据穷举核验，当前配方设计空间是32个离散合法格点，已观测30个（93.75%），仅缺2个点。因此 V0.1–V0.4 从“连续空间优化/OOD”修正为“32点离散空间补全、实测优先排序与两点预测”。

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
9. 当前 V0.1–V0.4 的合法配方空间必须严格限定为数据集定义的 **32 个离散格点**；不属于这32点的组合标记为 `INVALID_DESIGN_POINT`，不得进入推荐。
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
不确定性 / 设计空间状态判断
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


## 2.2 离散设计空间：32个合法格点，已覆盖30个

对原始 Excel 的四个配方变量进行穷举后，可以确定 TeaBioSens 当前实验设计不是连续配方空间，而是一个明确的离散格点设计：

```text
Green tea  ∈ {0.5, 1.0, 1.5, 2.0} g
White tea  ∈ {0.5, 1.0, 1.5, 2.0} g
Oolong tea ∈ {0.5, 1.0, 1.5, 2.0} g
Black tea  ∈ {0.5, 1.0, 1.5, 2.0, 2.5} g
```

并满足：

```text
Green + White + Oolong + Black = 4.0 g
```

在这些约束下，**合法配方总数恰好为32个**。

当前数据已经观测其中30个：

```text
coverage = 30 / 32 = 93.75%
```

仅有两个合法格点尚未观测：

```text
MISSING_01 = (Green 0.5, White 1.0, Oolong 1.5, Black 1.0) g
MISSING_02 = (Green 0.5, White 1.5, Oolong 0.5, Black 1.5) g
```

Agent 必须在 M0 数据审计时通过代码重新枚举并验证上述结论，不允许只把本说明书中的数值硬编码为事实。

### 重要含义

1. 当前 TeaBioSens 的问题本质上是**高覆盖率离散设计空间的补全/插值问题**，不是广阔连续空间中的黑盒优化问题。
2. 在当前32点设计空间内，30个已观测点的真实实验值优先级高于模型预测值。
3. 机器学习在 V0.1–V0.4 中最直接的预测任务，是估计剩余2个合法未观测格点，以及通过交叉验证评估这种补全能力。
4. 不属于32个合法格点的配方，在当前项目中不是“OOD候选”，而是**不属于本实验设计/不可按当前0.5 g步长制造的组合**。
5. 如果未来厂家允许更细称量步长、不同总质量或连续比例，则需要重新定义新的设计空间；不能直接把当前模型外推过去。


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

# 4. 核心统计学与设计空间约束

## 4.1 真正的独立实验配方只有30个

虽然数据表中有597行，但：

- 配方相同；
- 理化指标相同；
- 同一配方下主要变化的是感官评分。

因此：

```text
597 rows ≠ 597 independent recipes
```

用于 `Recipe -> Chemistry` 的独立实验配方仍只有：

```text
n_observed = 30
```

但必须同时认识到：

```text
n_total_valid_design_points = 32
coverage = 93.75%
```

所以“样本少”和“设计空间覆盖低”是两个不同概念：

- **独立实验数少：是。**
- **当前离散设计空间覆盖低：否。**
- **对更广泛连续/工业配方空间的覆盖：非常有限。**

## 4.2 当前任务是离散格点插值/补全，不是连续外推

当前阶段最重要的问题应表述为：

> 给定32个合法离散格点中的30个实测点，模型能否在留出已观测格点时稳定重建其结果，并对剩余2个合法未观测格点给出有校准风险提示的预测？

因此不得把 Leave-One-Blend-Out 的结果描述为：

```text
“验证模型对任意新配方的泛化能力”
```

正确描述应为：

```text
“验证模型在当前离散设计空间内，对被人为留出的合法格点进行插值/重建的能力”
```

真正对剩余两个未观测格点的预测能力，**只有在未来实际打样并测得这两个点之后才能直接验证。**

## 4.3 严禁普通随机 train_test_split

以下代码禁止作用于597行原始数据作为正式验证：

```python
train_test_split(df, test_size=0.2, random_state=42)
```

否则同一个配方可能同时进入训练和测试：

```text
S1 evaluator 01 -> train
S1 evaluator 02 -> train
S1 evaluator 03 -> test
```

会形成严重泄漏。

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

对30行 `blend_master`：

使用：

```text
LeaveOneOut
```

这些验证的语义统一定义为：

```text
within-design interpolation / reconstruction validation
```

不得定义为当前32点之外的外推验证。

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
│       ├── design_space.py
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
    ├── test_design_space.py
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

- 自动枚举合法设计空间是否恰好为32点；
- 当前观测配方集合是否恰好为30点；
- 覆盖率是否为93.75%；
- 未观测合法点是否恰好为：
  - `(0.5, 1.0, 1.5, 1.0)`；
  - `(0.5, 1.5, 0.5, 1.5)`。


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

还必须测试离散设计空间：

```python
valid_points = enumerate_valid_design_points()
assert len(valid_points) == 32

observed_points = extract_observed_recipe_points(df)
assert len(observed_points) == 30

missing = valid_points - observed_points
assert missing == {
    (0.5, 1.0, 1.5, 1.0),
    (0.5, 1.5, 0.5, 1.5),
}
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

即测试集是一个在该折中未参与训练的**合法已观测格点**。该实验用于评估当前32点设计空间内部的插值/重建能力，不代表对任意新配方空间的外推能力。

可以额外使用：

```text
GroupKFold(n_splits=5)
```

用于超参数选择，但最终报告必须包含 Leave-One-Blend-Out 结果，并明确标注为 `within-design reconstruction`。

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

六项感官字段继续保留在清洗数据、配方汇总和已测结果展示中。M4 Chemistry -> Sensory、M5 Recipe -> Sensory、Gate B 和模型驱动的推荐目标只建模以下五项：

```text
appearance
infusion_color
aroma
taste
overall_score
```

`solubility` 保留为描述字段，不进入模型目标、Gate B 统计量或未观测点加权推荐。报告必须引用重复评分的方差分解说明这一目标选择；不要只训练 Overall。

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

# 17. 设计空间与可制造性判定

V0.1–V0.4 不再把 Convex Hull 作为主要 OOD 判定工具。

原因：

- 30个已观测格点已经覆盖32点离散设计空间的93.75%；
- 剩余2个合法格点也位于已观测点凸包内部；
- 因而 Convex Hull 无法区分“已测点”和“合法但未测点”；
- 对当前任务而言，更重要的是判断候选是否属于**32个定义明确的合法格点**。

## 17.1 枚举合法设计空间

实现函数：

```python
enumerate_valid_design_points()
```

必须通过组合枚举自动生成全部32点，而不是手工写死列表。

条件：

```text
Green  ∈ {0.5, 1.0, 1.5, 2.0}
White  ∈ {0.5, 1.0, 1.5, 2.0}
Oolong ∈ {0.5, 1.0, 1.5, 2.0}
Black  ∈ {0.5, 1.0, 1.5, 2.0, 2.5}
sum = 4.0
```

测试必须验证：

```text
len(valid_design_points) == 32
```

## 17.2 候选状态

每个候选必须属于以下三类之一：

```text
OBSERVED
UNOBSERVED_VALID
INVALID_DESIGN_POINT
```

定义：

### OBSERVED

候选是32个合法格点之一，并且在 TeaBioSens 中已有真实实验数据。

当前：

```text
30 points
```

此类候选默认使用：

```text
真实理化数据 + 真实感官聚合数据
```

模型预测只作为模型诊断，不应覆盖真实值。

### UNOBSERVED_VALID

候选属于32个合法格点，但数据集中尚无实验结果。

当前恰好2个：

```text
(0.5, 1.0, 1.5, 1.0) g
(0.5, 1.5, 0.5, 1.5) g
```

此类候选使用模型预测，并必须附带：

```text
PREDICTED
uncertainty
nearest observed blends
model disagreement
```

### INVALID_DESIGN_POINT

任何不属于32个合法格点的组合。

例如：

```text
Green = 0.7 g
White = 0.9 g
...
```

即使比例和为4.0 g，也不属于当前实验设计。

V0.1–V0.4 中此类配方：

```text
禁止进入优化候选
禁止显示为推荐配方
```

## 17.3 最近邻距离

KNN距离仍保留，但用途改为：

- 解释未观测合法点与哪些实测点最接近；
- 作为模型不确定性的辅助特征；
- 不再承担主要“OOD裁决”职责。

输出：

```text
nearest_sample_code
nearest_distance
k_nearest_samples
```

## 17.4 未来扩展

只有当项目进入连续比例、更细步长或厂家真实原料空间时，再引入：

```text
Convex Hull
Mahalanobis Distance
Density Estimation
Conformal / Ensemble uncertainty
```

作为真正的分布外检测。

---

# 18. 阶段 M6：配方枚举与推荐器

执行：

```bash
python scripts/05_build_optimizer.py
```

当前阶段更准确的名称是：

```text
Discrete Design-Space Ranker
```

而不是连续优化器。

## 18.1 设计变量

仍表示为：

```text
g = green_g
w = white_g
o = oolong_g
b = black_g
```

但只允许取数据集定义的离散用量。

必须满足：

```text
g + w + o + b = 4.0 g
```

比例展示时：

```text
green_pct = g / 4.0
...
```

## 18.2 搜索空间

**第一版搜索空间必须且只能是32个合法格点。**

禁止使用：

```text
0.025 proportion step
连续盒约束
Differential Evolution
任意实数比例搜索
```

因为这些方法会产生当前实验设计无法制造/无法验证的组合。

Agent 应：

1. 自动枚举32个合法点；
2. 与30个已观测点做集合差；
3. 自动得到2个未观测合法点；
4. 对32个点逐一计算推荐信息。

## 18.3 实测优先，预测补缺

对每个候选：

### 如果 `OBSERVED`

直接采用：

```text
measured chemistry
measured sensory mean
measured sensory std
```

推荐依据中明确：

```text
evidence_type = MEASURED
```

模型预测可作为对照：

```text
cv/model estimate
```

但不得用预测覆盖真实实验值。

### 如果 `UNOBSERVED_VALID`

使用：

```text
Recipe -> Chemistry prediction
Recipe -> Sensory prediction
uncertainty
Path A / Path B disagreement
nearest observed recipes
```

并标记：

```text
evidence_type = PREDICTED
```

## 18.4 排名逻辑

第一版推荐排序原则：

```text
1. 满足用户原料约束
2. 满足可用且可靠的理化约束
3. 在32点合法设计空间内
4. 按目标函数排序
5. 对预测点应用风险惩罚
```

建议：

```text
OBSERVED candidate:
ranking_score = measured_objective

UNOBSERVED_VALID candidate:
ranking_score =
predicted_objective
- lambda * uncertainty
- gamma * model_disagreement
```

因此系统不会因为模型高估某个未测点，就轻易把它排在高质量实测点之前。

## 18.5 32点全表输出

必须生成：

```text
artifacts/optimization/design_space_32.csv
```

至少包含：

```text
green_g
white_g
oolong_g
black_g
green_pct
white_pct
oolong_pct
black_pct
design_status
evidence_type
sample_code_if_observed
objective_value
objective_uncertainty
nearest_sample
ranking_score
```

## 18.6 最优下一次实验

因为只缺2个合法格点，系统必须额外输出：

```text
next_experiments.csv
```

默认优先级就是这两个未测点。

原因不是它们一定最优，而是：

> 一旦完成这2个实验，当前32点离散设计空间将达到100%实测覆盖。

届时，对当前固定步长设计空间内的“最优配方选择”，可直接基于实测数据完成，而不再依赖机器学习预测。

## 18.7 未来何时才需要连续优化

只有出现以下任一变化才重新启用连续/多目标优化：

```text
厂家允许更细的称量步长
总配方质量不固定为4g
新增更多原料
加入工艺连续变量
加入成本/库存连续约束
```

届时可考虑：

```text
Bayesian Optimization
Differential Evolution
NSGA-II
```

当前版本不实现为默认推荐路径。

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
0.17647 * appearance
+ 0.17647 * infusion_color
+ 0.23529 * aroma
+ 0.41177 * taste
```

**该权重只是系统用户自定义目标函数，不允许声称是数据集中 Overall score 的计算公式。Solubility 不可用于模型驱动的加权推荐。**

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
Design-space status
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

| Rank | Green | White | Oolong | Black | Evidence | Overall | Uncertainty | Risk Score | Design status | Nearest |
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
13. 32点离散设计空间、实测/预测状态与可制造性判定；
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

### Gate B 可信度检查

除报告原始 LOO MAE/RMSE 门槛外，必须在同一行联合置换五项建模感官均值，并在每次置换中重跑候选模型和逐目标模型选择，报告经验 p 值；同时输出 30 个留出配方各自的误差、误差改善分布和删一评估折敏感性。置换检验 `p < 0.05` 才能通过模型驱动的未观测点推荐可信度门槛；否则预测可作为实验估计展示，但不得进入自动 Top-K。

还必须给出不依赖预测模型族的 Mantel 距离关联检验：比较四维配方距离和五维标准化感官均值距离，以联合行置换求经验 p 值。若不显著，表述为“当前样本未检测到显著的配方—感官距离关联”，不可写成已证明关联不存在；该检验不能替代 OOF 预测验证。

### 感官评分噪声分解与采数优先级

对 597 条重复评分按配方估计配方间方差和配方内评分方差，并报告配方均值可靠度。由于没有评价者 ID，配方内项必须标注为评分差异与残差的合并量，不可声称为纯评价者噪声。根据独立样本单位是配方这一点，后续数据收集优先扩大独立配方数；若某目标配方均值精度仍不足，再增加该配方的评价次数。`solubility` 仍保存在描述数据中，但不作为模型目标。

## Gate C：优化器有效

必须满足：

- 所有候选比例和=1；
- 无负值；
- 满足约束；
- 必须属于32个合法离散格点；
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

最终报告和UI必须准确区分“当前离散空间覆盖率”和“外部适用范围”。

必须明确：

1. 独立实测配方只有30个；
2. **当前定义的32点离散设计空间已经覆盖30点，覆盖率93.75%，并非“配方空间覆盖有限”；**
3. 尚缺2个合法格点，未完成100%覆盖；
4. 当前设计空间本身非常狭窄：仅4种茶、固定总质量4.0 g、固定0.5 g称量步长；
5. 不能根据本数据推断0.25 g、0.1 g或任意连续比例下的表现；
6. 不能根据本数据推断新增第五种原料后的配方行为；
7. 缺少独立原料批次变化；
8. 缺少生产工艺变量；
9. 缺少成本；
10. 缺少库存；
11. 缺少货架期/稳定性；
12. 缺少消费者数据；
13. 597条感官记录并非597个独立产品；
14. S30评价次数为17，与其他样品不同；
15. 无评价者ID，无法建模评价者偏差；
16. Leave-One-Blend-Out 只能证明在当前离散设计内部的重建/插值能力，不能证明对工业连续配方空间的泛化；
17. 对两个未观测合法格点的预测，在真实实验完成前仍未得到直接验证；
18. 所有预测候选仍需通过真实实验验证。

### 最关键的下一步实验

优先实际制作并检测：

```text
(0.5, 1.0, 1.5, 1.0) g
(0.5, 1.5, 0.5, 1.5) g
```

一旦获得这两个点的完整理化与感官数据：

```text
当前32点设计空间覆盖率 = 100%
```

此时在**当前固定离散空间内**选择最优配方，本质上可以直接对全部实测结果进行排序，无需依赖ML来“寻找”最优点。

机器学习的价值将主要转向：

- 解释成分—感官关系；
- 估计测量噪声；
- 为未来扩展的新设计空间提供先验；
- 在厂家新增原料、批次、工艺和更细比例后进行真正的预测与优化。

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
- [ ] 32点合法设计空间自动枚举完成；
- [ ] 30个OBSERVED与2个UNOBSERVED_VALID自动识别完成；
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
建立32点设计空间枚举 + OBSERVED/UNOBSERVED_VALID/INVALID状态 + KNN解释

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

> **在32个合法离散配方点中已有30个实测点的前提下，模型能否在 Leave-One-Blend-Out 中稳定重建被留出的合法格点，并对剩余2个合法未观测点给出有意义且带不确定性的补全预测？**

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
           Uncertainty + Design status
                     │
                     ▼
              32-point Design Ranker
                     │
                     ▼
               Measured/Predicted Top-K
                     │
                     ▼
                Streamlit Demo
```

---

**执行优先级：正确验证 > 模型复杂度 > GPU利用率 > LLM微调。**
