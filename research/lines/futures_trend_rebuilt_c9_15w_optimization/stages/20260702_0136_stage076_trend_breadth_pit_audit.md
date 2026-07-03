# Stage076 trend breadth PIT audit

- 时间：2026-07-02 01:36:24 CST
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 类型：只读候选级 PIT 审计，不改线上、不改实盘执行。
- 外部调研：趋势跟随长期有效性来自跨市场/跨资产分散和 time-series momentum，开源 `pysystemtrade` 也以多市场系统化组合为核心；因此本阶段采纳“整体趋势广度/参与度”作为低自由度候选信息，不采纳单品种/方向/窗口补丁。

## 版本变更

- 新增参数：`MAX_FEATURE_AGE_DAYS=7`，仅用于 T+1 market breadth 特征过期控制。
- 修改参数：无。
- 删除参数：无。
- 新增回测结果：无真实回测；新增候选级 OOS 条件审计和覆盖率审计。
- 修改回测结果：无。
- 删除回测结果：无。

## 结果

- 决策：`stage076_trend_breadth_keep_readonly_no_trade_rule`。
- entry_count：`2787`。
- matched_entry_pct：`97.5601%`。
- market date range：`2020-01-02 -> 2026-04-30`。
- entry date range：`2020-01-02 -> 2026-06-24`。
- has_recent_market_gap：`True`。
- stable OOS condition count：`0`。
- stable conditions：`无`。
- raw stable OOS conditions：`breadth_low_or_narrow_chop`。

## 条件摘要

| condition                                           |   count |        total_pnl |   mean_pnl_lift_vs_base |   oos_positive_fold_count |   oos_test_fold_count |   oos_min_fold_pnl | stable_oos_candidate   |      min_year_pnl |   negative_year_count |   top10_positive_pnl_share_pct | stage076_robust_candidate   |
|:----------------------------------------------------|--------:|-----------------:|------------------------:|--------------------------:|----------------------:|-------------------:|:-----------------------|------------------:|----------------------:|-------------------------------:|:----------------------------|
| breadth_low_or_narrow_chop                          |     759 |      3.40081e+07 |                  1.9871 |                         4 |                     4 |   283710           | True                   |      -3.5432e+06  |                     3 |                        33.2212 | False                       |
| account_injured_and_ai_top8_and_breadth_mid_or_high |     158 |      4.05971e+06 |                  1.1395 |                         1 |                     3 |  -213100           | False                  | -817320           |                     1 |                        78.2931 | False                       |
| broad_trend_regime                                  |     203 |      3.85547e+06 |                  0.8423 |                         3 |                     3 |   491710           | False                  | -451230           |                     2 |                        43.833  | False                       |
| breadth_high                                        |     478 |      6.94016e+06 |                  0.6439 |                         1 |                     3 |       -1.0538e+06  | False                  |      -1.83317e+06 |                     2 |                        42.3496 | False                       |
| full_market_ai_top8_and_breadth_mid_or_high         |     254 |      3.57951e+06 |                  0.625  |                         2 |                     3 |  -245500           | False                  | -135520           |                     1 |                        60.8558 | False                       |
| breadth_mid_or_high                                 |    2103 |      2.76025e+07 |                  0.5821 |                         2 |                     4 |       -1.06503e+07 | False                  |      -8.61955e+06 |                     3 |                        16.9007 | False                       |
| high_vol_low_eff_breadth_context                    |     407 |      2.45822e+06 |                  0.2679 |                         1 |                     3 |       -4.23393e+06 | False                  |      -4.50043e+06 |                     2 |                        36.2392 | False                       |
| account_injured_and_breadth_mid_or_high             |    1117 | 858588           |                  0.0341 |                         2 |                     4 |       -1.04761e+07 | False                  |      -5.99414e+06 |                     3 |                        24.0116 | False                       |
| full_market_ai_top8_and_broad_trend                 |      30 |     -1.0437e+06  |                 -1.5429 |                         0 |                     1 |       -1.0437e+06  | False                  | -613620           |                     2 |                                | False                       |
| full_market_ai_top8_and_breadth_high                |      97 |     -3.60899e+06 |                 -1.65   |                         0 |                     2 |       -3.56329e+06 | False                  |      -1.81828e+06 |                     3 |                        87.358  | False                       |
| breadth_matched                                     |    2719 |      6.40394e+07 |                  1.0445 |                         3 |                     4 |       -1.42048e+06 | False                  |      -6.0022e+06  |                     2 |                        14.4089 | False                       |

## 反思

- 运行前过拟合反思：否；本阶段先按外部趋势跟随分散化逻辑审计整体广度，不按最差窗口、品种、方向、月份或手数调参。
- 运行后过拟合反思：低但未消除；如果 stable 条件存在，也只能作为下一阶段冻结 proxy 的资格，不能直接按本阶段结果上线。
- 运行前继续价值反思：有价值；Stage074/075 证明账户冷启动降风险会伤右尾，广度/分散度是更贴近趋势策略本质的 PIT 信息。
- 运行后继续价值反思：取决于 stable 条件和覆盖缺口；若无稳定候选或覆盖缺口过大，应转向补齐 market daily 到 2026-06 或寻找新外生源。

## 后续规划和 TODO

- 下一步：`若 stable condition 非空，冻结一个条件做 add-risk/eligibility proxy；否则先补齐 market daily 或转新 PIT 信息源。`。
