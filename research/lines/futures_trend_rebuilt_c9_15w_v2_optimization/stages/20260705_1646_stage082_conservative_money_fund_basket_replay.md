# Stage082 conservative money fund basket replay

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T16:46:22
- 阶段性质：Stage081 独立审查后的保守 PIT 可购性与缺失 0 收益重放
- 是否重要突破：否，账户层边际过线只能作为资金治理弱候选，不能直接晋级

## 外部调研与判断

- 货币基金每日万份收益可以作为储备资金账户层收益源，但必须把可购性和缺失数据处理做保守。
- 本阶段不使用当前 7日年化排序，不按历史收益挑基金；也不把暂停申购基金的份额重分配给其他基金。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage082_conservative_money_fund_basket_replay.py`
- 新增参数：`PER_FUND_RESERVE_CAPITAL=12500.0`。
- 修改参数：无正式交易参数。
- 删除参数：删除 Stage081 中“有数据基金均值”和“忽略起点暂停申购”的宽松假设。

## 结果

| version                                          | variant_label                                 |   start_count |   positive_count |   min_return_pct |   median_return_pct |   max_return_pct |   min_return_retention_ratio |   median_return_retention_ratio |   worst_drawdown_pct |   median_drawdown_pct |   max_days_below_initial |   median_days_below_initial |   max_consecutive_below_initial_days |   median_consecutive_below_initial_days |   days_below_improved_count |   max_consecutive_below_improved_count | passes_account_level_stage077_proxy_goal   |
|:-------------------------------------------------|:----------------------------------------------|--------------:|-----------------:|-----------------:|--------------------:|-----------------:|-----------------------------:|--------------------------------:|---------------------:|----------------------:|-------------------------:|----------------------------:|-------------------------------------:|----------------------------------------:|----------------------------:|---------------------------------------:|:-------------------------------------------|
| official_c9_15w_reference                        | Official C9 15w reference                     |            13 |               13 |          1.90107 |             126.199 |          3886.19 |                      1       |                         1       |             -55.3701 |              -24.469  |                      500 |                          20 |                                  387 |                                      16 |                           0 |                                      0 | False                                      |
| c9_15w_plus_conservative_fixed_money_fund_basket | C9 15w + conservative fixed money fund basket |            13 |               13 |          1.1805  |              65.344 |          1948.89 |                      0.50149 |                         0.51526 |             -52.7119 |              -18.5753 |                      485 |                          20 |                                  383 |                                      16 |                           7 |                                      5 | True                                       |

## Per-start 可购性审计

| actual_start   |   basket_size |   active_fund_count |   paused_or_uninvestable_fund_count |   paused_or_uninvestable_funds |   cash_zero_yield_capital | requested_start_month   |
|:---------------|--------------:|--------------------:|------------------------------------:|-------------------------------:|--------------------------:|:------------------------|
| 2020-01-02     |            12 |                  12 |                                   0 |                                |                         0 | 2020-01                 |
| 2020-07-01     |            12 |                  12 |                                   0 |                                |                         0 | 2020-07                 |
| 2021-01-04     |            12 |                  12 |                                   0 |                                |                         0 | 2021-01                 |
| 2021-07-01     |            12 |                  12 |                                   0 |                                |                         0 | 2021-07                 |
| 2022-01-04     |            12 |                  12 |                                   0 |                                |                         0 | 2022-01                 |
| 2022-07-01     |            12 |                  12 |                                   0 |                                |                         0 | 2022-07                 |
| 2023-01-03     |            12 |                  12 |                                   0 |                                |                         0 | 2023-01                 |
| 2023-07-03     |            12 |                  12 |                                   0 |                                |                         0 | 2023-07                 |
| 2024-01-02     |            12 |                  11 |                                   1 |                         000009 |                     12500 | 2024-01                 |
| 2024-07-01     |            12 |                  11 |                                   1 |                         000009 |                     12500 | 2024-07                 |
| 2025-01-02     |            12 |                  11 |                                   1 |                         000009 |                     12500 | 2025-01                 |
| 2025-07-01     |            12 |                  11 |                                   1 |                         000009 |                     12500 | 2025-07                 |
| 2026-01-05     |            12 |                  11 |                                   1 |                         000009 |                     12500 | 2026-01                 |

## Retention 明细

| requested_start_month   |   total_return_pct |   official_return_pct |   return_retention_ratio |   max_drawdown_pct |   drawdown_improvement_pp |   days_below_delta |   max_consecutive_below_delta |
|:------------------------|-------------------:|----------------------:|-------------------------:|-------------------:|--------------------------:|-------------------:|------------------------------:|
| 2020-01                 |          1948.89   |            3886.19    |                 0.50149  |           -52.7119 |                   2.65823 |                  0 |                             0 |
| 2020-07                 |          1579.03   |            3147.57    |                 0.501666 |           -51.7447 |                   2.9921  |                  0 |                             0 |
| 2021-01                 |           753.096  |            1496.83    |                 0.503128 |           -48.6113 |                   5.70663 |                  0 |                             0 |
| 2021-07                 |           124.794  |             241.367   |                 0.517032 |           -32.1397 |                  15.1383  |                  0 |                             0 |
| 2022-01                 |            61.4833 |             115.866   |                 0.530641 |           -20.8502 |                  19.1319  |                -15 |                            -4 |
| 2022-07                 |           104.886  |             203.642   |                 0.51505  |           -35.7306 |                  19.4529  |                 -7 |                           -35 |
| 2023-01                 |            65.344  |             125.38    |                 0.521169 |           -14.3531 |                  10.1159  |                 -5 |                          -127 |
| 2023-07                 |            91.8929 |             179.443   |                 0.5121   |           -18.5753 |                   5.80323 |                 -1 |                            -7 |
| 2024-01                 |            64.6546 |             126.199   |                 0.512321 |           -16.1567 |                   6.40545 |                 -1 |                             0 |
| 2024-07                 |            26.7505 |              51.2352  |                 0.522112 |           -14.7972 |                   8.57789 |                -10 |                             0 |
| 2025-01                 |            16.9795 |              32.3783  |                 0.524409 |           -14.1114 |                   8.53939 |                 -1 |                            -1 |
| 2025-07                 |            16.5647 |              32.1483  |                 0.51526  |           -10.9589 |                   6.95927 |                  0 |                             0 |
| 2026-01                 |             1.1805 |               1.90107 |                 0.620965 |            -7.9503 |                   6.78004 |                  0 |                             0 |

## 结论

- 决策：`stage082_conservative_basket_account_level_marginal_pass_not_promotion`。
- 回测指标说明：本阶段是账户层现金收益源重放，不新增交易订单；底层 C9 交易路径不变，因此不生成新增真实滑点、交易次数或胜率。
- 独立 agent 审查结论：严重问题为无，置信度 `0.86`；Stage082 基本落实了 Stage081 审查要求，抓取失败直接失败、缺失收益按 `0`、起点暂停申购基金不买入且资金不重分配。中等风险是 `passes_account_level_stage077_proxy_goal=True` 只是聚合最差值口径通过，不是每个起点水下都改善；最低收益保留 `50.1490%` 过线很薄；历史 `限制大额申购` 缺少当时限额字段，T+1/T+2 确认和快速赎回限制未完全建模。
- 运行前过拟合反思：否。规则来自独立审查要求的保守口径，不按坏窗口、收益率或基金表现调参。
- 运行后过拟合反思：若继续按篮子大小、基金代码范围、暂停申购处理或当前收益率救过线，就是过拟合；本阶段只允许作为账户层资金治理证据。
- 继续价值：有但有限。保守口径仍边际过线，下一步只能审真实交易渠道和税费/申赎确认/赎回时效敏感性，不换基金、不扫篮子大小；若摩擦后不过线，则现金篮子方向降级。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage082_conservative_money_fund_basket_replay/rebuilt_c9_v2_stage082_conservative_money_fund_basket_replay_report_stage082_conservative_money_fund_basket_replay_v1.md`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage082_conservative_money_fund_basket_replay/rebuilt_c9_v2_stage082_conservative_money_fund_basket_replay_decision_stage082_conservative_money_fund_basket_replay_v1.json`
- curves：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage082_conservative_money_fund_basket_replay/rebuilt_c9_v2_stage082_conservative_money_fund_basket_replay_curves_stage082_conservative_money_fund_basket_replay_v1.csv.gz`
- variant_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage082_conservative_money_fund_basket_replay/rebuilt_c9_v2_stage082_conservative_money_fund_basket_replay_variant_summary_stage082_conservative_money_fund_basket_replay_v1.csv`
- retention：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage082_conservative_money_fund_basket_replay/rebuilt_c9_v2_stage082_conservative_money_fund_basket_replay_retention_vs_official_c9_stage082_conservative_money_fund_basket_replay_v1.csv`
