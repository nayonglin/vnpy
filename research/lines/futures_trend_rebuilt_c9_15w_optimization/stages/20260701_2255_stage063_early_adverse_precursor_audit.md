# Stage063 - early-adverse 前置信号与右尾冲突审计

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-01T22:55:50 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读归因，不改官方实盘配置。
- 是否重要突破：`否`
- 是否触发A/B：`否`

## 外部调研与判断

- 参考资料：TradesViz MAE/MFE、TradeMetria MAE/MFE、NinjaTrader MAE futures risk、Rob Carver dynamic trend following、pysystemtrade。
- 我的判断：early-adverse 只能先做入场前条件与右尾冲突审计；不能把路径事实或压力窗口内的品种/方向直接变成交易规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage063_early_adverse_precursor_audit.py`
- 新增测试：`tests/test_rebuilt_c9_stage063_early_adverse_precursor.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：无交易参数；固定审计 `selected_volume_gt1/ge5/ge10`、`ai_rank`、`oi_confirmed`、`full_market_ai_top8`、`loss_streak/drawdown/account`、相关性、risk multiplier 与少量 path diagnostic 条件。
- 修改参数：无。
- 删除参数：无。

## 结果

- 决策：`stage063_early_adverse_no_clean_preentry_candidate_keep_readonly`。
- target：`early_adverse_no_edge`。
- target lot：`54`。
- target realized PnL：`-200900.00`。
- target loss_abs：`200900.00`。
- 最优入场前条件：`not_full_market_consensus_top8`。
- 条件类型：`right_tail_collision`。
- early-adverse loss_abs 捕获率：`100.0000%`。
- 全样本 PnL：`50248642.20`。

## 回测指标说明

- 本阶段不是新增回测或真引擎 A/C，只读复用 Stage059 与 Stage038 输出，因此不产生新的期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数和胜率。
- 不连接 CTP，不调用订单 API，不改官方实盘配置。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage063_early_adverse_precursor_audit/rebuilt_c9_stage063_early_adverse_precursor_audit_report_stage063_early_adverse_precursor_audit_v1.md`
- tradeoff_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage063_early_adverse_precursor_audit/rebuilt_c9_stage063_early_adverse_precursor_audit_tradeoff_summary_stage063_early_adverse_precursor_audit_v1.csv`
- chart：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage063_early_adverse_precursor_audit/rebuilt_c9_stage063_early_adverse_precursor_audit_chart_stage063_early_adverse_precursor_audit_v1.png`

## 过拟合反思

- 运行前判断：否。只拆 Stage059 第二大亏损形态，不新增交易参数。
- 运行后判断：否。本阶段只输出候选证据和右尾冲突，不把任何条件直接改成交易规则。

## 继续价值反思

- 运行前判断：有。Stage059 已证明 early-adverse 是第二大 loss_abs 来源。
- 运行后判断：有但方向要转窄。early-adverse 的高捕获入场前条件撞全样本右尾；全样本为负的 OI 条件捕获不足，不能进入 proxy。下一步更适合做 giveback 路径审计或账户外层设计。
