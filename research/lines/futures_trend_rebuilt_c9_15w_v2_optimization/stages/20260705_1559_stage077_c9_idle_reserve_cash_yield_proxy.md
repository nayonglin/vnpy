# Stage077 C9 idle reserve cash yield proxy

- 口径状态：已废弃。首跑误用了 C9 曲线中的 `2018-01` 到 `2026-01` 共 17 个起点；当前有效口径见 `20260705_1603_stage077_c9_idle_reserve_cash_yield_proxy.md`，使用 `2020-01` 到 `2026-01` 共 13 个逐半年起点。

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T15:59:42
- 阶段性质：30w 缓冲资金现金收益 curve-level proxy
- 是否重要突破：是，代理满足新目标但需真实收益源验证

## 外部调研与判断

- managed futures 文献支持现金/抵押品收益是账户总回报的一部分；pysystemtrade capital correction 支持区分总资本和在险资本。
- 本阶段不把收益率当策略参数优化，只做固定情景 `0/1/2/3/5%`。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage077_c9_idle_reserve_cash_yield_proxy.py`
- 新增参数：`ANNUAL_YIELD_RATES=(0.0, 0.01, 0.02, 0.03, 0.05)`。
- 修改参数：无正式交易参数。
- 删除参数：无。

## 结果

| version                               | variant_label                  |   annual_yield_rate |   start_count |   positive_count |   min_return_pct |   median_return_pct |   max_return_pct |   min_return_retention_ratio |   median_return_retention_ratio |   worst_drawdown_pct |   median_drawdown_pct |   max_days_below_initial |   median_days_below_initial |   max_consecutive_below_initial_days |   median_consecutive_below_initial_days |
|:--------------------------------------|:-------------------------------|--------------------:|--------------:|-----------------:|-----------------:|--------------------:|-----------------:|-----------------------------:|--------------------------------:|---------------------:|----------------------:|-------------------------:|----------------------------:|-------------------------------------:|----------------------------------------:|
| official_c9_15w_reference             | Official C9 15w reference      |                0    |            17 |               17 |         1.90107  |             203.642 |          9833.65 |                     1        |                        1        |             -56.2069 |              -47.2779 |                      500 |                          25 |                                  387 |                                      17 |
| c9_15w_plus_idle_reserve_yield_0000bp | C9 15w + idle reserve yield 0% |                0    |            17 |               17 |         0.950533 |             101.821 |          4916.83 |                     0.5      |                        0.5      |             -54.9499 |              -32.8565 |                      500 |                          25 |                                  387 |                                      17 |
| c9_15w_plus_idle_reserve_yield_0100bp | C9 15w + idle reserve yield 1% |                0.01 |            17 |               17 |         1.19084  |             103.85  |          4920.97 |                     0.500421 |                        0.509945 |             -54.8706 |              -32.4542 |                      494 |                          25 |                                  383 |                                      17 |
| c9_15w_plus_idle_reserve_yield_0200bp | C9 15w + idle reserve yield 2% |                0.02 |            17 |               17 |         1.42992  |             105.94  |          4925.4  |                     0.500872 |                        0.520038 |             -54.7873 |              -32.0484 |                      485 |                          24 |                                  383 |                                      17 |
| c9_15w_plus_idle_reserve_yield_0300bp | C9 15w + idle reserve yield 3% |                0.03 |            17 |               17 |         1.66779  |             108.092 |          4930.16 |                     0.501355 |                        0.530279 |             -54.7001 |              -31.6391 |                      479 |                          24 |                                  288 |                                      17 |
| c9_15w_plus_idle_reserve_yield_0500bp | C9 15w + idle reserve yield 5% |                0.05 |            17 |               17 |         2.13997  |             112.588 |          4940.68 |                     0.502426 |                        0.551211 |             -54.5128 |              -30.8101 |                      389 |                          24 |                                  255 |                                      16 |

## 结论

- 决策：`stage077_cash_yield_proxy_candidate_needs_real_yield_source`。
- 运行前过拟合反思：否。现金收益是外部账户层变量，固定情景不是坏窗口救参。
- 运行后过拟合反思：若按结果挑一个不可获得的年化收益率或忽略流动性/税费，就是统计幻觉。
- 继续价值：只有低现实收益率也能通过时，才值得进入真实资金产品/流动性审计。
