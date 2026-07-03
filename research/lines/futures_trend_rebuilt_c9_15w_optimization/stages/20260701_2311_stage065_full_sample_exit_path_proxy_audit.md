# Stage065 - 全样本退出路径 proxy 审计

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-01T23:11:48 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读 proxy 上界，不改官方实盘配置。
- 是否重要突破：`否`
- 是否触发A/B：`否`

## 外部调研与判断

- 参考资料：Rob Carver dynamic trend following/stop losses、TradeStation MFE graph、TradesViz MFE/MAE、pysystemtrade。
- 我的判断：趋势跟随不能机械止盈，必须先检查全样本右尾冲突。本阶段所有 proxy 都是乐观上界，不是真实成交路径。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage065_full_sample_exit_path_proxy_audit.py`
- 新增测试：`tests/test_rebuilt_c9_stage065_exit_path_proxy.py`
- 修改脚本：无正式策略脚本修改；审计脚本修复 Stage059 pressure lot paths 只有 `r_multiple_agg` 时的 `r_multiple` 兼容口径，并用回归测试覆盖。
- 删除脚本：无。
- 新增参数：无交易参数；固定审计 `hard_takeprofit_1/2/4/8r`、`optimistic_breakeven_after_1/2/4r`、`optimistic_lock_1r_after_2r`、`optimistic_lock_1/2r_after_4/8r`。
- 修改参数：无。
- 删除参数：无。

## 结果

- 决策：`stage065_exit_proxy_has_candidate_needs_true_engine`。
- best proxy：`optimistic_breakeven_after_1r`。
- proxy class：`proxy_candidate_needs_true_engine`。
- full retention：`146.7293%`。
- pressure delta：`140330.00`。
- winner cut：`0.00`。
- loser saved：`29913735.00`。
- 压力样本：`246` 笔；`optimistic_breakeven_after_1r` 触发 `100` 笔，全部来自 `gave_back_favorable_excursion`，不命中 `early_adverse_no_edge`、`late_adverse_no_edge` 或 winner。
- 反证项：`hard_takeprofit_1/2/8r` 虽有压力样本改善，但全样本收益保留失败或大幅砍掉 big winner，其中 `hard_takeprofit_8r` 仍触发 `242` 个 big winner。

## 回测指标说明

- 本阶段不是新增回测或真引擎 A/C，只读复用 Stage013 closed lots 与 Stage059 pressure lot paths，因此不产生新的期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数和胜率。
- 不连接 CTP，不调用订单 API，不改官方实盘配置。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage065_full_sample_exit_path_proxy_audit/rebuilt_c9_stage065_full_sample_exit_path_proxy_audit_report_stage065_full_sample_exit_path_proxy_audit_v1.md`
- proxy_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage065_full_sample_exit_path_proxy_audit/rebuilt_c9_stage065_full_sample_exit_path_proxy_audit_proxy_summary_stage065_full_sample_exit_path_proxy_audit_v1.csv`
- chart：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage065_full_sample_exit_path_proxy_audit/rebuilt_c9_stage065_full_sample_exit_path_proxy_audit_chart_stage065_full_sample_exit_path_proxy_audit_v1.png`

## 过拟合反思

- 运行前判断：否。只审计低自由度退出 proxy 上界，不新增真引擎交易参数。
- 运行后判断：否。本阶段只读复用 closed-lot MFE/MAE，不根据结果调整止盈/锁盈阈值。

## 继续价值反思

- 运行前判断：有。Stage064 证明 giveback 只能作为退出路径诊断，需要确认全样本右尾冲突强度。
- 运行后判断：有。存在压力样本改善且全样本收益保留通过的 optimistic exit proxy，但它只是 closed-lot 乐观上界；下一步只能冻结 `optimistic_breakeven_after_1r` 做真实引擎验真，不能直接上线或扫保本/锁盈参数。
