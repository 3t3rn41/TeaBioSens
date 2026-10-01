# TeaBioSens 茶叶智能拼配原型 — 项目进度报告

> **报告日期**：2026-10-01
> **项目阶段**：V0.4 原型验证（含可信度验证）
> **数据源**：`TeaBioSens.xlsx`（30 个独立拼配样品 / 597 条感官评分）
> **代码仓库**：`github.com/3t3rn41/TeaBioSens`（private，最新提交 `5606bc8`）
> **硬件**：远端单卡 RTX 4090 24GB（**已于 2026-10-01 释放**）
> **本报告状态**：远端主机已释放，内容依据执行期间的实际产物与日志整理；未标注"待复核"的数值均来自已落盘的产物文件。

---

## 0. 执行摘要

本项目在一天内完成了从数据审计到可演示原型的**全流程实现**，并额外完成了一轮**可信度验证**——后者是本项目最有价值的产出。

**三句话结论：**

1. **系统已建成且可复现**：完整的 `recipe → chemistry → sensory` 预测链、32 点设计空间枚举、受约束优化器、Streamlit Demo，端到端约 55 分钟（纯 CPU，GPU 0%），12 项测试全部通过。
2. **核心预测能力未被证实**：直接 Recipe→Sensory 模型在数值上"通过"了预设的 Gate B（5/5 目标同时改善 MAE 与 RMSE），但**200 次联合标签置换检验显示，打乱标签后仍有 96/200（48%）的置换能通过 Gate B（p = 0.4826）**——该门槛不构成预测能力的证据。据此**自动预测推荐已被关闭**。
3. **数据瓶颈已定量定位**：感官测量本身是可靠的（`overall_score` 的 20 次评分均值信度 **0.944**），因此瓶颈不是评价者数量，而是**独立配方数量**，且可能还缺少**配方之外的变量**（原料等级/批次、工艺参数）——因为配方与感官之间只存在**弱关联**（Mantel 全局 r = 0.117，p = 0.0512，经 Holm 校正后不显著）。

**一句话**：这不是"算法失败"，而是**一个诚实的可行性验证**——它证明了当前公开数据不足以支撑可靠的自动推荐，并精确说明了需要什么数据。

---

## 1. 项目目标与范围

### 1.1 目标

建立一个可验证的茶叶智能拼配 Proof of Concept：

```
四种茶的配比 → 理化成分预测 → 感官品质预测 → 不确定性/OOD → 受约束优化器 → Top-K 候选配方 → Streamlit Demo
```

### 1.2 明确非目标（V0.1–V0.4）

不训练大语言模型、不产出工业生产级配方、不做法规合规结论、不做真实成本/库存优化、不做辅料优化、不做消费者偏好模型、不做多模态视觉/光谱模型。

### 1.3 总原则

**先完成结构化数据建模、品质预测和受约束配方优化，再考虑大语言模型微调。**

执行优先级：**正确验证 > 模型复杂度 > GPU 利用率 > LLM 微调**。

---

## 2. 数据：已核验的事实

### 2.1 原始文件

| 项 | 值 |
|---|---|
| 文件 | `TeaBioSens.xlsx`（97,870 字节） |
| 工作表 | `Sheet1`（**仅此一个**，无隐藏表） |
| 行 × 列 | 598 × 30（1 表头 + **597 数据行**） |
| 独立配方 | **30 个**（`S1`–`S30`） |
| 评分分布 | S1–S29 各 20 条；**S30 为 17 条** |
| 缺失值 | 0 |
| 完全重复评分行 | 5 行（保留，不影响独立配方数） |
| SHA256 | `956415251daeb7463f2d7f6a9c13c84f10e404258442d04b01e9999f12dea0b1` |

### 2.2 字段结构

- **样品 ID**（1 列）：`Sample code`
- **配方输入**（4 列）：`Green tea` / `White tea` / `Oolong tea` / `Black tea`，单位 g，**每行和恒为 4.0 g**
- **理化指标**（19 列）：15 个基础指标 + 4 个派生比值
- **感官指标**（6 列）：`Appearance` / `Infusion color` / `Aroma` / `Taste` / `Solubility` / `Overall score`

**关键结构性事实**：同一 `Sample code` 内，19 个理化指标**完全相同**（配方级实验数据），只有 6 个感官指标在不同评价行间变化。

> **因此 597 行 ≠ 597 个独立配方。可用于 `Recipe → Chemistry` 的独立样本量只有 n = 30。**

### 2.3 派生比值字段（已逐项核对公式）

```
TP/theanine = TP (mgGAE/g) / L-theanine (mg/g)
CAF/TP      = Caffeine % / TP (mgGAE/g)
Protein/TP  = Protein (μg/g) / TP (mgGAE/g)
TF/TR       = TF % / TR %
```

**建模原则**：优先预测 15 个基础指标，再据此重算 4 个比值；禁止默认训练 19 个独立回归器后让比值与分子/分母产生逻辑冲突。

---

## 3. ★ 核心结构性发现：设计空间是 32 点离散格点

这是本项目最关键的结构性发现，由独立枚举核验得出（并已被写入 V2 说明书）。

### 3.1 格点枚举

原料以 **0.5 g 为步长**，四者和恒为 4.0 g：

| 原料 | 水平 | 最小 | 最大 |
|---|---|---|---|
| Green | {0.5, 1.0, 1.5, 2.0} | 12.5% | 50% |
| White | {0.5, 1.0, 1.5, 2.0} | 12.5% | 50% |
| Oolong | {0.5, 1.0, 1.5, 2.0} | 12.5% | 50% |
| Black | {0.5, 1.0, 1.5, 2.0, 2.5} | 12.5% | 62.5% |

满足 `sum = 4.0 g` 的组合**恰好 32 个**，**30 个已观测（覆盖率 93.75%）**，且 30 个观测点**全部精确落在格点上**（无一例外）。

### 3.2 缺失的 2 个格点

```
(0.5, 1.0, 1.5, 1.0)   # Green / White / Oolong / Black，单位 g
(0.5, 1.5, 0.5, 1.5)
```

**缺口完全集中在 `green = 0.5` 这一个切片**：该切片 13 个格点中 11 个已观测；其余三个 green 水平（1.0 / 1.5 / 2.0）合计 19 个格点 **100% 全覆盖**。

### 3.3 这推翻了原方案的哪些假设

原说明书（V1）把"配方空间覆盖有限"列为局限，并设计了连续空间的优化器。实际情况**恰恰相反**：

| 原假设 | 修正后 |
|---|---|
| "Leave-One-Blend-Out 泛化到未见配方" | 实际是**在几乎铺满的离散格点上做插值**；真正的"未见配方"只有 2 个，无法用于验证泛化 |
| 优化器用 0.025 步长的**连续网格** | 会生成 0.125/0.3/0.225/0.35 这类**物理上无法配料**的组合；搜索空间应为**这 32 个格点** |
| Convex Hull 作为 OOD 主判定 | 对格点几乎失效；已改为三态分类 `OBSERVED` / `UNOBSERVED_VALID` / `INVALID_DESIGN_POINT` |

**修正后的准确定位**：这是一个**离散设计空间的补全与排序原型**，不是连续配方优化器。

---

## 4. 系统实现（V0.4）

### 4.1 项目结构

```
tea-ai/
├── README.md / PROJECT_SPEC.md / pyproject.toml / requirements.txt
├── data/
│   ├── raw/TeaBioSens.xlsx           原始数据（只读）
│   ├── processed/                    teabiosens_clean.csv / blend_master.csv /
│   │                                 sensory_observations.csv / dataset_manifest.json
│   └── confirmatory_teabiosens/      两个缺失格点的空白录入模板（S31 / S32）
├── configs/                          default.yaml / feature_schema.yaml
├── src/tea_ai/
│   ├── constants.py / io.py / validation.py / preprocessing.py / features.py
│   ├── metrics.py / cv.py / uncertainty.py / ood.py / optimization.py
│   ├── inference.py / diagnostics.py / design_space.py
│   └── models/                       chemistry.py / sensory.py / direct_recipe.py
│                                     mixture.py（Scheffé）/ common.py / training.py
├── scripts/                          00_audit … 10_sensory_noise_decomposition
├── artifacts/                        models / predictions / optimization / reports / runs
├── app/                              app.py / components.py（Streamlit）
└── tests/                            9 个测试文件
```

### 4.2 处理链

| 脚本 | 作用 |
|---|---|
| `00_audit_data.py` | 数据审计 + 契约校验 |
| `01_build_datasets.py` | 构建 clean / blend_master（30 行）/ sensory_observations（597 行） |
| `02_train_recipe_chemistry.py` | Recipe → Chemistry |
| `03_train_chemistry_sensory.py` | Chemistry → Sensory |
| `04_train_recipe_sensory.py` | Recipe → Sensory（直接模型） |
| `05_build_optimizer.py` | 32 点设计空间枚举 + 排序 |
| `06_generate_report.py` | 生成 `final_report.md` |
| `07_run_full_pipeline.py` | 端到端全流程（含下列两项验证） |
| `08_validate_gate_b.py` | 联合标签置换检验 + 逐折敏感性 |
| `09_validate_recipe_sensory_association.py` | 无模型 Mantel 关联检验 |
| `10_sensory_noise_decomposition.py` | 感官噪声方差分解 |

### 4.3 验证协议（防泄漏）

- **禁止**对 597 行直接随机拆分。
- `Recipe → Chemistry` 与 `Recipe → Sensory`：**Leave-One-Blend-Out**（n=30）。
- `Chemistry → Sensory`：**LeaveOneGroupOut**，`groups = sample_code`（测试集是完整未见配方）。
- 标准化 / 特征选择 / 超参搜索全部放在 sklearn `Pipeline` 内，**每个 CV 折内部拟合**。
- 所有指标均来自合并后的 OOF 预测；逐折 R² 不单独计算（单样品折无意义），R² 在完整 OOF 向量上统一计算。
- 全部随机过程 `random_state = 42`。

### 4.4 测试

`pytest -q` → **12 passed in 4.91s**，覆盖 9 个文件：

```
test_dataset_contract (2)  test_design_space (1)   test_features (2)
test_inference (1)         test_no_leakage (1)     test_optimizer (1)
test_ratios (2)            test_streamlit_app (1)  test_training_artifacts (1)
test_scheffe_model (1)
```

其中 `test_no_leakage` 验证 `train sample codes ∩ test sample codes == ∅` 在每折恒成立。

---

## 5. 实验结果

### 5.1 Gate A：数据有效 — **PASS**

契约全部通过：597 行 / 30 列 / 30 独立样品 / 无缺失 / 四者和恒为 4.0 g / 比例和恒为 1 / 同样品理化恒定 / 比值公式一致。审计状态 `PASS_WITH_WARNINGS`（5 条完全重复评分行）。

### 5.2 Recipe → Chemistry（M3）

**结果：8/15 个基础理化指标同时改善 OOF MAE 与 RMSE，其余 7 个未能超过均值基线。**

| 改善（8 个） | 未改善（7 个） |
|---|---|
| `caffeine_pct`、`catechin_pct`、`citric_acid`、`galic_acid`、`oxalic_acid`、`ph`、`tf_pct`、`tr_pct` | `protein_ug_g`、`tss_ug_g`、`tp_mggae_g`、`malic_acid_mg_g`、`ascorbic_acid_mg_g`、`succinic_acid_mg_g`、`l_theanine_mg_g` |

**重要**：为修正模型误设，专门实现了**二阶 Scheffé 混合模型**
```
sum(beta_i * x_i) + sum(beta_ij * x_i * x_j)    无截距
```
（10 项 = 4 线性 + 6 交互，已由 `test_scheffe_model.py` 验证）。**它并未胜出**——多数目标仍不如 `ridge_a` / `pls`。例如：

| 目标 | Scheffé MAE | 最优模型 MAE |
|---|---:|---:|
| `caffeine_pct` | 1.194 | **0.973**（pls） |
| `tf_pct` | 0.089 | **0.067**（ridge_a） |
| `tr_pct` | 0.698 | **0.553**（ridge_a） |

> 即：**换用正确的模型类之后，Recipe→Chemistry 依然不可学。** 这让"数据不足"的结论更硬。

**下游影响**：优化器仅把上述 **8 个**指标列为 `reliable_chemistry_constraints`，其余 7 个不得作为硬约束——符合"不可靠指标不得作硬约束"的要求。

### 5.3 Chemistry → Sensory（M4）

**结果：这是三条链路中最强的一环。** 以 `overall_score` 为例：

| 模型 | OOF MAE | OOF RMSE | R² |
|---|---:|---:|---:|
| 均值基线 | 6.653 | 7.314 | −0.070 |
| **`chemistry_a:pls`** | **3.358** | **4.153** | **0.655** |
| `chemistry_a:gpr` | 3.749 | 4.491 | 0.597 |
| `chemistry_a:ridge` | 4.294 | 5.104 | 0.479 |

`taste` R² ≈ 0.66，`aroma` R² ≈ 0.58，同样显著优于基线。

### 5.4 Recipe → Sensory（M5）与 Gate B

**数值门槛结果**：5/5 目标同时改善 OOF MAE 与 RMSE（原为 6/6，`solubility` 后被剔除，见 5.7）。

| 目标 | 选中模型 | MAE 改善 | RMSE 改善 | 逐折取胜 | 删一折后仍改善 |
|---|---|---:|---:|---:|---:|
| `overall_score` | `pls` | 2.068 | 1.410 | 23/30 | 30/30 |
| `taste` | `ridge_a` | 2.808 | 2.502 | 23/30 | 30/30 |
| `aroma` | `catboost` | 1.488 | 0.898 | 21/30 | 30/30 |
| `infusion_color` | `pls` | 1.219 | 0.691 | 20/30 | 30/30 |
| `appearance` | `catboost` | 1.107 | 1.307 | 18/30 | 30/30 |

> 注意：**逐折取胜只有 18–23 / 30（60%–77%）**，并非压倒性；改善还集中在少数样品上（`appearance` 的 top-3 样品贡献了 47% 的总平方误差收益）。

**但这一结果在可信度验证中被推翻**（见 5.5）。

### 5.5 ★ 可信度验证一：联合标签置换检验

**方法**：200 次联合行置换（六项/五项感官结果**保持同行**打乱，配方行固定），**每次置换内部重跑完整的模型族选择规则**——因此该方法已把"选择偏差"计入零假设。经验 p 值 = (1 + 超越次数) / (B + 1)。

| 统计量 | 观测 | 零假设下出现 | **经验 p** | 零假设 95% 精确区间 |
|---|---|---|---|---|
| 5/5 目标同时改善 | true | 30 / 200 | **0.1542** | — |
| **Overall 通过 Gate B** | true | **96 / 200** | **0.4826** | [0.409, 0.552] |

> **打乱标签后仍有 96/200 = 48% 的置换"通过 Gate B"。**

**原因**：Gate B 是拿"从 ~7 个模型族中逐折挑选最优"去比**均值基线**。在 n=30 的 LOO 下，**选择偏差本身**就足以让约一半的随机置换"赢过基线"。

**后果**：`ai_recommendation_enabled` 由 `true` **改为 `false`**，自动预测推荐关闭。

**值得肯定的一点**：后为剔除 `solubility` 而将目标从 6 个减到 5 个后，p 值从 0.0995 **变差**到 0.1542——说明该调整是**按数据质量而非按 p 值**做的决定。

### 5.6 ★ 可信度验证二：无模型 Mantel 关联检验

**方法**：不依赖任何模型，直接检验配方距离矩阵与感官距离矩阵的关联（Mantel Pearson，4999 次联合行置换）。

| 范围 | Mantel r | 原始 p | Holm 校正 p |
|---|---:|---:|---:|
| **全局多变量（5 目标）** | **0.1169** | **0.0512** | — |
| `taste` | **0.1561** | **0.0160** | 0.0800 |
| `overall_score` | **0.1231** | **0.0262** | 0.1048 |
| `infusion_color` | 0.1246 | 0.0546 | 0.1638 |
| `appearance` | 0.0728 | 0.3168 | 0.6336 |
| `aroma` | 0.0462 | 0.4554 | 0.6336 |

**解读（重要）**：

- **配方与感官之间存在"弱但可检测"的关联**——全局 p = 0.0512 卡在边缘，`taste`（p=0.016）与 `overall_score`（p=0.026）单目标原始 p 显著。
- **但没有任何一个通过 Holm 多重比较校正**（最小校正 p = 0.080）。
- **准确表述**：关联存在但**极弱**（r ≈ 0.12–0.16），**远不足以支撑预测**。

脚本自身也记录了正确的解释边界：
> *"A non-significant test means this sample did not detect distance association at the chosen threshold; it does not establish that association is absent and does not test causality or predictive performance."*

### 5.7 ★ 可信度验证三：感官噪声方差分解

**方法**：非平衡单因素随机效应 ANOVA（矩估计），区分**配方间方差**与**配方内（评分）方差**。

| 目标 | 组间方差占比 (ICC) | **20 次评分均值信度** | 达到 5× 裕度所需评分者 |
|---|---:|---:|---:|
| **`overall_score`** | **0.459** | **0.944** | **2** |
| `taste` | 0.414 | 0.934 | 2 |
| `aroma` | 0.255 | 0.872 | 3 |
| `infusion_color` | 0.222 | 0.850 | 4 |
| `appearance` | 0.167 | 0.799 | 5 |
| **`solubility`** | **0.042** | **0.467** | 23 |

**两个决定性结论**：

1. **感官测量不是瓶颈。** `overall_score` 的 20 次评分均值信度高达 **0.944**，2 个评分者就足以达到 5× 裕度——现有 20 个评分**绰绰有余**。所以"要更多评价者"是错的。
2. **`solubility` 基本是噪声**（ICC 0.042、信度 0.467），已**从建模目标中剔除**。

> 方法学局限（脚本已注明）：无评价者 ID，因此无法分离评价者、场次、测量效应；配方内方差 = 评分离散 + 残差。

---

## 6. 综合结论

### 6.1 可以主张的

1. 建成了一条**可复现、无数据泄漏、有基线、有不确定性、有测试**的完整原型管线（端到端约 55 分钟，纯 CPU）。
2. **离散设计空间已被精确刻画**：32 个合法格点，30 个已观测（93.75%），缺口精确定位在 `green = 0.5` 切片。
3. **30 个已观测配方的实测排序是真实数据**（不依赖模型），可以直接交付。
4. **当前数据不足以支撑可靠的自动配方推荐**——这一结论由三重独立验证支撑（置换检验、Mantel、噪声分解），且已量化。
5. **瓶颈定位清楚**：不是评价者数量，而是独立配方数量；且因关联本身极弱，**可能还缺少配方之外的变量**。

### 6.2 不能主张的

- ❌ **不能**说"AI 配方推荐可用"——Gate B 的数值 PASS 已被置换检验证伪（p=0.48）。
- ❌ **不能**把 Gate B 的 PASS 当卖点，也不能只看这一个门槛。
- ❌ **不能**说"配方与感官无关联"——Mantel 显示存在弱关联（r≈0.12），只是不足以预测。
- ❌ **不能**把 93.75% 覆盖率包装成模型能力。
- ❌ **不能**把 597 行当作 597 个独立产品。
- ❌ **不能**把 GPR 的 predictive spread 说成"置信区间"——它是模型估计的离散度，**未经覆盖率校准**。
- ❌ **不能**把结果外推到 0.25 g / 0.1 g 步长、连续比例、第五种原料或工业生产。

### 6.3 交付判定（沿用项目自身口径）

| 判定 | 结果 |
|---|---|
| Demo 可演示 | **是** |
| 原始 Gate B 数值门槛 | PASS |
| **自动预测推荐可信度** | **未通过**（推荐功能已关闭，仅展示实测排序） |
| 指导实验 | 预测点**仅用于安排两项验证实验**，不作为生产依据 |

---

## 7. 主要局限

1. 独立实测配方只有 30 个；离散空间覆盖率 93.75%，尚差 2 点。
2. 设计空间狭窄：四种茶、固定 4.0 g 总量、固定 0.5 g 步长。
3. 缺少：第五种原料、原料批次、生产工艺参数、成本、库存、稳定性/货架期、消费者数据。
4. 597 条感官记录并非 597 个独立产品；S30 评分次数为 17（其余 20）。
5. 缺少评价者 ID，无法建模评价者偏差。
6. Leave-One-Blend-Out 只验证**离散空间内部重建**，不证明对任意新配方的泛化。
7. 两个缺失格点的预测在实际实验前**未经直接验证**。
8. 置换检验是**条件性零假设检验**（假设无关联下配方标签可交换），**不能替代外部确认集**。
9. `solubility` 因信度过低已被剔除，**该指标的建模结论不成立**。
10. 所有候选配方均需真实研发与法规验证。

---

## 8. 厂家数据需求（按优先级）

### 8.1 结论先行

**不要更多感官评分，要更多独立配方；而且很可能还要配方之外的变量。**

依据：`overall_score` 的 20 次评分均值信度已达 **0.944**（2 个评分者即足够），而配方↔感官关联仅 r ≈ 0.12。

### 8.2 需求清单

| 优先级 | 需求 | 理由 |
|---|---|---|
| 1 | **两个缺失格点的完整理化和感官实测**（`S31` = 0.5/1.5/0.5/1.5，`S32` = 0.5/1.0/1.5/1.0） | 使当前离散空间达 100% 覆盖（**仅补全，不提升模型能力**） |
| 2 | **更多独立配方**，且**超出当前 0.5 g 步长**（如 0.25 g 步长） | 30 点在 4 维混合空间中过于稀疏；填满 32 点仍是同一个格子 |
| 3 | **原料批次变化** | 现在每种茶只有一个批次，无法区分"配方效应"与"批次效应"——这很可能是关联极弱的真正原因 |
| 4 | **生产工艺参数**（温度、时间、水料比等） | 品质很可能主要由工艺而非配比决定 |
| 5 | **标准化感官评价方案 + 评价者 ID** | 便于建模评价者偏差；但**当前评价者数量已足够** |
| 6 | 成本、库存、稳定性/货架期、是否量产 | V1.x 的企业级建模所需 |

### 8.3 已备好的录入模板

`data/confirmatory_teabiosens/` 下已备好 `blend_measurements_template.csv` 与 `sensory_ratings_template.csv`，要求：
- 填 15 个基础理化实测值（比值由项目按实测分子/分母计算，**不得用预测值代填**）；
- 每个配方 20 条**独立原始评分**（0–100），**不得只填平均值**；
- 保持 `sample_code` 一致；若实验/冲泡/检测条件与历史不同须注明。

> 模板目录 README 明确写着：*"以下 CSV 只是空白录入模板，不代表测量值，**不能据此把覆盖率记为 100%**"*，且*"未观测格点只有在获得真实检测和感官记录后才计入覆盖率"*。

---

## 9. 交付物清单

| 类别 | 路径 |
|---|---|
| 数据 | `data/processed/`（clean / blend_master / sensory_observations / manifest） |
| 审计 | `artifacts/reports/data_audit.{json,md}` |
| 模型 | `artifacts/models/{chemistry,sensory,direct_recipe}/`（`model.joblib` + `metadata.json` + `metrics.json` + `feature_order.json`） |
| OOF 预测 | `artifacts/predictions/`（三任务 OOF + 逐样本误差表 + 逐评分误差） |
| 优化 | `artifacts/optimization/`（`design_space_32.csv`、`top_candidates.csv`、`next_experiments.csv`、`optimization_summary.json`） |
| 报告 | `artifacts/reports/final_report.md` + 各阶段报告 |
| **可信度验证** | `artifacts/reports/gate_b_validation/`（置换分布、可信度结论、逐折与删折敏感性） |
| **关联检验** | `artifacts/reports/recipe_sensory_mantel/` |
| **噪声分解** | `artifacts/reports/sensory_noise_decomposition/` |
| 补测模板 | `data/confirmatory_teabiosens/` |
| Demo | `app/app.py`（`streamlit run app/app.py`） |
| 复现 | `python scripts/07_run_full_pipeline.py`；测试 `pytest -q` |

### 9.1 关键结果速查

- **Top-1 实测配方**：`S16`（Green/White/Oolong/Black = **1/1/1/1 g**），Overall = **82.596**
- **前 10 名全部是实测点**（非模型预测）
- **两个待补测格点预测值**：`(0.5,1.5,0.5,1.5)` → 79.547；`(0.5,1.0,1.5,1.0)` → 74.463
  （**仅为待验证假设**，其理化输入本身由不可靠的 Recipe→Chemistry 模型预测）

---

## 10. 工程状态与遗留问题

### 10.1 版本控制

仓库 `github.com/3t3rn41/TeaBioSens`（**private**），提交历史：

| 提交 | 内容 |
|---|---|
| `be1bd36` | 初始导入（V2 离散设计空间版说明书 + 首版实现） |
| `4f04e3c` | V0.4 全流程结果（Gate B 数值 PASS） |
| `dc5a58d` | 置换检验证伪 Gate B + Scheffé 模型 + 补测模板 |
| `5606bc8` | Mantel 关联检验 + 感官噪声分解 + 5 目标置换重跑 |

### 10.2 ★ 遗留问题（需注意）

1. **工作目录分裂未解决。** 代码生成方（codex）始终在 `~/work` 工作，而版本库在 `~/teabiosens`。两者需要**人工单向同步**，期间多次出现"成果只在 `~/work`、不在仓库"的窗口期。**随着远端主机释放，这一风险已不再存在**，但若未来重建环境，应从一开始就统一目录。
2. **远端主机已释放。** 全部实验产物、`.venv`、`runs/` 随主机一同消失。**当前唯一持久化副本是 GitHub 私有仓库**（含代码、处理后的数据、模型、预测、报告与全部验证产物）。原始 `TeaBioSens.xlsx` 已随仓库保存（`data/raw/` 与根目录各一份）。
3. **未完成项**：Streamlit 从未实际启动过服务（仅有单元测试通过）；说明书 §40 要求的 11 项交付汇报未单独产出。

### 10.3 若需重建环境

```bash
git clone https://github.com/3t3rn41/TeaBioSens.git
cd TeaBioSens
pip install -r requirements.txt
pytest -q
python scripts/07_run_full_pipeline.py      # 约 55 分钟，纯 CPU
streamlit run app/app.py
```
GPU 非必需（本阶段 GPU 利用率全程 0%，仅持有一个约 0.4 GB 的空转 CUDA context）。

---

## 附录 A：基础设施沿革（本机）

本项目的执行环境是一台远端 GPU 主机（`39.156.149.45:10961`，RTX 4090 24GB），该主机此前承载了另一个已于本日终止的项目。执行期间处理过两次环境故障，记录如下以备将来重建：

| 故障 | 根因 | 处置 |
|---|---|---|
| `nvidia-smi` 报 `Driver/library version mismatch` | 系统升级后已加载内核模块为旧版 580.159.03，用户态库与磁盘模块为新版 580.173.02 | 重载内核模块（`rmmod` → `modprobe`），无需重启 |
| codex 报 `workspace routing discovery timed out (-32603)` | ① 代理上游节点失联；② codex app-server 守护进程早于代理上线启动，环境中无 proxy 变量 | 切换可用代理节点；带代理变量重启守护进程 |

---

## 附录 B：方法与诚实性说明

本报告的所有数值均取自执行期间落盘的产物文件（CSV / JSON / MD），未做二次估算或美化。三处需要读者特别注意的方法学边界：

1. **置换检验的零假设是条件性的**——假设"无关联时配方标签可交换"。它**不能**替代外部确认集。
2. **Mantel 检验的非显著结果不等于"无关联"**——只能说该样本在所选阈值下未检测到距离关联。
3. **噪声分解无法分离评价者/场次效应**（缺少评价者 ID），配方内方差是评分离散与残差的混合。

**最后一点说明**：本项目最有价值的产出不是"一个能推荐配方的 AI"，而是**在投入更多资源之前，用三重独立验证证明了当前数据不足以支撑该目标，并定量说明了缺口在哪里**。这正是一个 PoC 应当发挥的作用。

---

*报告生成时间：2026-10-01 21:45 (CST) ｜ 依据：执行期间全部落盘产物与日志*
