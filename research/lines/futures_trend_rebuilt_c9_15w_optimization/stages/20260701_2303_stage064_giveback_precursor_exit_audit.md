# Stage064 - giveback 前置信号与退出路径审计

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-01T23:03:55 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读归因，不改官方实盘配置。
- 是否重要突破：`否`
- 是否触发A/B：`否`

## 外部调研与判断

- 参考资料：Rob Carver dynamic trend following、TradeStation MFE graph、TradeMetria MAE/MFE、Investopedia trailing stops、pysystemtrade。
- 我的判断：giveback 方向不能直接止盈化；只有入场前可见且不撞全样本右尾的条件才可能进入预算 proxy，入场后 MFE/MAE 只能先保留为退出路径审计入口。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage064_giveback_precursor_exit_audit.py`
- 新增测试：`tests/test_rebuilt_c9_stage064_giveback_precursor.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：无交易参数；固定审计入场前质量/账户/相关性条件和 `path_mfe_ge1/ge2/ge3`、`path_mfe_before_mae` 等 path diagnostic 条件。
- 修改参数：无。
- 删除参数：无。

## 结果

- 决策：`stage064_giveback_no_clean_preentry_candidate_keep_exit_diagnostic`。
- target：`gave_back_favorable_excursion`。
- target lot：`100`。
- target realized PnL：`-140330.00`。
- target loss_abs：`140330.00`。
- 最优入场前条件：`not_full_market_consensus_top8`。
- 条件类型：`right_tail_collision`。
- giveback loss_abs 捕获率：`100.0000%`。
- 全样本 PnL：`50248642.20`。

## 回测指标说明

- 本阶段不是新增回测或真引擎 A/C，只读复用 Stage059 与 Stage038 输出，因此不产生新的期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数和胜率。
- 不连接 CTP，不调用订单 API，不改官方实盘配置。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage064_giveback_precursor_exit_audit/rebuilt_c9_stage064_giveback_precursor_exit_audit_report_stage064_giveback_precursor_exit_audit_v1.md`
- tradeoff_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage064_giveback_precursor_exit_audit/rebuilt_c9_stage064_giveback_precursor_exit_audit_tradeoff_summary_stage064_giveback_precursor_exit_audit_v1.csv`
- chart：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage064_giveback_precursor_exit_audit/rebuilt_c9_stage064_giveback_precursor_exit_audit_chart_stage064_giveback_precursor_exit_audit_v1.png`

## 过拟合反思

- 运行前判断：否。只拆 Stage059 第三类 giveback 亏损形态，不新增交易参数。
- 运行后判断：否。本阶段只输出候选证据、路径事实和右尾冲突，不把任何条件直接改成交易规则。

## 继续价值反思

- 运行前判断：有。Stage059 已证明 giveback 是压力亏损的独立来源。
- 运行后判断：有但不能直接交易化。giveback 的高捕获证据主要是入场后 MFE/MAE 路径事实；入场前条件若撞全样本右尾，就不能变成预算过滤。下一步若继续，只能做低自由度退出路径审计或账户外层设计。
