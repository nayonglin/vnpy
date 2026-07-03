# Stage077 jd.DCE independent candidate audit

- 时间：2026-07-02 01:43:47 CST
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 类型：只读资格审计，不改线上、不改共享 AI 池、不接实盘。
- 外部调研：趋势跟随鼓励增加可交易市场和分散化，但新增品种应先看资本承载、独立材料性和点时 selector；本阶段采纳“jd 只能先独立非挤占审计”的方向，不采纳共享 AI rerank。

## 版本变更

- 新增参数：`MIN_COUNT=6`、`MIN_YEARS=3`、`MIN_TOTAL_PNL=50000`，仅用于 jd 独立候选资格门。
- 修改参数：无正式交易参数修改。
- 删除参数：无。
- 新增回测结果：无真实资金曲线回测；新增 jd full-market 月度选择器资格审计。
- 修改回测结果：无。
- 删除回测结果：无。

## 结果

- 决策：`stage077_jd_not_independent_candidate_keep_observe`。
- jd month count：`50`，日期 `2022-01-28 -> 2026-02-27`。
- jd 全部 60d future PnL 合计：`-4620.0000`。
- independent candidate count：`0`。
- candidate conditions：`无`。

## 条件摘要

| condition                        | description                                                          | eligible_independent   |   count |   coverage_pct |   year_count |   total_future_net_pnl_60d |   mean_future_net_pnl_60d |   win_rate_pct |   min_year_pnl |   negative_year_count |   oos_fold_count |   oos_positive_fold_count |   oos_min_fold_pnl |   top5_positive_pnl_share_pct | stage077_independent_candidate   |
|:---------------------------------|:---------------------------------------------------------------------|:-----------------------|--------:|---------------:|-------------:|---------------------------:|--------------------------:|---------------:|---------------:|----------------------:|-----------------:|--------------------------:|-------------------:|------------------------------:|:---------------------------------|
| jd_ai_top8_independent           | jd 进入 full-market AI top8；仅作为独立非挤占候选                    | True                   |      11 |             22 |            3 |                      16800 |                  1527.27  |        27.2727 |           2380 |                     0 |                4 |                         2 |               -480 |                      100      | False                            |
| jd_ai_or_simple_top8_independent | jd 进入 AI top8 或 simple top8；仅作宽松独立观察                     | True                   |      20 |             40 |            3 |                      14390 |                   719.5   |        20      |          -4980 |                     1 |                4 |                         2 |              -4160 |                      100      | False                            |
| jd_consensus_top8_independent    | jd 同时进入 full-market AI top8 与 simple top8；仅作为独立非挤占候选 | True                   |       2 |              4 |            1 |                      -1520 |                  -760     |         0      |          -1520 |                     1 |                1 |                         0 |              -1520 |                               | False                            |
| jd_simple_top8_independent       | jd 进入 simple trend top8；仅作为独立非挤占候选                      | True                   |      11 |             22 |            3 |                      -3930 |                  -357.273 |         9.0909 |          -7360 |                     1 |                3 |                         1 |              -3680 |                      100      | False                            |
| all_jd_months                    | jd 全部 full-market 月度预测；只作覆盖基准                           | False                  |      50 |            100 |            5 |                      -4620 |                   -92.4   |        20      |         -27160 |                     2 |                4 |                         1 |             -26320 |                       71.7078 | False                            |

## 年度摘要

|   eval_year |   month_count |   future_net_pnl_60d |   ai_top8_months |   simple_top8_months |   consensus_top8_months |
|------------:|--------------:|---------------------:|-----------------:|---------------------:|------------------------:|
|        2022 |            12 |                34780 |                3 |                    6 |                       2 |
|        2023 |            12 |               -27160 |                0 |                    0 |                       0 |
|        2024 |            12 |               -17360 |                5 |                    2 |                       0 |
|        2025 |            12 |                 5120 |                3 |                    3 |                       0 |
|        2026 |             2 |                    0 |                0 |                    0 |                       0 |

## 反思

- 运行前过拟合反思：否；本阶段只审计 jd 独立非挤占资格，不把 jd 塞入共享 AI rerank，也不扫 sleeve 大小、月份、方向或 TopN。
- 运行后过拟合反思：否；若没有稳定候选，继续调 jd AI rank、simple rank、年份或风险预算就是过拟合。
- 运行前继续价值反思：有价值；用户目标明确要求基础池加鸡蛋，但历史反证要求先证明 jd 独立材料性。
- 运行后继续价值反思：有限；若 jd 仍无独立候选，应保留数据资产和 forward watch，转更强 PIT 信息源或非鸡蛋主线。

## 后续规划和 TODO

- 下一步：`若 candidate_conditions 为空，停止 jd 共享/独立历史救参；只允许 forward watch 或新特征证明后再给小独立预算。`。
