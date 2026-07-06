# Stage077 C9 idle reserve cash yield proxy

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T16:03:14
- 阶段性质：30w 缓冲资金现金收益 curve-level proxy
- 回测起点：`2020-01` 到 `2026-01` 逐半年，终点 `2026-06-30`
- 是否重要突破：是，代理满足新目标但需真实收益源验证

## 外部调研与判断

- managed futures 文献支持现金/抵押品收益是账户总回报的一部分；pysystemtrade capital correction 支持区分总资本和在险资本。
- 本阶段不把收益率当策略参数优化，只做固定情景 `0/1/2/3/5%`。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage077_c9_idle_reserve_cash_yield_proxy.py`
- 新增参数：`ANNUAL_YIELD_RATES=(0.0, 0.01, 0.02, 0.03, 0.05)`。
- 新增口径参数：`START_MONTH_MIN=2020-01`、`START_MONTH_MAX=2026-01`、`REQUESTED_END=2026-06-30`。
- 修改参数：无正式交易参数。
- 删除参数：无。

## 结果

| version                               | variant_label                  |   annual_yield_rate |   start_count |   positive_count |   min_return_pct |   median_return_pct |   max_return_pct |   min_return_retention_ratio |   median_return_retention_ratio |   worst_drawdown_pct |   median_drawdown_pct |   max_days_below_initial |   median_days_below_initial |   max_consecutive_below_initial_days |   median_consecutive_below_initial_days |
|:--------------------------------------|:-------------------------------|--------------------:|--------------:|-----------------:|-----------------:|--------------------:|-----------------:|-----------------------------:|--------------------------------:|---------------------:|----------------------:|-------------------------:|----------------------------:|-------------------------------------:|----------------------------------------:|
| official_c9_15w_reference             | Official C9 15w reference      |                0    |            13 |               13 |         1.90107  |            126.199  |          3886.19 |                     1        |                        1        |             -55.3701 |              -24.469  |                      500 |                          20 |                                  387 |                                      16 |
| c9_15w_plus_idle_reserve_yield_0000bp | C9 15w + idle reserve yield 0% |                0    |            13 |               13 |         0.950533 |             63.0997 |          1943.09 |                     0.5      |                        0.5      |             -52.9113 |              -18.7861 |                      500 |                          20 |                                  387 |                                      16 |
| c9_15w_plus_idle_reserve_yield_0100bp | C9 15w + idle reserve yield 1% |                0.01 |            13 |               13 |         1.19084  |             64.4556 |          1946.43 |                     0.500858 |                        0.51056  |             -52.8072 |              -18.6352 |                      494 |                          20 |                                  383 |                                      16 |
| c9_15w_plus_idle_reserve_yield_0200bp | C9 15w + idle reserve yield 2% |                0.02 |            13 |               13 |         1.42992  |             66.2655 |          1949.95 |                     0.501765 |                        0.521545 |             -52.7002 |              -18.4828 |                      485 |                          20 |                                  383 |                                      16 |
| c9_15w_plus_idle_reserve_yield_0300bp | C9 15w + idle reserve yield 3% |                0.03 |            13 |               13 |         1.66779  |             68.12   |          1953.67 |                     0.502721 |                        0.53297  |             -52.5903 |              -18.3289 |                      479 |                          20 |                                  288 |                                      16 |
| c9_15w_plus_idle_reserve_yield_0500bp | C9 15w + idle reserve yield 5% |                0.05 |            13 |               13 |         2.13997  |             71.9658 |          1961.72 |                     0.504794 |                        0.557189 |             -52.3615 |              -18.0164 |                      389 |                          18 |                                  255 |                                      16 |

## 结论

- 决策：`stage077_cash_yield_proxy_candidate_needs_real_yield_source`。
- 运行前过拟合反思：否。现金收益是外部账户层变量，固定情景不是坏窗口救参。
- 运行后过拟合反思：若按结果挑一个不可获得的年化收益率或忽略流动性/税费，就是统计幻觉。
- 继续价值：只有低现实收益率也能通过时，才值得进入真实资金产品/流动性审计。
