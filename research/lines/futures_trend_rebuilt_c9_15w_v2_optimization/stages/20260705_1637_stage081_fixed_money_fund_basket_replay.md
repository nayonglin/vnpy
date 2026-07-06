# Stage081 fixed money fund basket replay

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T16:37:30
- 阶段性质：无当前收益筛选的固定货币基金篮子历史收益回放
- 是否重要突破：否，固定篮子仅边际数字过线，需真实渠道与 PIT 可购性确认后才能继续评价

## 外部调研与判断

- 货币基金每日每万份收益可以作为现金储备账户层历史收益源；但基金篮子选择必须避免当前收益率排序造成选择偏差。
- 本阶段按公开平台申赎/限额字段合格、基金代码稳定排序取前 `12` 只，不使用当前 7日年化。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage081_fixed_money_fund_basket_replay.py`
- 新增参数：`BASKET_SIZE=12`、`RESERVE_CAPITAL=150000.0`、`START_MONTHS=('2020-01', '2020-07', '2021-01', '2021-07', '2022-01', '2022-07', '2023-01', '2023-07', '2024-01', '2024-07', '2025-01', '2025-07', '2026-01')`。
- 修改参数：无正式交易参数。
- 删除参数：删除 Stage079/080 后续研究中的当前收益率筛选依赖。

## Basket

|   fund_code | fund_name_purchase   | fund_type       | purchase_status   | redeem_status   |   purchase_min_yuan |   daily_limit_yuan |   fee_pct |
|------------:|:---------------------|:----------------|:------------------|:----------------|--------------------:|-------------------:|----------:|
|      000009 | 易方达天天理财货币A  | 货币型-普通货币 | 开放申购          | 开放赎回        |                  10 |              1e+11 |         0 |
|      000203 | 国富日日收益货币A    | 货币型-普通货币 | 开放申购          | 开放赎回        |                  10 |              1e+11 |         0 |
|      000204 | 国富日日收益货币B    | 货币型-普通货币 | 开放申购          | 开放赎回        |                  10 |              1e+11 |         0 |
|      000300 | 德邦德利货币A        | 货币型-普通货币 | 开放申购          | 开放赎回        |                  10 |              1e+11 |         0 |
|      000331 | 中加货币A            | 货币型-普通货币 | 开放申购          | 开放赎回        |                  10 |              1e+11 |         0 |
|      000366 | 汇添富添富通货币A    | 货币型-普通货币 | 限大额            | 开放赎回        |                  10 |              1e+07 |         0 |
|      000379 | 平安日增利货币A      | 货币型-普通货币 | 限大额            | 开放赎回        |                  10 |              1e+07 |         0 |
|      000380 | 景顺长城景益货币A    | 货币型-普通货币 | 限大额            | 开放赎回        |                  10 |              5e+06 |         0 |
|      000389 | 广发天天红货币A      | 货币型-普通货币 | 限大额            | 开放赎回        |                  10 |              1e+07 |         0 |
|      000424 | 长盛添利宝货币A      | 货币型-普通货币 | 限大额            | 开放赎回        |                  10 |              1e+06 |         0 |
|      000464 | 嘉实活期宝货币A      | 货币型-普通货币 | 开放申购          | 开放赎回        |                  10 |              1e+11 |         0 |
|      000475 | 广发天天利货币A      | 货币型-普通货币 | 限大额            | 开放赎回        |                  10 |              1e+07 |         0 |

## Source Audit

|   basket_size |   universe_size |   history_fund_count |   history_rows | history_date_min   | history_date_max   |   calendar_raw_coverage_pct |   min_daily_fund_count |   median_daily_fund_count |   fetch_error_count | fetch_errors_sample   |
|--------------:|----------------:|---------------------:|---------------:|:-------------------|:-------------------|----------------------------:|-----------------------:|--------------------------:|--------------------:|:----------------------|
|            12 |             401 |                   12 |          27714 | 2020-01-01         | 2026-06-30         |                         100 |                      9 |                        12 |                   0 |                       |

## 保守缺失处理复核

- 12 只基金的历史最早日期均可追到 `2020-01-01`，未发现基金晚成立导致的明显回看问题。
- Stage081 主口径按“当日有数据基金的每日万份收益均值”计算储备收益；为防止缺失日动态调权高估，补做保守复算：任一基金当日缺失则按该基金收益 `0` 计，再对 12 只等权平均。
- 保守复算后，最低收益保留从 `50.1535%` 降为 `50.1490%`，中位收益保留从 `51.6832%` 降为 `51.6578%`，最差回撤从 `-52.7051%` 小幅变为 `-52.7119%`，最长水下仍为 `485` 天、最长连续水下仍为 `383` 天。
- 结论：缺失日处理不是本阶段过线的主要来源；真正脆弱点仍是最低收益保留只比 `50%` 门槛高约 `0.15pp`，以及该篮子尚未完成用户真实交易渠道确认。

## 结果

| version                                | variant_label                       |   start_count |   positive_count |   min_return_pct |   median_return_pct |   max_return_pct |   min_return_retention_ratio |   median_return_retention_ratio |   worst_drawdown_pct |   median_drawdown_pct |   max_days_below_initial |   median_days_below_initial |   max_consecutive_below_initial_days |   median_consecutive_below_initial_days | passes_stage077_numeric_goal   |
|:---------------------------------------|:------------------------------------|--------------:|-----------------:|-----------------:|--------------------:|-----------------:|-----------------------------:|--------------------------------:|---------------------:|----------------------:|-------------------------:|----------------------------:|-------------------------------------:|----------------------------------------:|:-------------------------------|
| official_c9_15w_reference              | Official C9 15w reference           |            13 |               13 |          1.90107 |            126.199  |          3886.19 |                     1        |                        1        |             -55.3701 |               -24.469 |                      500 |                          20 |                                  387 |                                      16 | False                          |
| c9_15w_plus_fixed_12_money_fund_basket | C9 15w + fixed 12 money fund basket |            13 |               13 |          1.20367 |             65.3862 |          1949.06 |                     0.501535 |                        0.516832 |             -52.7051 |               -18.572 |                      485 |                          20 |                                  383 |                                      16 | True                           |

## 结论

- 决策：`stage081_fixed_money_fund_basket_passes_numeric_needs_real_channel`。
- 回测指标说明：本阶段是账户层现金收益源重放，不新增交易订单；底层 C9 交易路径不变，因此不生成新增真实滑点、交易次数或胜率。
- 独立 agent 审查结论：账面计算未发现硬错误，DWJZ/LJJZ 货币基金字段解释基本合理；但该结论只能按 `30w 总账户体验` 的弱口径接受，不能解释为同资金策略本体回撤优化或稳健突破。最低收益保留仅 `50.1535%`，水下改善也不是每个起点都出现，且存在当前可购池/存续者偏差、历史申购状态未过滤、抓取失败未入通过闸门等问题。
- 运行前过拟合反思：否。篮子选择不使用收益排序或坏窗口。
- 运行后过拟合反思：若后续按篮子内历史表现挑基金或调篮子大小，就是过拟合；本阶段只验证固定规则篮子的账户层可行性。
- 继续价值：有，但只作为 Stage082 保守版输入；需重跑“抓取失败直接失败、缺失基金 0 收益、起点暂停申购不可买入”的 PIT 可购性口径，不得直接接入实盘默认路径。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage081_fixed_money_fund_basket_replay/rebuilt_c9_v2_stage081_fixed_money_fund_basket_replay_report_stage081_fixed_money_fund_basket_replay_v1.md`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage081_fixed_money_fund_basket_replay/rebuilt_c9_v2_stage081_fixed_money_fund_basket_replay_decision_stage081_fixed_money_fund_basket_replay_v1.json`
- basket：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage081_fixed_money_fund_basket_replay/rebuilt_c9_v2_stage081_fixed_money_fund_basket_replay_basket_stage081_fixed_money_fund_basket_replay_v1.csv`
- source_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage081_fixed_money_fund_basket_replay/rebuilt_c9_v2_stage081_fixed_money_fund_basket_replay_source_audit_stage081_fixed_money_fund_basket_replay_v1.csv`
- variant_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage081_fixed_money_fund_basket_replay/rebuilt_c9_v2_stage081_fixed_money_fund_basket_replay_variant_summary_stage081_fixed_money_fund_basket_replay_v1.csv`
