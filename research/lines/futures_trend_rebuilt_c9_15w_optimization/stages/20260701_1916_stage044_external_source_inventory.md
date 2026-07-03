# Stage044 - 外生数据源资格库存审计

- 记录时间：`2026-07-01T19:16`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage044_external_source_inventory_v1`
- 决策：`stage044_external_inventory_found_basis_warehouse_need_pit_no_trade_rule`

## 口径

- 只审计本地已存在外生缓存，不写交易规则。
- 检查日期覆盖、产品覆盖、是否覆盖 `2022-2023` 左尾窗口、是否已有 point-in-time 证明。
- 不改官方 C9、不连接 CTP、不调用订单 API。

## 来源汇总

| source_name                        | source_path                                                                                                              | source_authority                       |   row_count | date_min   | date_max   |   unique_date_count |   product_count |   covers_objective_start |   covers_2022_left_tail |   covers_objective_end |   point_in_time_validated | readiness                               |
|:-----------------------------------|:-------------------------------------------------------------------------------------------------------------------------|:---------------------------------------|------------:|:-----------|:-----------|--------------------:|----------------:|-------------------------:|------------------------:|-----------------------:|--------------------------:|:----------------------------------------|
| domestic_basis_history_backfill    | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/external_supply_demand_cache        | third_party_akshare_100ppi             |       24482 | 2020-01-02 | 2026-04-17 |                1522 |              18 |                        0 |                       1 |                      0 |                         0 | history_candidate_needs_pit_validation  |
| domestic_warehouse_receipt_history | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/external_supply_demand_cache        | exchange_or_exchange_via_library_mixed |       13084 | 2020-01-02 | 2026-04-17 |                1523 |              17 |                        0 |                       1 |                      0 |                         0 | history_candidate_needs_pit_validation  |
| domestic_member_rank_history       | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/external_domestic_member_rank_cache | official_exchange_via_library          |       68857 | 2023-01-03 | 2026-04-17 |                 795 |              15 |                        0 |                       0 |                      0 |                         0 | forward_monitor_only                    |
| external_forward_ledger            | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/external_state_forward_ledger       | mixed_forward_monitor                  |         457 | 2026-05-29 | 2026-06-03 |                   4 |              37 |                        0 |                       0 |                      0 |                         1 | forward_monitor_only                    |
| cftc_cot_disaggregated_weekly      | /Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/external_cftc_cot_cache             | official_cftc                          |       78186 | 2020-01-07 | 2026-05-19 |                 333 |             371 |                        0 |                       1 |                      0 |                         1 | mapping_required_not_cn_direct_selector |

## 产品覆盖样例

| source_name                   | product_code                                        |   row_count | date_min   | date_max   |   unique_date_count |
|:------------------------------|:----------------------------------------------------|------------:|:-----------|:-----------|--------------------:|
| cftc_cot_disaggregated_weekly | ADHUBDAPEAKDAILYICEFUTURESENERGYDIV                 |           1 | 2020-05-26 | 2020-05-26 |                   1 |
| cftc_cot_disaggregated_weekly | AECOFINBASISICEFUTURESENERGYDIV                     |         333 | 2020-01-07 | 2026-05-19 |                 333 |
| cftc_cot_disaggregated_weekly | AEPDAYTONHUBDAPEAKDAILYICEFUTURESENERGYDIV          |          47 | 2020-07-14 | 2026-05-19 |                  47 |
| cftc_cot_disaggregated_weekly | ALGONQUINCITYGATESBASISICEFUTURESENERGYDIV          |         191 | 2022-01-25 | 2026-05-19 |                 191 |
| cftc_cot_disaggregated_weekly | ALGONQUINCITYGATESFINANCIALBASISICEFUTURESENERGYDIV |         107 | 2020-01-07 | 2022-01-18 |                 107 |
| cftc_cot_disaggregated_weekly | ALGONQUINCITYGATESINDEXICEFUTURESENERGYDIV          |          74 | 2022-05-24 | 2026-03-31 |                  74 |
| cftc_cot_disaggregated_weekly | ALUMEURUNPAIDCOMMODITYEXCHANGEINC                   |          10 | 2023-03-28 | 2023-07-03 |                  10 |
| cftc_cot_disaggregated_weekly | ALUMINIUMEUROPREMDUTYPAIDCOMMODITYEXCHANGEINC       |         264 | 2020-09-29 | 2026-05-19 |                 264 |
| cftc_cot_disaggregated_weekly | ALUMINIUMEUROPREMDUTYUNPAIDCOMMODITYEXCHANGEINC     |          45 | 2020-02-18 | 2021-12-28 |                  45 |
| cftc_cot_disaggregated_weekly | ALUMINUMCOMMODITYEXCHANGEINC                        |         141 | 2022-12-13 | 2026-02-03 |                 141 |
| cftc_cot_disaggregated_weekly | ALUMINUMMWPCOMMODITYEXCHANGEINC                     |         224 | 2022-02-08 | 2026-05-19 |                 224 |
| cftc_cot_disaggregated_weekly | ALUMINUMMWUSTRPLATTSCOMMODITYEXCHANGEINC            |         109 | 2020-01-07 | 2022-02-01 |                 109 |
| cftc_cot_disaggregated_weekly | ARGUSCIFARALGFINLPROPANEICEFUTURESENERGYDIV         |          91 | 2020-01-14 | 2026-05-19 |                  91 |
| cftc_cot_disaggregated_weekly | ARGUSFAREASTPROPANEICEFUTURESENERGYDIV              |         333 | 2020-01-07 | 2026-05-19 |                 333 |
| cftc_cot_disaggregated_weekly | ARGUSMARSVSWTITRADEMONTHICEFUTURESENERGYDIV         |          28 | 2020-01-07 | 2020-11-24 |                  28 |
| cftc_cot_disaggregated_weekly | ARGUSPROPANEFAREASTINDEXNEWYORKMERCANTILEEXCHANGE   |         333 | 2020-01-07 | 2026-05-19 |                 333 |
| cftc_cot_disaggregated_weekly | ARGUSPROPANESAUDIARAMCONEWYORKMERCANTILEEXCHANGE    |          59 | 2020-01-21 | 2025-05-27 |                  59 |
| cftc_cot_disaggregated_weekly | ARGUSWTIHOUSTONWTITRADEMOICEFUTURESENERGYDIV        |           2 | 2020-05-12 | 2020-05-19 |                   2 |
| cftc_cot_disaggregated_weekly | ARGUSWTIMIDWTITRADEMONTHICEFUTURESENERGYDIV         |         122 | 2020-02-04 | 2022-08-23 |                 122 |
| cftc_cot_disaggregated_weekly | BLACKSEAWHEATFINANCIALCHICAGOBOARDOFTRADE           |         112 | 2020-01-07 | 2022-02-22 |                 112 |
| cftc_cot_disaggregated_weekly | BRENTCRUDEOILLASTDAYNEWYORKMERCANTILEEXCHANGE       |         109 | 2020-01-07 | 2022-02-01 |                 109 |
| cftc_cot_disaggregated_weekly | BRENTLASTDAYNEWYORKMERCANTILEEXCHANGE               |         224 | 2022-02-08 | 2026-05-19 |                 224 |
| cftc_cot_disaggregated_weekly | BUTANEARGUSSAUDICPICEFUTURESENERGYDIV               |           1 | 2025-07-01 | 2025-07-01 |                   1 |
| cftc_cot_disaggregated_weekly | BUTANEOPISMTBELVNONTETFPICEFUTURESENERGYDIV         |         333 | 2020-01-07 | 2026-05-19 |                 333 |
| cftc_cot_disaggregated_weekly | BUTANEOPISMTBNONTETFIXICEFUTURESENERGYDIV           |           6 | 2026-01-13 | 2026-03-31 |                   6 |
| cftc_cot_disaggregated_weekly | BUTTERCASHSETTLEDCHICAGOMERCANTILEEXCHANGE          |         333 | 2020-01-07 | 2026-05-19 |                 333 |
| cftc_cot_disaggregated_weekly | CAISONPDAOFFPKFIXEDICEFUTURESENERGYDIV              |         311 | 2020-06-09 | 2026-05-19 |                 311 |
| cftc_cot_disaggregated_weekly | CAISONPOFFPEAKICEFUTURESENERGYDIV                   |          20 | 2020-01-21 | 2020-06-02 |                  20 |
| cftc_cot_disaggregated_weekly | CAISONPPEAKICEFUTURESENERGYDIV                      |         333 | 2020-01-07 | 2026-05-19 |                 333 |
| cftc_cot_disaggregated_weekly | CAISOSPDAOFFPKFIXEDICEFUTURESENERGYDIV              |         311 | 2020-06-09 | 2026-05-19 |                 311 |
| cftc_cot_disaggregated_weekly | CAISOSPFINDAOFFPEAKICEFUTURESENERGYDIV              |          22 | 2020-01-07 | 2020-06-02 |                  22 |
| cftc_cot_disaggregated_weekly | CAISOSPPEAKHEICEFUTURESENERGYDIV                    |          51 | 2025-05-20 | 2026-05-19 |                  51 |
| cftc_cot_disaggregated_weekly | CALIFCARBONALLOWANCEVICEFUTURESENERGYDIV            |         306 | 2020-01-07 | 2024-12-24 |                 215 |
| cftc_cot_disaggregated_weekly | CALIFCARBONALLOWANCEVNODALEXCHANGE                  |          84 | 2024-08-27 | 2026-05-19 |                  83 |
| cftc_cot_disaggregated_weekly | CALIFCARBONALLVINTAGEICEFUTURESENERGYDIV            |         272 | 2020-01-07 | 2026-05-19 |                 145 |
| cftc_cot_disaggregated_weekly | CALIFCARBONCURRENTAUCTIONICEFUTURESENERGYDIV        |         264 | 2020-03-17 | 2026-05-19 |                 264 |
| cftc_cot_disaggregated_weekly | CALIFCARBONICEFUTURESENERGYDIV                      |         173 | 2022-02-08 | 2023-12-19 |                  98 |
| cftc_cot_disaggregated_weekly | CALIFCARBONVINTAGEICEFUTURESENERGYDIV               |         212 | 2020-01-07 | 2022-02-01 |                 109 |
| cftc_cot_disaggregated_weekly | CALIFCARBONVINTAGESPECICEFUTURESENERGYDIV           |           8 | 2025-03-04 | 2025-12-23 |                   8 |
| cftc_cot_disaggregated_weekly | CALIFLOWCARBONFSCOPISICEFUTURESENERGYDIV            |         181 | 2022-12-06 | 2026-05-19 |                 181 |

## 判断

- 可作为下一步研究候选但必须补 PIT 规则的历史源：`['domestic_basis_history_backfill', 'domestic_warehouse_receipt_history']`。
- 只能 forward monitor 或映射不足的来源：`['domestic_member_rank_history', 'external_forward_ledger', 'cftc_cot_disaggregated_weekly']`。
- 当前没有任何来源可直接进入历史 selector；下一步若继续，应优先对 `warehouse_receipt` 和 `basis` 做 `T+1` 点时化与坏窗口覆盖归因。

## 输出

- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage044_external_source_inventory/rebuilt_c9_stage044_external_source_inventory_summary_stage044_external_source_inventory_v1.csv`
- product_coverage：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage044_external_source_inventory/rebuilt_c9_stage044_external_source_inventory_product_coverage_stage044_external_source_inventory_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage044_external_source_inventory/rebuilt_c9_stage044_external_source_inventory_decision_stage044_external_source_inventory_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage044_external_source_inventory/rebuilt_c9_stage044_external_source_inventory_report_stage044_external_source_inventory_v1.md`
- stage_record：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/stages/20260701_1916_stage044_external_source_inventory.md`

## 反思

- 运行前过拟合反思：否。本阶段是数据资格审计，不根据收益挑规则。
- 运行后过拟合反思：否。没有把 backfilled 外生数据直接用于交易；若跳过 PIT 验证直接做历史 selector 就会过拟合/泄漏。
- 运行前继续价值反思：有。Stage043 后必须寻找真正能解释左尾的外生状态。
- 运行后继续价值反思：有，但只限 `basis/warehouse` 的点时化和覆盖归因；CFTC 需要跨市场映射，member rank 缺 2022，forward ledger 历史太短。
