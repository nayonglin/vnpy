# Stage078 real cash yield source audit

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T16:12:40
- 阶段性质：真实/基准现金收益源账户层审计
- 回测起点：`2020-01` 到 `2026-01` 逐半年，终点 `2026-06-30`
- 是否重要突破：否，暂未发现可直接接受的真实收益源

## 外部调研与判断

- managed futures/collateral return 资料支持现金或抵押品收益是账户总回报的一部分，但它不是交易 alpha。
- Backtrader/QuantConnect/pysystemtrade 这类框架也把利息或资本校正放在账户现金流/资本层，而不是交易信号层。
- 本阶段因此只做资金治理审计，不改 C9 交易逻辑。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage078_real_cash_yield_source_audit.py`
- 新增参数：`START_MONTHS=('2020-01', '2020-07', '2021-01', '2021-07', '2022-01', '2022-07', '2023-01', '2023-07', '2024-01', '2024-07', '2025-01', '2025-07', '2026-01')`、`RESERVE_CAPITAL=150000.0`、`TOTAL_CAPITAL=300000.0`。
- 修改参数：无正式交易参数。
- 删除参数：无。

## Source Audit

| source_id                   | source_label                             | source_kind              | is_direct_product   |   raw_rows |   calendar_rows | source_date_min   | source_date_max   |   c9_date_raw_coverage_pct |   calendar_raw_coverage_pct |   annualized_rate_min_pct |   annualized_rate_median_pct |   annualized_rate_latest_pct | latest_purchase_status   | latest_redeem_status   | notes                                                                                        |   fetch_error_count | fetch_errors_sample   | passes_stage077_numeric_goal   | accepted_for_cash_governance_replay   |
|:----------------------------|:-----------------------------------------|:-------------------------|:--------------------|-----------:|----------------:|:------------------|:------------------|---------------------------:|----------------------------:|--------------------------:|-----------------------------:|-----------------------------:|:-------------------------|:-----------------------|:---------------------------------------------------------------------------------------------|--------------------:|:----------------------|:-------------------------------|:--------------------------------------|
| benchmark_shibor_on         | SHIBOR O/N benchmark                     | benchmark_rate           | False               |       2316 |            2373 | 2015-05-08        | 2026-07-03        |                   100      |                     67.973  |                     0.441 |                       1.782  |                        1.369 |                          |                        | Benchmark only; not a directly investable reserve product.                                   |                   0 |                       | True                           | False                                 |
| benchmark_cfets_fr001_query | CFETS repo fixing FR001 query            | benchmark_rate           | False               |        748 |            2373 | 2023-07-03        | 2026-07-03        |                    46.1489 |                     31.3949 |                     1.15  |                       1.65   |                        1.4   |                          |                        | Benchmark query has short recent history in current AKShare endpoint.                        |                   0 |                       | False                          | False                                 |
| product_money_fund_000009   | Money fund 000009 actual income sample   | money_fund_actual_income | True                |       4680 |            2373 | 2013-03-25        | 2026-07-04        |                   100      |                    100      |                     0.817 |                       2.3885 |                        0.863 | 暂停申购                 | 开放赎回               | Actual daily per-10k income sample; current subscription status must be accepted separately. |                   0 |                       | True                           | False                                 |
| benchmark_cfets_fdr001_hist | CFETS deposit repo fixing FDR001 history | benchmark_rate           | False               |       1616 |            2373 | 2020-01-02        | 2026-06-30        |                   100      |                     68.0995 |                     0.43  |                       1.61   |                        1.35  |                          |                        | Monthly historical benchmark pulls; not a directly investable reserve product.               |                   0 |                       | True                           | False                                 |

## 结果

| version                                 | source_id                   |   start_count |   positive_count |   min_return_pct |   median_return_pct |   min_return_retention_ratio |   worst_drawdown_pct |   max_days_below_initial |   max_consecutive_below_initial_days | passes_stage077_numeric_goal   | accepted_for_cash_governance_replay   |
|:----------------------------------------|:----------------------------|--------------:|-----------------:|-----------------:|--------------------:|-----------------------------:|---------------------:|-------------------------:|-------------------------------------:|:-------------------------------|:--------------------------------------|
| official_c9_15w_reference               | official_c9                 |            13 |               13 |          1.90107 |            126.199  |                     1        |             -55.3701 |                      500 |                                  387 | False                          | False                                 |
| c9_15w_plus_benchmark_shibor_on         | benchmark_shibor_on         |            13 |               13 |          1.26577 |             65.4548 |                     0.501414 |             -52.7405 |                      485 |                                  383 | True                           | False                                 |
| c9_15w_plus_benchmark_cfets_fr001_query | benchmark_cfets_fr001_query |            13 |               13 |          1.28376 |             65.2016 |                     0.500646 |             -52.9109 |                      499 |                                  387 | False                          | False                                 |
| c9_15w_plus_product_money_fund_000009   | product_money_fund_000009   |            13 |               13 |          1.18056 |             65.3374 |                     0.501517 |             -52.7039 |                      485 |                                  383 | True                           | False                                 |
| c9_15w_plus_benchmark_cfets_fdr001_hist | benchmark_cfets_fdr001_hist |            13 |               13 |          1.26681 |             65.4674 |                     0.501416 |             -52.7406 |                      485 |                                  383 | True                           | False                                 |

## 结论

- 决策：`stage078_numeric_pass_but_no_accepted_real_cash_source`。
- 总滑点、总交易次数、胜率：本阶段是账户层现金收益源重放，不新增订单，底层 C9 交易路径不变，因此不生成新增真实滑点、交易次数或胜率。
- 运行前过拟合反思：否。真实收益源审计是 Stage077 的必要可实现性验证，不按坏窗口救参。
- 运行后过拟合反思：若按历史表现挑某只货币基金或忽略申购/赎回/税费/保证金占用，就是会计幻觉；本阶段以 accepted gate 阻止直接上线。
- 继续价值：有但条件化，需要真实可投、可申赎、可审计的现金产品或券商计息账本。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage078_real_cash_yield_source_audit/rebuilt_c9_v2_stage078_real_cash_yield_source_audit_report_stage078_real_cash_yield_source_audit_v1.md`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage078_real_cash_yield_source_audit/rebuilt_c9_v2_stage078_real_cash_yield_source_audit_decision_stage078_real_cash_yield_source_audit_v1.json`
- source_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage078_real_cash_yield_source_audit/rebuilt_c9_v2_stage078_real_cash_yield_source_audit_source_audit_stage078_real_cash_yield_source_audit_v1.csv`
- variant_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage078_real_cash_yield_source_audit/rebuilt_c9_v2_stage078_real_cash_yield_source_audit_variant_summary_stage078_real_cash_yield_source_audit_v1.csv`
