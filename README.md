# Passport Real Ranking

护照"真实含金量"排名。

现有排名（Henley、Passport Index 等）只数免签/落地签目的地的**数量**——去瑞士和去一个小岛国都算 1 分。
本项目给每个免签/落地签目的地一个**价值权重**，按目的地的实际价值加权求和。

## 打分思路（草案，待定）

```
护照得分 = Σ  入境便利系数(目的地) × 目的地价值(目的地)
```

- **入境便利系数**：免签 > 落地签 / eTA > 电子签 > 需提前签证（具体数值待定）
- **目的地价值**：由多个维度加权组合，例如
  - 经济体量（GDP）
  - 旅游资源（世界遗产、自然景观等）
  - 旅游体验（安全、基础设施、服务等）
  - 其他待补充维度

各维度权重、数据来源、归一化方法都还没定，后续会在 `docs/` 里记录。

## 签证关系表

入境方式代码与权重见 `data/raw/entry_codes.csv`（S 100 自由流动 · A 90 免签 · B 85 电子旅行授权 · C 75 落地签 · D 50 电子签 · E 20 需签证 · F 0 禁止入境/极难获得）。

```
data/raw/passport_index_2025-01-12.csv  基础数据（Passport Index 开源数据集，MIT，最后更新 2025-01-12）
data/raw/free_movement_groups.csv       S 级自由流动区（enabled=0 的组默认不生效）
data/raw/visa_overrides.csv             2025 年后的政策变化及人工判断，自上而下覆盖，后行优先
data/processed/visa_matrix.csv          生成结果（长表：passport, destination, code, weight, days, source, note）
data/processed/visa_matrix_wide.csv     生成结果（宽表，199×199，方便在 Excel 里看）
```

修改规则或政策后重新生成：`python3 scripts/build_visa_matrix.py`。生成结果不要手改，改 `visa_overrides.csv`。

## 目录

```
data/raw/        原始数据（签证政策、GDP、旅游指标……）
data/processed/  清洗、合并后的数据
docs/            方法论与权重说明
```
