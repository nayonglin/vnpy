# Stage059 - 交易路径 MAE/MFE 归因

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-01T22:08:52 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读路径归因，不改官方实盘配置。
- 是否重要突破：`否`
- 是否触发A/B：`否`

## 外部调研与判断

- 参考资料：TradesViz MAE/MFE duration、TradeMetria MAE/MFE guide、NinjaTrader futures MAE risk、trend-following managed futures 资料。
- 我的判断：Stage059 只用 MAE/MFE 和持仓时长做亏损路径诊断，不用亏损品种、方向、日期或阈值直接写策略。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage059_trade_path_excursion_audit.py`
- 新增测试：`tests/test_rebuilt_c9_stage059_trade_path_excursion.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：无交易参数；路径分类固定为 `early_adverse_no_edge`、`gave_back_favorable_excursion`、`late_adverse_no_edge`、`winner`。
- 修改参数：无。
- 删除参数：无。

## 结果

- 决策：`stage059_pressure_losses_mixed_path_keep_readonly`。
- 样本行数：`246`。
- 亏损 lot 数：`189`。
- 赢家 lot 数：`57`。
- realized PnL：`-474365.00`。
- loss_abs：`576250.00`。
- 主形态：`late_adverse_no_edge`。
- 主形态 loss_abs 占比：`40.7844%`。
- early adverse loss_abs 占比：`34.8633%`。
- giveback loss_abs 占比：`24.3523%`。
- late adverse loss_abs 占比：`40.7844%`。

## 回测指标说明

- 本阶段不是新增回测或真引擎 A/C，只读复用 Stage055 逐笔结果，因此不产生新的期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数和胜率。
- 不连接 CTP，不调用订单 API，不改官方实盘配置。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage059_trade_path_excursion_audit/rebuilt_c9_stage059_trade_path_excursion_audit_report_stage059_trade_path_excursion_audit_v1.md`
- archetype_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage059_trade_path_excursion_audit/rebuilt_c9_stage059_trade_path_excursion_audit_archetype_summary_stage059_trade_path_excursion_audit_v1.csv`
- chart：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage059_trade_path_excursion_audit/rebuilt_c9_stage059_trade_path_excursion_audit_chart_stage059_trade_path_excursion_audit_v1.png`

## 过拟合反思

- 运行前判断：否。只做固定路径归因，不改交易参数。
- 运行后判断：否。本阶段只读复用既有 closed-lot 路径字段，没有新增交易参数或候选规则。

## 继续价值反思

- 运行前判断：有。Stage058 后需要确认压力亏损是入场早错、盈利回吐还是后段持仓问题。
- 运行后判断：有但需收窄。亏损路径混合，下一步应按亏损形态拆成独立假设，不要把所有压力窗口写成一个规则。
