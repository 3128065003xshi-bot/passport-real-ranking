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

## 目的地价值表

`data/processed/country_indicators.csv`（由 `python3 scripts/build_country_indicators.py` 生成），每个国家/地区一行：

| 字段 | 含义 | 来源 |
|---|---|---|
| gdp_usd_bn / gdp_per_capita_usd | 总 GDP（十亿美元）/ 人均 GDP | 世界银行，最新年份 |
| cities_1m_plus / 5m / 10m | 100 万 / 500 万 / 1000 万人口以上城市（都市区）数量 | 联合国《世界城镇化展望 2018》，2020 年值 |
| tourist_arrivals_m | 年入境过夜游客（百万人次） | 联合国旅游组织（经 Our World in Data）：优先 2023+，其次 2017–2019，再次 2022；缺失时用世界银行 2019 或人工估算，见 `arrivals_source` |
| price_level_us100 | 物价水平，美国 = 100 | 世界银行：居民消费 PPP 换算系数 ÷ 市场汇率 |
| crime_index | 犯罪指数 0–100，越高越不安全 | 由联合国毒罪办凶杀率换算：100·ln(1+率)/ln(41)，封顶 100 |
| nature_score / culture_score | 自然风光 / 人文景点推荐指数 0–100 | 人工打分（`data/raw/manual_scores.csv`），参考世界遗产数 |
| whs_cultural / natural / mixed | 世界遗产数量 | UNESCO 2024 名录 |
| estimated | 该行哪些字段是人工估算 | `data/raw/manual_estimates.csv` |

## 目的地旅游分数

`python3 scripts/build_tourism_score.py` → `data/processed/tourism_scores.csv`。

每项：先按 `cap` 封顶（如人均 GDP 超过 10 万美元按 10 万算），再按 `transform` 变换（`log` = ln(1+x)，`sqrt` = 平方根，介于对数和线性之间；`linear` = 原值），然后在全部国家间 min-max 缩放到 0–100（`direction = lower` 时翻转），乘以权重/100 得到该项得分；各项相加即旅游分数（权重总和 100 时满分 100）。缺失值记 0 分并写在 `missing` 列。权重在 `data/raw/indicator_weights.csv`。

## 目录

```
data/raw/        原始数据（签证政策、GDP、旅游指标……）
data/processed/  清洗、合并后的数据
docs/            方法论与权重说明
```
