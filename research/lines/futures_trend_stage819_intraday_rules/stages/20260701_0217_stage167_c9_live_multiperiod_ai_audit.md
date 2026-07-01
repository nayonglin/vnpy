# Stage167 C9 15w 线上版本多周期回测与 AI 池审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-07-01 02:17 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：当前线上版本固定回放 + AI 池生效审计
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：未做外部策略调研。本阶段不是引入新策略或优化参数，而是复用仓库当前线上 profile 做固定回放与元数据审计；判断依据来自本地 `qmt_roll_official_live_config.py`、`qmt_roll_portfolio_strategy.py` 和 Stage901 live wrapper。
- 我的判断：这次应重点验证“线上 C9/15w 路径是否按月使用 Stage182 AI 池”，不应根据结果调资金、TopN、止损或品种池。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit.py`
- 修改脚本：无策略逻辑修改；仅在 Stage167 审计脚本内把首个 Stage182 快照 `2019-12-31` 当日及之前的候选归为 `PRE_AI_HISTORY`，原因是策略代码使用 `searchsorted(..., side="left") - 1`，即 AI 快照完成后才对后续交易日生效。
- 删除脚本：无
- 新增参数：无策略参数新增；回放固定 `2018-01-01` 起每半年一个冷启动起点，统一结束 `2026-06-30`。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：每半年起点 `2018-01-01`、`2018-07-01`、...、`2026-01-01`，统一结束 `2026-06-30`；共 `17` 个独立冷启动窗口。
- 账户规模：`150,000`
- 成本口径：沿用当前线上 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once` / Stage901 live wrapper；总滑点按回放逐窗口累计。
- 样本过滤：不做额外过滤。
- 策略/归因口径：当前线上 profile `stage847_c9_15w_stage819_05r_stop_retry_live`，AI 池为 `qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_stage182_ai_product_pool_live_inference_v1.csv`。

## AI 池审计

- AI 池 sha256：`8f54218d5c1922ebd4e0a2a16ef6d80c4f4392d1aa6c8cddd3f6127ffca574e3`
- AI 池行数：`477`
- AI eval_date：`2019-12-31` -> `2026-05-29`
- AI eval_date 数：`52`
- AI strategy：`ai_top8_plus_fu_satellite_post_signal_entry_filter`
- 候选行数：`9,751`
- 候选月份行：`918`
- 审计状态：`PASS 858`、`PRE_AI_HISTORY 60`、`FAIL 0`
- 结论：首个 AI 快照完成后的候选月份全部带有 AI enabled 和 signal-date 元数据；`2019-12-31` 及之前没有可用 Stage182 快照，按策略语义归为 `PRE_AI_HISTORY`，不是漏用 AI 的 bug。

## 结果

- 样本数：`17`
- 正收益样本：`17/17`
- 期末权益最低/中位/最高：`152,851.60` / `455,463.70` / `14,900,482.00`
- 总收益最低/中位/最高：`1.9011%` / `203.6425%` / `9,833.6547%`
- 期末权益：本阶段为多周期集合，单一代表值使用中位数 `455,463.70`
- 总收益：本阶段为多周期集合，单一代表值使用中位数 `203.6425%`
- 最大回撤：最差 `-56.2069%`，来自 `2018-01` 起点；中位 `-47.2779%`
- Sharpe：最低/中位/最高 `0.2860` / `1.1937` / `1.4786`
- 总滑点：`7,870,830`
- 总交易次数：`6,696`
- 胜率：中位非零日收益胜率 `52.2753%`
- 其他关键指标：peak broker10 margin/equity `96.6295%`；broker100 fail `0`；DD30 fail `10`，DD40 fail `9`，DD50 fail `8`。

## 起点明细

| 起点 | 期末权益 | 总收益 | 最大回撤 | Sharpe | peak broker10 |
|---|---:|---:|---:|---:|---:|
| 2018-01 | 12,857,154.10 | 8,471.4361% | -56.2069% | 1.3510 | 91.4950% |
| 2018-07 | 14,900,482.00 | 9,833.6547% | -55.3357% | 1.4479 | 89.9439% |
| 2019-01 | 13,776,968.70 | 9,084.6458% | -55.7845% | 1.4786 | 96.6295% |
| 2019-07 | 7,884,917.90 | 5,156.6119% | -54.8159% | 1.4228 | 87.0606% |
| 2020-01 | 5,979,281.00 | 3,886.1873% | -55.3701% | 1.3959 | 88.3398% |
| 2020-07 | 4,871,350.10 | 3,147.5667% | -54.7368% | 1.4052 | 85.9526% |
| 2021-01 | 2,395,239.80 | 1,496.8265% | -54.3180% | 1.2859 | 80.7461% |
| 2021-07 | 512,049.90 | 241.3666% | -47.2779% | 0.8355 | 72.3595% |
| 2022-01 | 323,799.00 | 115.8660% | -39.9820% | 0.6772 | 64.5100% |
| 2022-07 | 455,463.70 | 203.6425% | -55.1835% | 0.9290 | 72.7529% |
| 2023-01 | 338,069.40 | 125.3796% | -24.4690% | 0.9137 | 59.9696% |
| 2023-07 | 419,165.20 | 179.4435% | -24.3785% | 1.1937 | 63.9855% |
| 2024-01 | 339,299.00 | 126.1993% | -22.5622% | 1.2246 | 55.8731% |
| 2024-07 | 226,852.80 | 51.2352% | -23.3751% | 0.7898 | 65.2040% |
| 2025-01 | 198,567.40 | 32.3783% | -22.6508% | 0.7362 | 56.9317% |
| 2025-07 | 198,222.40 | 32.1483% | -17.9182% | 1.0469 | 48.8226% |
| 2026-01 | 152,851.60 | 1.9011% | -14.7303% | 0.2860 | 51.5137% |

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_report_stage167_c9_live_15w_multiperiod_ai_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_summary_stage167_c9_live_15w_multiperiod_ai_audit_v1.csv`
- stats：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_stats_stage167_c9_live_15w_multiperiod_ai_audit_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_curves_stage167_c9_live_15w_multiperiod_ai_audit_v1.csv`
- entry_candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_entry_candidates_stage167_c9_live_15w_multiperiod_ai_audit_v1.csv`
- ai_month_audit：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_ai_month_audit_stage167_c9_live_15w_multiperiod_ai_audit_v1.csv`
- ai_pool_audit：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_ai_pool_audit_stage167_c9_live_15w_multiperiod_ai_audit_v1.csv`
- performance_chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_performance_chart_stage167_c9_live_15w_multiperiod_ai_audit_v1.png`
- absolute_equity_chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_absolute_equity_chart_stage167_c9_live_15w_multiperiod_ai_audit_v1.png`
- ai_audit_chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_ai_audit_chart_stage167_c9_live_15w_multiperiod_ai_audit_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_decision_stage167_c9_live_15w_multiperiod_ai_audit_v1.json`

## 结论

- 本阶段结论：当前线上 C9/15w 版本能完成多周期回放；首个 Stage182 AI 快照之后的每个有候选月份都带 AI 池元数据，`FAIL=0`。但左尾仍重，早期起点最大回撤约 `-55%` 至 `-56%`，不能因为长期右尾强就忽略实盘承受力。
- 是否进入下一步：是，但下一步应做风险尾归因或执行前健康检查，不应根据这次多起点结果救参。
- 下一步：如继续研究，应围绕 DD50 起点和 broker10 高水位做账户层风险归因；如用于实盘，则继续按当前 Stage901/Stage162 健康门和 Phase D SOP 执行。

## 过拟合反思

- 运行前判断：否。起点、结束日、资金、C9 规则和 Stage182 AI 池均预先固定，不根据结果调参数。
- 运行后判断：否。本次只做固定线上版本多起点回放和 AI 元数据审计，没有修改 AI 池、TopN、品种或 C9 参数。
- 原因：唯一脚本修正是审计标签语义，策略回放路径和交易逻辑未变。

## 继续价值反思

- 运行前判断：是。用户关心当前线上版本和 AI 选品是否仍按月生效，多周期回放加 AI 审计能直接回答。
- 运行后判断：是。结果可作为当前线上路径风险基准。
- 原因：AI 漏用问题已排除，剩余主要问题是当前线上版本本身的高回撤尾部。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新。本阶段是审计与回放记录，未改变研究线状态。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是重要突破或正式候选变更。
