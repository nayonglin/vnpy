# Stage060 - late-adverse 前置信号与右尾冲突审计

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-01T22:17:25 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读归因，不改官方实盘配置。
- 是否重要突破：`否`
- 是否触发A/B：`否`

## 外部调研与判断

- 参考资料：TradesViz MAE/MFE duration、Rob Carver dynamic trend following、PyTrendFollow/pyfolio/backtesting.py 等系统化回测与复盘资料。
- 我的判断：late-adverse 需要区分入场后路径事实和入场前可见条件；路径事实不能作为开仓前预算规则，入场前条件必须同时看全样本右尾冲突。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage060_late_adverse_precursor_audit.py`
- 新增测试：`tests/test_rebuilt_c9_stage060_late_adverse_precursor.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：无交易参数；固定审计 `oi_confirmed`、`oi_and_selected_volume_gt1`、`selected_volume_gt1`、`not_full_market_ai_top8`、`rank_4_9`、`path_mfe_day0_1_mae_day4_10` 等条件。
- 修改参数：无。
- 删除参数：无。

## 结果

- 决策：`stage060_late_adverse_has_preentry_oi_candidate_needs_proxy`。
- target：`late_adverse_no_edge`。
- target lot：`35`。
- target realized PnL：`-235020.00`。
- target loss_abs：`235020.00`。
- 最优条件：`oi_confirmed`。
- 条件类型：`pre_entry_negative_full_pnl_candidate`。
- late-adverse loss_abs 捕获率：`100.0000%`。
- 全样本 PnL：`-10862524.00`。

## 回测指标说明

- 本阶段不是新增回测或真引擎 A/C，只读复用 Stage059 与 Stage038 输出，因此不产生新的期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数和胜率。
- 不连接 CTP，不调用订单 API，不改官方实盘配置。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage060_late_adverse_precursor_audit/rebuilt_c9_stage060_late_adverse_precursor_audit_report_stage060_late_adverse_precursor_audit_v1.md`
- tradeoff_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage060_late_adverse_precursor_audit/rebuilt_c9_stage060_late_adverse_precursor_audit_tradeoff_summary_stage060_late_adverse_precursor_audit_v1.csv`
- chart：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage060_late_adverse_precursor_audit/rebuilt_c9_stage060_late_adverse_precursor_audit_chart_stage060_late_adverse_precursor_audit_v1.png`

## 过拟合反思

- 运行前判断：否。只拆 Stage059 最大亏损形态，不新增交易参数。
- 运行后判断：否。本阶段只输出候选证据和右尾冲突，不把任何条件直接改成交易规则。

## 继续价值反思

- 运行前判断：有。Stage059 已证明 late-adverse 是最大 loss_abs 来源。
- 运行后判断：有。`oi_confirmed`/`oi_and_selected_volume_gt1` 同时捕获 late-adverse 且全样本 PnL 为负，但只能先做冻结 proxy，不能直接改线上。
