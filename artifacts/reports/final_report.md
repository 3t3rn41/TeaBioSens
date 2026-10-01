# TeaBioSens 茶叶智能拼配 V0.4 原型报告

生成日期：2026-10-01 13:32 UTC

> 本报告中的预测均为当前公开数据和当前实验设计内的模型估计。配方仅为建模/实验候选，未经食品研发实验和法规验证，不用于直接生产。

## 1. 数据审计与样本量

- 来源：`/home/ubuntu/work/data/raw/TeaBioSens.xlsx`；SHA256：`956415251daeb7463f2d7f6a9c13c84f10e404258442d04b01e9999f12dea0b1`。
- Sheet1：597 行评分记录、30 列、30 个独立样品，无缺失。
- 完全重复评分记录：5 行，作为源数据保留；评分重复不改变独立配方数。
- 独立实验配方数为 30。S1–S29 各有 20 条评分，S30 有 17 条。
- 四种茶配方总质量均为 4.0 g，19 个理化字段在同一 `sample_code` 内恒定。4 个派生比值经逐项公式核对。

### 感官评分方差分解与建模目标

下表用不平衡单因素随机效应 ANOVA 矩估计，将评分变异分为配方间方差与同配方内评分方差。评价者 ID 缺失，因此同配方内项包含评价者差异及其他残差，不能解释为纯测量误差。

| 感官项 | 配方间方差 | 同配方内评分方差 | 配方间占比 | 同配方内占比 | 配方均值可靠度（当前评分数） | 达到均值标准误低于配方间标准差所需评分数* |
|---|---:|---:|---:|---:|---:|---:|
| `appearance` | 21.136 | 105.483 | 16.7% | 83.3% | 0.799 | 5 |
| `infusion_color` | 33.457 | 117.188 | 22.2% | 77.8% | 0.850 | 4 |
| `aroma` | 57.777 | 169.089 | 25.5% | 74.5% | 0.872 | 3 |
| `taste` | 120.570 | 170.596 | 41.4% | 58.6% | 0.934 | 2 |
| `solubility` | 6.675 | 151.448 | 4.2% | 95.8% | 0.467 | 23 |
| `overall_score` | 48.772 | 57.405 | 45.9% | 54.1% | 0.944 | 2 |

* 这是方差分量下的精度参考，不是正式样本量/功效分析。当前每个配方约有 20 条评分；除 solubility 外，配方均值可靠度约为 0.80–0.94。最优先增加独立配方数，因为重复评价不能增加独立配方样本量。
Solubility 的配方间方差占比仅 4.2%，当前配方均值可靠度约 0.467；所以它保留为测量和描述字段，但从 M4/M5 训练、Gate B 与推荐目标中剔除。其余五项构成建模目标。

### 离散设计空间

- 程序从原料用量水平与 4.0 g 总质量约束中重新枚举出 32 个合法格点。
- 当前观测 30 点，覆盖率 93.75%；这是当前定义离散空间的覆盖率，不代表工业配方范围。
- 缺失合法点：`[[0.5, 1.0, 1.5, 1.0], [0.5, 1.5, 0.5, 1.5]]` g。

## 2. 验证含义与泄漏控制

597 行数据没有按行随机拆分。Recipe→Chemistry 和 Recipe→Sensory 使用 30 个独立配方的 Leave-One-Out；Chemistry→Sensory 按 `sample_code` 分组，每折留出整组。
所有指标均来自合并后的 OOF 预测。标准化通过 sklearn Pipeline 在训练折内拟合；Recipe→Chemistry 的 GPR 不确定性模型和 Chemistry→Sensory 的 GPR 使用每个独立配方的聚合均值。
这些结果评估的是 `within-design reconstruction`：在当前合法离散空间内留出已观测格点后的重建能力，不证明对任意连续新配方或工业配方的泛化。

## 3. Recipe → Chemistry

验证：LeaveOneOut by unique sample_code (n=30; within-design reconstruction)。主目标为 15 个基础理化指标；4 个派生 ratio 在推理时由预测分子和分母重建。
### 按目标比较的 OOF 指标

| Target | Model | MAE | RMSE | R² | Spearman |
|---|---|---:|---:|---:|---:|
| `protein_ug_g` | `mean` | 16.6078 | 21.3372 | -0.0702 | -0.9999 |
| `protein_ug_g` | `scheffe_quadratic` | 22.2720 | 29.5286 | -1.0495 | -0.3332 |
| `protein_ug_g` | `ridge_a` | 16.8988 | 22.5331 | -0.1935 | -0.0214 |
| `protein_ug_g` | `ridge_b_no_intercept` | 17.0251 | 24.0037 | -0.3543 | -0.1097 |
| `protein_ug_g` | `pls` | 17.0195 | 22.6454 | -0.2054 | -0.0160 |
| `protein_ug_g` | `gpr` | 16.6078 | 21.3373 | -0.0702 | -0.9996 |
| `protein_ug_g` | `random_forest` | 17.6375 | 23.0046 | -0.2439 | -0.1487 |
| `protein_ug_g` | `xgboost` | 18.4732 | 23.8465 | -0.3367 | -0.1493 |
| `protein_ug_g` | `catboost` | 18.1932 | 23.3846 | -0.2854 | -0.1525 |
| `protein_ug_g` | `nearest_recipe` | 19.4722 | 24.7444 | -0.4392 | -0.0795 |
| `tss_ug_g` | `mean` | 408.5857 | 464.3661 | -0.0702 | -1.0000 |
| `tss_ug_g` | `scheffe_quadratic` | 481.9049 | 621.3819 | -0.9162 | -0.0821 |
| `tss_ug_g` | `ridge_a` | 416.2228 | 488.1049 | -0.1824 | -0.0049 |
| `tss_ug_g` | `ridge_b_no_intercept` | 439.5487 | 557.8613 | -0.5445 | -0.1787 |
| `tss_ug_g` | `pls` | 417.3745 | 490.8263 | -0.1956 | -0.0085 |
| `tss_ug_g` | `gpr` | 429.4833 | 485.1923 | -0.1683 | -0.8735 |
| `tss_ug_g` | `random_forest` | 423.8894 | 481.3941 | -0.1501 | -0.0398 |
| `tss_ug_g` | `xgboost` | 444.5159 | 512.0923 | -0.3014 | 0.0020 |
| `tss_ug_g` | `catboost` | 457.9169 | 516.6266 | -0.3246 | -0.2009 |
| `tss_ug_g` | `nearest_recipe` | 485.0620 | 587.4332 | -0.7125 | -0.2360 |
| `tp_mggae_g` | `mean` | 4.3319 | 5.6741 | -0.0702 | -1.0000 |
| `tp_mggae_g` | `scheffe_quadratic` | 5.5994 | 6.9378 | -0.5999 | -0.1368 |
| `tp_mggae_g` | `ridge_a` | 4.6170 | 5.6831 | -0.0736 | 0.0808 |
| `tp_mggae_g` | `ridge_b_no_intercept` | 6.6127 | 7.6654 | -0.9531 | 0.0363 |
| `tp_mggae_g` | `pls` | 4.6457 | 5.7017 | -0.0806 | 0.0905 |
| `tp_mggae_g` | `gpr` | 4.3319 | 5.6741 | -0.0702 | -1.0000 |
| `tp_mggae_g` | `random_forest` | 4.6349 | 6.0516 | -0.2173 | -0.1141 |
| `tp_mggae_g` | `xgboost` | 4.8862 | 6.2655 | -0.3049 | -0.2445 |
| `tp_mggae_g` | `catboost` | 4.8372 | 6.1516 | -0.2579 | -0.2191 |
| `tp_mggae_g` | `nearest_recipe` | 5.7752 | 7.0778 | -0.6652 | -0.2362 |
| `caffeine_pct` | `mean` | 1.0677 | 1.2504 | -0.0702 | -1.0000 |
| `caffeine_pct` | `scheffe_quadratic` | 1.1941 | 1.4712 | -0.4815 | -0.0229 |
| `caffeine_pct` | `ridge_a` | 0.9785 | 1.2276 | -0.0315 | 0.0937 |
| `caffeine_pct` | `ridge_b_no_intercept` | 1.2283 | 1.5238 | -0.5894 | 0.0216 |
| `caffeine_pct` | `pls` | 0.9728 | 1.2315 | -0.0381 | 0.1097 |
| `caffeine_pct` | `gpr` | 1.1039 | 1.2993 | -0.1555 | -0.9826 |
| `caffeine_pct` | `random_forest` | 1.0314 | 1.2829 | -0.1265 | -0.0937 |
| `caffeine_pct` | `xgboost` | 1.0158 | 1.2959 | -0.1495 | -0.0024 |
| `caffeine_pct` | `catboost` | 1.0518 | 1.3084 | -0.1717 | -0.0229 |
| `caffeine_pct` | `nearest_recipe` | 1.3689 | 1.6354 | -0.8307 | -0.1016 |
| `catechin_pct` | `mean` | 0.0769 | 0.0881 | -0.0702 | -1.0000 |
| `catechin_pct` | `scheffe_quadratic` | 0.0808 | 0.0965 | -0.2858 | 0.1177 |
| `catechin_pct` | `ridge_a` | 0.0716 | 0.0851 | -0.0003 | 0.2107 |
| `catechin_pct` | `ridge_b_no_intercept` | 0.0719 | 0.0884 | -0.0781 | 0.1809 |
| `catechin_pct` | `pls` | 0.0718 | 0.0854 | -0.0067 | 0.2285 |
| `catechin_pct` | `gpr` | 0.0777 | 0.0903 | -0.1240 | -0.1715 |
| `catechin_pct` | `random_forest` | 0.0685 | 0.0822 | 0.0677 | 0.2636 |
| `catechin_pct` | `xgboost` | 0.0691 | 0.0821 | 0.0699 | 0.2836 |
| `catechin_pct` | `catboost` | 0.0688 | 0.0833 | 0.0419 | 0.2423 |
| `catechin_pct` | `nearest_recipe` | 0.0914 | 0.1164 | -0.8685 | 0.1427 |
| `tf_pct` | `mean` | 0.0832 | 0.1006 | -0.0702 | -0.9999 |
| `tf_pct` | `scheffe_quadratic` | 0.0890 | 0.1095 | -0.2679 | 0.2237 |
| `tf_pct` | `ridge_a` | 0.0666 | 0.0855 | 0.2269 | 0.4827 |
| `tf_pct` | `ridge_b_no_intercept` | 0.0792 | 0.0949 | 0.0467 | 0.3906 |
| `tf_pct` | `pls` | 0.0669 | 0.0859 | 0.2194 | 0.4782 |
| `tf_pct` | `gpr` | 0.0762 | 0.0932 | 0.0803 | 0.3343 |
| `tf_pct` | `random_forest` | 0.0759 | 0.0953 | 0.0398 | 0.2846 |
| `tf_pct` | `xgboost` | 0.0790 | 0.0981 | -0.0186 | 0.2123 |
| `tf_pct` | `catboost` | 0.0806 | 0.0985 | -0.0261 | 0.2337 |
| `tf_pct` | `nearest_recipe` | 0.1081 | 0.1324 | -0.8563 | 0.3029 |
| `tr_pct` | `mean` | 0.5771 | 0.6612 | -0.0702 | -1.0000 |
| `tr_pct` | `scheffe_quadratic` | 0.6976 | 0.8123 | -0.6152 | -0.1003 |
| `tr_pct` | `ridge_a` | 0.5534 | 0.6560 | -0.0533 | 0.2298 |
| `tr_pct` | `ridge_b_no_intercept` | 0.5604 | 0.6621 | -0.0731 | 0.0612 |
| `tr_pct` | `pls` | 0.5550 | 0.6587 | -0.0622 | 0.2071 |
| `tr_pct` | `gpr` | 0.5886 | 0.6745 | -0.1139 | -0.9835 |
| `tr_pct` | `random_forest` | 0.5730 | 0.6790 | -0.1286 | 0.0923 |
| `tr_pct` | `xgboost` | 0.6176 | 0.7340 | -0.3189 | -0.0300 |
| `tr_pct` | `catboost` | 0.6196 | 0.7327 | -0.3141 | -0.0434 |
| `tr_pct` | `nearest_recipe` | 0.6900 | 0.8606 | -0.8131 | -0.0984 |
| `ph` | `mean` | 0.1487 | 0.1779 | -0.0702 | -0.9997 |
| `ph` | `scheffe_quadratic` | 0.1793 | 0.2159 | -0.5755 | -0.0261 |
| `ph` | `ridge_a` | 0.1407 | 0.1683 | 0.0428 | 0.3017 |
| `ph` | `ridge_b_no_intercept` | 0.6042 | 0.6273 | -12.3008 | 0.1941 |
| `ph` | `pls` | 0.1415 | 0.1687 | 0.0378 | 0.3030 |
| `ph` | `gpr` | 0.1506 | 0.1809 | -0.1056 | -0.9950 |
| `ph` | `random_forest` | 0.1546 | 0.1790 | -0.0826 | 0.0731 |
| `ph` | `xgboost` | 0.1569 | 0.1780 | -0.0711 | 0.1542 |
| `ph` | `catboost` | 0.1583 | 0.1827 | -0.1277 | 0.1069 |
| `ph` | `nearest_recipe` | 0.2097 | 0.2533 | -1.1676 | -0.3704 |
| `malic_acid_mg_g` | `mean` | 0.3664 | 0.4978 | -0.0702 | -1.0000 |
| `malic_acid_mg_g` | `scheffe_quadratic` | 0.5237 | 0.6668 | -0.9196 | -0.3731 |
| `malic_acid_mg_g` | `ridge_a` | 0.3899 | 0.5266 | -0.1976 | 0.0011 |
| `malic_acid_mg_g` | `ridge_b_no_intercept` | 0.5815 | 0.6958 | -1.0903 | -0.1008 |
| `malic_acid_mg_g` | `pls` | 0.3929 | 0.5302 | -0.2139 | -0.0225 |
| `malic_acid_mg_g` | `gpr` | 0.3681 | 0.4997 | -0.0783 | -0.9956 |
| `malic_acid_mg_g` | `random_forest` | 0.4051 | 0.5290 | -0.2085 | -0.1462 |
| `malic_acid_mg_g` | `xgboost` | 0.4137 | 0.5204 | -0.1694 | -0.0692 |
| `malic_acid_mg_g` | `catboost` | 0.4055 | 0.5329 | -0.2260 | -0.1613 |
| `malic_acid_mg_g` | `nearest_recipe` | 0.4587 | 0.6171 | -0.6445 | -0.3256 |
| `citric_acid_mg_g` | `mean` | 1.4520 | 1.7048 | -0.0702 | -1.0000 |
| `citric_acid_mg_g` | `scheffe_quadratic` | 1.8034 | 2.1487 | -0.7001 | 0.0136 |
| `citric_acid_mg_g` | `ridge_a` | 1.3640 | 1.6391 | 0.0107 | 0.2801 |
| `citric_acid_mg_g` | `ridge_b_no_intercept` | 1.4168 | 1.6856 | -0.0463 | 0.2022 |
| `citric_acid_mg_g` | `pls` | 1.3620 | 1.6440 | 0.0048 | 0.2663 |
| `citric_acid_mg_g` | `gpr` | 1.4598 | 1.7377 | -0.1119 | -0.0038 |
| `citric_acid_mg_g` | `random_forest` | 1.5051 | 1.7343 | -0.1075 | 0.1697 |
| `citric_acid_mg_g` | `xgboost` | 1.6281 | 1.8595 | -0.2733 | 0.1208 |
| `citric_acid_mg_g` | `catboost` | 1.5066 | 1.7373 | -0.1114 | 0.1364 |
| `citric_acid_mg_g` | `nearest_recipe` | 2.1698 | 2.5503 | -1.3950 | -0.0939 |
| `ascorbic_acid_mg_g` | `mean` | 2.2047 | 2.2974 | -0.0702 | -1.0000 |
| `ascorbic_acid_mg_g` | `scheffe_quadratic` | 2.6637 | 2.9865 | -0.8085 | -0.1786 |
| `ascorbic_acid_mg_g` | `ridge_a` | 2.2970 | 2.4690 | -0.2361 | -0.2089 |
| `ascorbic_acid_mg_g` | `ridge_b_no_intercept` | 2.1920 | 2.3591 | -0.1284 | -0.3646 |
| `ascorbic_acid_mg_g` | `pls` | 2.3043 | 2.4826 | -0.2496 | -0.2133 |
| `ascorbic_acid_mg_g` | `gpr` | 2.2047 | 2.2974 | -0.0702 | -1.0000 |
| `ascorbic_acid_mg_g` | `random_forest` | 2.3847 | 2.5473 | -0.3157 | -0.2725 |
| `ascorbic_acid_mg_g` | `xgboost` | 2.5643 | 2.8015 | -0.5913 | -0.3620 |
| `ascorbic_acid_mg_g` | `catboost` | 2.5068 | 2.7030 | -0.4814 | -0.3362 |
| `ascorbic_acid_mg_g` | `nearest_recipe` | 2.5846 | 3.3778 | -1.3133 | -0.1959 |
| `oxalic_acid_mg_g` | `mean` | 0.3716 | 0.5123 | -0.0702 | -1.0000 |
| `oxalic_acid_mg_g` | `scheffe_quadratic` | 0.4707 | 0.5902 | -0.4204 | 0.1003 |
| `oxalic_acid_mg_g` | `ridge_a` | 0.3808 | 0.5054 | -0.0415 | 0.2823 |
| `oxalic_acid_mg_g` | `ridge_b_no_intercept` | 0.4275 | 0.6198 | -0.5664 | 0.0563 |
| `oxalic_acid_mg_g` | `pls` | 0.3816 | 0.5066 | -0.0465 | 0.2854 |
| `oxalic_acid_mg_g` | `gpr` | 0.3852 | 0.5106 | -0.0630 | -0.1408 |
| `oxalic_acid_mg_g` | `random_forest` | 0.3829 | 0.5021 | -0.0278 | 0.1902 |
| `oxalic_acid_mg_g` | `xgboost` | 0.3966 | 0.5272 | -0.1335 | 0.0692 |
| `oxalic_acid_mg_g` | `catboost` | 0.3636 | 0.4880 | 0.0288 | 0.2160 |
| `oxalic_acid_mg_g` | `nearest_recipe` | 0.5551 | 0.7581 | -1.3436 | 0.0757 |
| `galic_acid_mg_g` | `mean` | 0.0959 | 0.1227 | -0.0702 | -1.0000 |
| `galic_acid_mg_g` | `scheffe_quadratic` | 0.1191 | 0.1503 | -0.6061 | 0.0948 |
| `galic_acid_mg_g` | `ridge_a` | 0.0889 | 0.1121 | 0.1058 | 0.4221 |
| `galic_acid_mg_g` | `ridge_b_no_intercept` | 0.2985 | 0.3213 | -6.3426 | 0.1095 |
| `galic_acid_mg_g` | `pls` | 0.0895 | 0.1128 | 0.0953 | 0.4207 |
| `galic_acid_mg_g` | `gpr` | 0.0964 | 0.1210 | -0.0402 | 0.1573 |
| `galic_acid_mg_g` | `random_forest` | 0.0939 | 0.1170 | 0.0270 | 0.2641 |
| `galic_acid_mg_g` | `xgboost` | 0.0965 | 0.1180 | 0.0104 | 0.2993 |
| `galic_acid_mg_g` | `catboost` | 0.0978 | 0.1204 | -0.0314 | 0.2668 |
| `galic_acid_mg_g` | `nearest_recipe` | 0.1132 | 0.1345 | -0.2856 | 0.4108 |
| `succinic_acid_mg_g` | `mean` | 1.9252 | 2.5340 | -0.0702 | -1.0000 |
| `succinic_acid_mg_g` | `scheffe_quadratic` | 2.4140 | 3.0779 | -0.5789 | -0.0016 |
| `succinic_acid_mg_g` | `ridge_a` | 1.9827 | 2.5714 | -0.1020 | 0.1297 |
| `succinic_acid_mg_g` | `ridge_b_no_intercept` | 1.8810 | 2.5392 | -0.0746 | 0.0839 |
| `succinic_acid_mg_g` | `pls` | 1.9858 | 2.5788 | -0.1084 | 0.1297 |
| `succinic_acid_mg_g` | `gpr` | 1.9414 | 2.5755 | -0.1055 | -1.0000 |
| `succinic_acid_mg_g` | `random_forest` | 1.9742 | 2.4915 | -0.0346 | 0.1626 |
| `succinic_acid_mg_g` | `xgboost` | 2.1439 | 2.5998 | -0.1264 | 0.1497 |
| `succinic_acid_mg_g` | `catboost` | 2.2024 | 2.6806 | -0.1976 | 0.0474 |
| `succinic_acid_mg_g` | `nearest_recipe` | 3.1031 | 3.8530 | -1.4743 | -0.1373 |
| `l_theanine_mg_g` | `mean` | 0.2840 | 0.3550 | -0.0702 | -1.0000 |
| `l_theanine_mg_g` | `scheffe_quadratic` | 0.3650 | 0.4381 | -0.6300 | 0.0587 |
| `l_theanine_mg_g` | `ridge_a` | 0.2859 | 0.3563 | -0.0780 | 0.1982 |
| `l_theanine_mg_g` | `ridge_b_no_intercept` | 0.3356 | 0.4294 | -0.5659 | -0.0334 |
| `l_theanine_mg_g` | `pls` | 0.2873 | 0.3575 | -0.0854 | 0.2007 |
| `l_theanine_mg_g` | `gpr` | 0.2872 | 0.3591 | -0.0947 | -0.9954 |
| `l_theanine_mg_g` | `random_forest` | 0.3011 | 0.3700 | -0.1626 | -0.0634 |
| `l_theanine_mg_g` | `xgboost` | 0.3216 | 0.3828 | -0.2444 | -0.0857 |
| `l_theanine_mg_g` | `catboost` | 0.3218 | 0.3888 | -0.2838 | -0.1758 |
| `l_theanine_mg_g` | `nearest_recipe` | 0.3695 | 0.4215 | -0.5082 | 0.1293 |

M3 Gate：**PASS** — 8/15 base chemistry targets improved both OOF MAE and RMSE over the mean baseline.

除既有基线与模型外，M3 还比较标准二次 Scheffé 混合模型：无截距，含各原料比例一阶项及所有两两交互项 `x_i x_j`；全部项在每个 LOO 训练折内拟合。

最近配方基线与 Mean baseline、Ridge、PLS、GPR、Random Forest、XGBoost、CatBoost 一并比较。可选后端可用情况记录于 `recipe_chemistry_metrics.json`。

## 4. Chemistry → Sensory

验证：LeaveOneGroupOut by sample_code (30 independent blend means; within-design reconstruction); models also fit on 597 ratings。源表含 597 评价记录、30 个独立配方。OOF 选择以每个配方感官均值为评价目标；另保存逐评价记录误差，未将评分行数描述为独立产品数。

### 按目标与特征组比较的 OOF 指标

| Target | Model | MAE | RMSE | R² | Spearman |
|---|---|---:|---:|---:|---:|
| `appearance` | `mean` | 4.2463 | 5.2208 | -0.0704 | -1.0000 |
| `appearance` | `nearest_chemistry` | 3.3165 | 4.2259 | 0.2987 | 0.6349 |
| `appearance` | `chemistry_a:ridge` | 4.5150 | 5.8734 | -0.3548 | 0.4389 |
| `appearance` | `chemistry_a:pls` | 3.0653 | 4.0555 | 0.3541 | 0.6627 |
| `appearance` | `chemistry_a:gpr` | 3.3046 | 4.1634 | 0.3193 | 0.5742 |
| `appearance` | `chemistry_a:random_forest` | 3.9601 | 4.8311 | 0.0834 | 0.3451 |
| `appearance` | `chemistry_a:xgboost` | 3.8538 | 4.7807 | 0.1024 | 0.3170 |
| `appearance` | `chemistry_a:catboost` | 3.8731 | 4.7565 | 0.1115 | 0.2943 |
| `appearance` | `chemistry_b:ridge` | 5.6084 | 7.0873 | -0.9726 | 0.3184 |
| `appearance` | `chemistry_b:pls` | 3.2611 | 4.1473 | 0.3245 | 0.6427 |
| `appearance` | `chemistry_b:gpr` | 3.3696 | 4.1695 | 0.3173 | 0.5430 |
| `appearance` | `chemistry_b:random_forest` | 4.0683 | 4.9990 | 0.0186 | 0.2707 |
| `appearance` | `chemistry_b:xgboost` | 4.1165 | 5.1124 | -0.0264 | 0.1751 |
| `appearance` | `chemistry_b:catboost` | 3.8465 | 4.8363 | 0.0814 | 0.2739 |
| `infusion_color` | `mean` | 5.5169 | 6.3850 | -0.0701 | -0.9973 |
| `infusion_color` | `nearest_chemistry` | 4.7099 | 5.5835 | 0.1817 | 0.6280 |
| `infusion_color` | `chemistry_a:ridge` | 5.8737 | 7.3275 | -0.4093 | 0.4394 |
| `infusion_color` | `chemistry_a:pls` | 4.0286 | 4.8566 | 0.3809 | 0.6320 |
| `infusion_color` | `chemistry_a:gpr` | 3.9644 | 4.9194 | 0.3648 | 0.6334 |
| `infusion_color` | `chemistry_a:random_forest` | 4.9724 | 5.7493 | 0.1324 | 0.4100 |
| `infusion_color` | `chemistry_a:xgboost` | 4.9134 | 5.9322 | 0.0763 | 0.3326 |
| `infusion_color` | `chemistry_a:catboost` | 4.8590 | 5.8428 | 0.1039 | 0.3246 |
| `infusion_color` | `chemistry_b:ridge` | 5.3663 | 7.2015 | -0.3613 | 0.4839 |
| `infusion_color` | `chemistry_b:pls` | 4.2030 | 4.9446 | 0.3583 | 0.6489 |
| `infusion_color` | `chemistry_b:gpr` | 4.0952 | 4.9483 | 0.3573 | 0.5782 |
| `infusion_color` | `chemistry_b:random_forest` | 5.2485 | 6.1490 | 0.0076 | 0.2988 |
| `infusion_color` | `chemistry_b:xgboost` | 5.2920 | 6.2730 | -0.0329 | 0.2699 |
| `infusion_color` | `chemistry_b:catboost` | 4.6273 | 5.6752 | 0.1546 | 0.3628 |
| `aroma` | `mean` | 7.1712 | 8.2724 | -0.0703 | -0.9996 |
| `aroma` | `nearest_chemistry` | 5.7537 | 7.1881 | 0.1919 | 0.5942 |
| `aroma` | `chemistry_a:ridge` | 4.2246 | 5.1698 | 0.5820 | 0.7998 |
| `aroma` | `chemistry_a:pls` | 4.0386 | 5.4223 | 0.5401 | 0.7575 |
| `aroma` | `chemistry_a:gpr` | 4.6572 | 5.7210 | 0.4881 | 0.7402 |
| `aroma` | `chemistry_a:random_forest` | 6.1228 | 7.6089 | 0.0945 | 0.3286 |
| `aroma` | `chemistry_a:xgboost` | 5.9172 | 7.1413 | 0.2024 | 0.4340 |
| `aroma` | `chemistry_a:catboost` | 5.7584 | 6.9749 | 0.2391 | 0.4585 |
| `aroma` | `chemistry_b:ridge` | 4.5409 | 5.4167 | 0.5411 | 0.7976 |
| `aroma` | `chemistry_b:pls` | 4.5712 | 5.7798 | 0.4775 | 0.7482 |
| `aroma` | `chemistry_b:gpr` | 4.7178 | 5.7990 | 0.4740 | 0.7219 |
| `aroma` | `chemistry_b:random_forest` | 6.3739 | 8.0410 | -0.0113 | 0.3290 |
| `aroma` | `chemistry_b:xgboost` | 6.3779 | 7.6740 | 0.0789 | 0.3281 |
| `aroma` | `chemistry_b:catboost` | 5.5282 | 6.6951 | 0.2989 | 0.5181 |
| `taste` | `mean` | 10.2998 | 11.5695 | -0.0700 | -0.9996 |
| `taste` | `nearest_chemistry` | 5.3850 | 6.4173 | 0.6708 | 0.8111 |
| `taste` | `chemistry_a:ridge` | 6.5641 | 8.2304 | 0.4585 | 0.7704 |
| `taste` | `chemistry_a:pls` | 5.3475 | 6.5002 | 0.6622 | 0.8291 |
| `taste` | `chemistry_a:gpr` | 5.6001 | 6.5273 | 0.6594 | 0.8461 |
| `taste` | `chemistry_a:random_forest` | 6.5805 | 8.8407 | 0.3752 | 0.5542 |
| `taste` | `chemistry_a:xgboost` | 6.6511 | 8.2677 | 0.4536 | 0.6423 |
| `taste` | `chemistry_a:catboost` | 6.3806 | 7.4728 | 0.5536 | 0.7402 |
| `taste` | `chemistry_b:ridge` | 5.8585 | 7.5593 | 0.5432 | 0.8300 |
| `taste` | `chemistry_b:pls` | 5.9523 | 6.8271 | 0.6274 | 0.8149 |
| `taste` | `chemistry_b:gpr` | 5.3694 | 6.3740 | 0.6752 | 0.8296 |
| `taste` | `chemistry_b:random_forest` | 6.7832 | 8.8518 | 0.3736 | 0.5849 |
| `taste` | `chemistry_b:xgboost` | 6.8571 | 8.3175 | 0.4470 | 0.6552 |
| `taste` | `chemistry_b:catboost` | 6.0074 | 7.1256 | 0.5941 | 0.7580 |
| `overall_score` | `mean` | 6.6530 | 7.3143 | -0.0701 | -1.0000 |
| `overall_score` | `nearest_chemistry` | 3.3817 | 4.7620 | 0.5464 | 0.8185 |
| `overall_score` | `chemistry_a:ridge` | 4.2941 | 5.1037 | 0.4790 | 0.7637 |
| `overall_score` | `chemistry_a:pls` | 3.3575 | 4.1532 | 0.6550 | 0.8091 |
| `overall_score` | `chemistry_a:gpr` | 3.7486 | 4.4910 | 0.5966 | 0.8082 |
| `overall_score` | `chemistry_a:random_forest` | 5.1362 | 6.5418 | 0.1440 | 0.4011 |
| `overall_score` | `chemistry_a:xgboost` | 5.2700 | 6.2872 | 0.2093 | 0.4736 |
| `overall_score` | `chemistry_a:catboost` | 4.8010 | 5.5516 | 0.3835 | 0.6036 |
| `overall_score` | `chemistry_b:ridge` | 3.9680 | 4.9960 | 0.5007 | 0.8140 |
| `overall_score` | `chemistry_b:pls` | 3.7447 | 4.4310 | 0.6073 | 0.7838 |
| `overall_score` | `chemistry_b:gpr` | 3.7705 | 4.4799 | 0.5986 | 0.7646 |
| `overall_score` | `chemistry_b:random_forest` | 5.4975 | 6.8604 | 0.0586 | 0.3700 |
| `overall_score` | `chemistry_b:xgboost` | 5.2932 | 6.4546 | 0.1667 | 0.4643 |
| `overall_score` | `chemistry_b:catboost` | 4.8186 | 5.6366 | 0.3645 | 0.5884 |

M4 Gate：**PASS** — 5/5 modeled blend-mean targets improved both OOF MAE and RMSE over the mean baseline.

Chemistry-A 使用 15 个基础理化变量；Chemistry-B 使用 15 个基础变量加 4 个派生比值。

## 5. Recipe → Sensory（直接模型）

验证：LeaveOneOut by unique sample_code (n=30; within-design reconstruction)。保留 Mean、Nearest Recipe、Ridge、PLS、GPR、Random Forest，以及已安装时的 XGBoost/CatBoost。

### 按目标的 OOF 比较

| Target | Model | MAE | RMSE | R² | Spearman |
|---|---|---:|---:|---:|---:|
| `appearance` | `mean` | 4.2451 | 5.2201 | -0.0702 | -1.0000 |
| `appearance` | `nearest_recipe` | 5.9646 | 6.9794 | -0.9130 | 0.1544 |
| `appearance` | `ridge_a` | 3.2631 | 4.2584 | 0.2878 | 0.5849 |
| `appearance` | `pls` | 3.2894 | 4.2755 | 0.2821 | 0.5795 |
| `appearance` | `gpr` | 3.8114 | 4.7113 | 0.1283 | 0.3962 |
| `appearance` | `random_forest` | 3.3973 | 4.2161 | 0.3019 | 0.5631 |
| `appearance` | `xgboost` | 3.2356 | 4.0744 | 0.3481 | 0.5506 |
| `appearance` | `catboost` | 3.1377 | 3.9134 | 0.3986 | 0.5791 |
| `infusion_color` | `mean` | 5.5172 | 6.3852 | -0.0702 | -1.0000 |
| `infusion_color` | `nearest_recipe` | 7.7543 | 9.4466 | -1.3423 | 0.1526 |
| `infusion_color` | `ridge_a` | 4.2989 | 5.6605 | 0.1590 | 0.4603 |
| `infusion_color` | `pls` | 4.2985 | 5.6938 | 0.1491 | 0.4590 |
| `infusion_color` | `gpr` | 4.8583 | 6.2201 | -0.0155 | 0.2552 |
| `infusion_color` | `random_forest` | 4.3827 | 5.7007 | 0.1470 | 0.3931 |
| `infusion_color` | `xgboost` | 4.6771 | 5.9849 | 0.0598 | 0.3766 |
| `infusion_color` | `catboost` | 4.3253 | 5.5442 | 0.1932 | 0.4487 |
| `aroma` | `mean` | 7.1711 | 8.2718 | -0.0702 | -1.0000 |
| `aroma` | `nearest_recipe` | 8.4784 | 10.1142 | -0.6000 | 0.0618 |
| `aroma` | `ridge_a` | 5.8705 | 7.5517 | 0.1081 | 0.4127 |
| `aroma` | `pls` | 5.8517 | 7.5923 | 0.0984 | 0.4202 |
| `aroma` | `gpr` | 6.7434 | 8.0935 | -0.0245 | 0.2111 |
| `aroma` | `random_forest` | 6.2435 | 7.7483 | 0.0610 | 0.3313 |
| `aroma` | `xgboost` | 5.8875 | 7.6376 | 0.0876 | 0.3557 |
| `aroma` | `catboost` | 5.6827 | 7.3737 | 0.1496 | 0.4420 |
| `taste` | `mean` | 10.3096 | 11.5702 | -0.0702 | -1.0000 |
| `taste` | `nearest_recipe` | 12.0152 | 13.6914 | -0.4985 | 0.0867 |
| `taste` | `ridge_a` | 7.5020 | 9.0683 | 0.3426 | 0.5822 |
| `taste` | `pls` | 7.5170 | 9.1102 | 0.3365 | 0.5791 |
| `taste` | `gpr` | 8.2755 | 9.6434 | 0.2566 | 0.4567 |
| `taste` | `random_forest` | 7.8520 | 9.2419 | 0.3172 | 0.5275 |
| `taste` | `xgboost` | 7.9728 | 9.5570 | 0.2698 | 0.5012 |
| `taste` | `catboost` | 7.5287 | 9.1484 | 0.3310 | 0.5413 |
| `overall_score` | `mean` | 6.6587 | 7.3145 | -0.0702 | -1.0000 |
| `overall_score` | `nearest_recipe` | 7.8076 | 8.7953 | -0.5473 | 0.2126 |
| `overall_score` | `ridge_a` | 4.6026 | 5.8744 | 0.3097 | 0.6222 |
| `overall_score` | `pls` | 4.5911 | 5.9042 | 0.3027 | 0.6298 |
| `overall_score` | `gpr` | 5.4052 | 6.4211 | 0.1753 | 0.5159 |
| `overall_score` | `random_forest` | 4.9347 | 5.9142 | 0.3004 | 0.5399 |
| `overall_score` | `xgboost` | 5.0178 | 6.0589 | 0.2657 | 0.5261 |
| `overall_score` | `catboost` | 4.8657 | 5.8545 | 0.3144 | 0.5253 |

M5 / Gate B（原始 OOF 数值门槛）：**PASS** — Overall-score OOF MAE/RMSE both improve over the mean baseline; 5/5 modeled targets improved both metrics.
Overall score 选中模型 `pls`：MAE 4.5911、RMSE 5.9042；Mean baseline：MAE 6.6587、RMSE 7.3145。

当原始 OOF Gate B 未通过，或置换可信度未通过时，Demo 都会关闭未测点的自动推荐资格，仍展示实测配方排序与补点实验计划。

### Gate B 可信度补充：置换检验与逐折敏感性

对五项建模感官均值做 200 次联合行置换，并在每次置换中重跑候选模型和逐目标选模。观测到 5/5 项的 MAE 与 RMSE 同时改善；置换中达到或超过该数量的经验 p 值为 0.154229（30 次；置换率95%精确区间 10.355%–20.716%）。Overall-score Gate B 的经验 p 值为 0.482587（96 次通过；置换率95%精确区间 40.901%–55.159%）。

按预设 α=0.05，自动预测推荐可信度门槛为 **NOT VALIDATED**；未观测点预测不会进入 Top-K 自动推荐。

置换检验以无配方—感官关联时配方行与感官向量可交换为条件；它不是外部验证，也不能替代新配方实测。逐折误差与删一评估折敏感性见 `artifacts/reports/gate_b_validation/`。

### 无模型的配方—感官距离关联检验

在 30 个独立配方上，比较四维配方比例欧氏距离与标准化五维感官均值欧氏距离；Mantel Pearson r=0.1169，联合行置换 4999 次、双侧经验 p=0.051200，置换零分布 95% 区间为 -0.1081–0.1259。

该检验在当前样本中未检测到显著的整体配方—感官距离关联（p 略高于 0.05）；这不等于证明关联不存在，n=30 的检验能力有限。
单目标补充检验经 Holm 校正后的最低 p 值为 0.080，没有单一目标在校正后达到 0.05。
各目标的补充 Mantel 结果及 Holm 多重比较校正见 `artifacts/reports/recipe_sensory_mantel/recipe_sensory_mantel.csv`。该分析独立于模型族，不以预测误差或模型选择作为统计量。

## 6. 双预测路径、不确定性与设计空间状态

Path A：Recipe→Chemistry→Sensory；Path B：Recipe→Sensory。对每个目标同时保存两条路径预测和绝对差异。优化器对未测点的风险分数采用 `predicted objective − λ × uncertainty − γ × model disagreement`；已测点排序直接使用真实感官均值。
GPR predictive standard deviation 是模型估计的 spread，不是经覆盖率校准的置信区间；不会声称 95%/98% 置信度。感官评价标准差用于描述已测评分离散程度。

当前不以凸包作 OOD 主判定。候选被标记为 `OBSERVED`、`UNOBSERVED_VALID` 或 `INVALID_DESIGN_POINT`。合法设计空间外的配方不会进入候选；KNN 最近样品及距离用于解释当前合法点与实测数据的邻近关系。

## 7. 32 点设计空间排序与下一次实验

排序器检查全部 32 个合法点；其中 30 个采用实测值，2 个采用带风险惩罚的预测。Gate B 自动推荐状态：**disabled**。

### 当前 Top 候选

| Rank | 证据 | 配方 (g: Green / White / Oolong / Black) | Objective | Uncertainty | Risk score | 样品 |
|---:|---|---|---:|---:|---:|---|
| 1 | MEASURED | 1 / 1 / 1 / 1 | 82.596 | 11.761 | 82.596 | S16 |
| 2 | MEASURED | 0.5 / 2 / 0.5 / 1 | 82.285 | 8.407 | 82.285 | S15 |
| 3 | MEASURED | 1 / 1.5 / 0.5 / 1 | 82.275 | 8.183 | 82.275 | S20 |
| 4 | MEASURED | 0.5 / 1.5 / 1 / 1 | 81.904 | 8.290 | 81.904 | S24 |
| 5 | MEASURED | 1 / 0.5 / 0.5 / 2 | 81.139 | 8.983 | 81.139 | S19 |
| 6 | MEASURED | 0.5 / 2 / 1 / 0.5 | 79.059 | 8.376 | 79.059 | S23 |
| 7 | MEASURED | 0.5 / 1 / 2 / 0.5 | 76.908 | 8.013 | 76.908 | S22 |
| 8 | MEASURED | 0.5 / 0.5 / 1 / 2 | 76.901 | 8.105 | 76.901 | S18 |
| 9 | MEASURED | 1.5 / 1 / 0.5 / 1 | 76.422 | 10.628 | 76.422 | S12 |
| 10 | MEASURED | 0.5 / 1 / 1 / 1.5 | 76.334 | 8.672 | 76.334 | S7 |

### 建议优先打样的未观测格点

| 优先级 | 配方 (g: Green / White / Oolong / Black) | 预测目标 | GPR spread | 最近实测样品 |
|---:|---|---:|---:|---|
| 1 | 0.5 / 1.5 / 0.5 / 1.5 | 79.547 | 5.969 | S11 |
| 2 | 0.5 / 1 / 1.5 / 1 | 74.463 | 5.752 | S1 |

补测这两个点会使当前固定离散设计空间达到 100% 实测覆盖；这不扩大到更细步长或其他原料。

## 8. 主要局限与厂家下一步数据

1. 独立实测配方只有 30 个；当前定义的 32 点离散设计空间覆盖率为 93.75%，尚差 2 点。
2. 当前设计空间狭窄：四种茶、固定 4.0 g 总量、固定 0.5 g 称量步长；不能推断 0.25 g、0.1 g 或任意连续比例。
3. 不包含第五种原料、原料批次、生产工艺、成本、库存、稳定性/货架期或消费者偏好。
4. 597 条感官记录并非 597 个独立产品；S30 的评分次数为 17，其余为 20。缺少评价者 ID，无法建模评价者偏差。
5. Leave-One-Blend-Out 只验证当前离散空间内部重建；两个缺失点的预测在实际实验前未经直接验证。所有候选均需真实研发与法规验证。
6. 厂家下一步优先提供两个缺失格点的完整理化和感官结果，随后补充原料批次、工艺参数、标准化感官评价、成本、库存和稳定性记录。

## 9. 交付物索引

- 数据：`data/processed/`；审计：`artifacts/reports/data_audit.*`。
- OOF 预测：`artifacts/predictions/`；综合已选模型误差表：`prediction_error_by_sample.csv`；模型与字段顺序：`artifacts/models/`。
- 32 点全表、下一次实验、Top 候选：`artifacts/optimization/`。
- Streamlit 页面：`app/app.py`；启动：`streamlit run app/app.py`。
- 方差分解：`artifacts/reports/sensory_noise_decomposition/`；模型无关关联检验：`artifacts/reports/recipe_sensory_mantel/`。
- 完整复现：`python scripts/07_run_full_pipeline.py`；Gate B 选择调整置换：`python scripts/08_validate_gate_b.py --permutations 200 --seed 42 --n-jobs 7`；测试：`pytest -q`。

**Demo 判定：** 可演示。 **原始 Gate B 数值门槛：** PASS。 **自动预测推荐可信度：** 未通过；只展示实测排序，未观测预测仅作实验估计。 **指导实验判定：** 预测点仅用于安排两项验证实验，不作为生产依据。
