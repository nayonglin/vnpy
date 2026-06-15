# Stage065 Stage889 C9 亏损分钟形态覆盖审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：day
- 记录时间：2026-06-15 09:19 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：C9 本体只读覆盖审计；不新增交易规则，不接真实引擎。
- 是否重要突破：否。微弱正代理不具备推进价值。
- 是否触发A/B：否。

## 外部调研与判断

- 参考资料：
  - CME 风险管理/stop loss 教育资料：用于确认预设止损与账户风险约束是工程纪律。
  - CME open interest 教育资料：用于确认 OI 只能作为参与度辅助变量，不应单独决定退出。
  - 趋势跟随 whipsaw / false breakout 资料：用于确认假突破识别有意义，但不能复制参数。
- 我的判断：
  - C9 剩余亏损如果还有可交易形态，应该在 `0.5R`、`OR15`、`first60`、entry-day close 这些已冻结低自由度维度上表现为“救亏损明显多于砍赢家”。
  - Stage889 显示大量亏损确实被 `adverse_first` / `early60_adverse` 覆盖，但这些形态也覆盖大量右尾；可执行 proxy 多数明显为负。
  - 唯一微弱正代理 `neither +/-0.5R + 收盘反向 EOD exit` 只有 `+72,650`，触发 `12` 笔，正年份 `1`、负年份 `4`，不是能穿越周期的规则线索。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage889_stage863_c9_loss_shape_coverage_audit.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无交易参数；只使用已冻结审计维度 `0.5R`、`1R`、`OR15`、`first60`、entry-day close。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage863 C9 全周期 closed lots 与 Stage861 full minute bars。
- 账户规模：Stage819 候选 30w / C9 口径。
- 成本口径：沿用 Stage863 C9 closed lots；本阶段不重跑交易成本。
- 样本过滤：C9 arm `stage847_stage819_c4_05r_stop_retry_once`，closed lots `401`。
- 策略/归因口径：只读 per-lot minute shape coverage、EOD/first60/OR proxy、retry role summary、K线 atlas。

## 结果

- 期末权益：本阶段不新增组合回测；引用 C9 已有闭合 lot PnL 总计 `53,950,264.60`。
- 总收益：本阶段不新增组合回测。
- 最大回撤：本阶段不新增组合回测。
- Sharpe：本阶段不新增组合回测。
- 总滑点：本阶段不新增组合回测。
- 总交易次数：C9 closed lots `401`；Stage863 C9 trades `786`。
- 胜率：本阶段未重算整体胜率；closed lots 中赢家 `148`、亏损 `250`。
- 其他关键指标：
  - C9 loser PnL `-36,510,760.40`，winner PnL `90,461,025.00`。
  - `A_adverse_first_05r` 覆盖亏损 PnL `54.0518%`，但 winner PnL `17,971,900.00`，不是新规则。
  - `E_early60_adverse_any_oi` 覆盖亏损 PnL `53.0324%`，但 winner PnL `16,804,470.00`。
  - `EOD1_progress_first_close_below_entry` proxy delta `-2,421,820.00`，winner cut `-3,931,060.00`。
  - `EOD2_progress_first_close_adverse_half` proxy delta `-2,274,295.00`，winner cut `-6,788,515.00`。
  - `EARLY1_exit60_adverse_any_oi` proxy delta `-6,389,771.30`，winner cut `-15,337,920.00`。
  - `OR1_skip_extended_gt_1or` proxy delta `-3,242,482.40`，winner cut `-6,414,200.00`。
  - 唯一正代理 `EOD3_neither_05r_close_below_entry` 只有 delta `+72,650.00`，loser saved `475,050.00`，winner cut `-402,400.00`，正年份 `1`、负年份 `4`。
  - decision：`stage889_c9_loss_shape_tiny_positive_proxy_year_fragile_no_engine`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage889_stage863_c9_loss_shape_coverage_audit_report_stage889_stage863_c9_loss_shape_coverage_audit_v1.md`
- features：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage889_stage863_c9_loss_shape_coverage_audit_features_stage889_stage863_c9_loss_shape_coverage_audit_v1.csv`
- shape coverage：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage889_stage863_c9_loss_shape_coverage_audit_shape_coverage_stage889_stage863_c9_loss_shape_coverage_audit_v1.csv`
- proxy summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage889_stage863_c9_loss_shape_coverage_audit_proxy_summary_stage889_stage863_c9_loss_shape_coverage_audit_v1.csv`
- proxy yearly：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage889_stage863_c9_loss_shape_coverage_audit_proxy_yearly_stage889_stage863_c9_loss_shape_coverage_audit_v1.csv`
- retry role summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage889_stage863_c9_loss_shape_coverage_audit_retry_role_summary_stage889_stage863_c9_loss_shape_coverage_audit_v1.csv`
- summary chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage889_stage863_c9_loss_shape_coverage_audit_summary_chart_stage889_stage863_c9_loss_shape_coverage_audit_v1.png`
- atlas manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage889_stage863_c9_loss_shape_coverage_audit_atlas_manifest_stage889_stage863_c9_loss_shape_coverage_audit_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage889_stage863_c9_loss_shape_coverage_audit_decision_stage889_stage863_c9_loss_shape_coverage_audit_v1.json`

## 结论

- 本阶段结论：C9 本体的剩余分钟形态没有找到足够强的新规则。亏损覆盖最多的形态也大量覆盖赢家；唯一正代理幅度太小且年份脆弱，不进入真实引擎。
- 是否进入下一步：不沿 Stage889 的 EOD/first60/OR proxy 进入下一步。
- 下一步：停止在 C9 本体上扫 `0.5R/1R/OR15/first60/EOD close` 小变体；若继续本线，应转向新的低自由度外生信息源，或账户级非交易层生存线。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否；但如果继续拿 `EOD3` 这种 `+72,650` 的微弱正代理扫窗口/R/年份/品种，就会过拟合。
- 原因：本阶段只做覆盖审计，没有改策略，也没有用结果反推参数；结论是拒绝微弱信号，而不是救参。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：C9 分钟K本体继续价值下降；整条研究线仍有价值，但应换信息维度。
- 原因：本阶段压实了“C9 剩余亏损与右尾共享同一批分钟形态”的事实。继续在同一组分钟K内部变量上微调，边际收益很低。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage065 当前状态和后续规划。
- 是否更新 `research/registry.md`：否。本阶段不是正式候选、重要突破或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段为本线分支反证记录，不是正式候选或重要合入摘要。
