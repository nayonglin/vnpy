# Stage003 Stage052 vs Stage074 残差互补审计

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02 02:48 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：同窗互补上界审计
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - managed futures / trend following diversification：趋势跟随作为组合分散资产可能降低组合回撤。
  - Alpha Architect 多信号回测过拟合提醒：https://alphaarchitect.com/backtesting-strategies-based-multiple-signals-beware-overfitting-biases/
  - pysystemtrade backtesting / risk targeting 文档：https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md
- 我的判断：
  - 组合/ensemble 可能有价值，但不能因为 Stage052 和 Stage074 各自有一项指标好，就直接合并成候选。
  - 本阶段必须先做同一窗口的互补上界：同窗取 `max(Stage052, Stage074)` 后若仍失败，说明这两条旧路线本身互补不够。
  - Stage074 必须使用与 Stage002 一致的 start-reset ramp 口径，不能直接读原始 requested-start ramp panel 曲线，否则指标会错位。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage003_residual_complement_audit.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增测试：
  - `tests/test_rebuilt_c9_v2_stage003_residual_complement_audit.py`
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：目标起点范围 `2020-01-01` 至 `2025-06-30`，任意结束日周期 `>365` 自然日。
- 账户规模：沿用当前重建 C9/15w 研究口径。
- 成本口径：读取上游已冻结曲线，不新增交易引擎回测。
- 样本过滤：完整面板 `7,215,647` 个严格窗口。
- 策略/归因口径：
  - base：Stage013 `account_equity`。
  - Stage052：`stage052_contract_oi_share_ge50_add_risk_proxy`。
  - Stage074：`full_market_ai_top8_and_active_positions_lt3` 对每个目标起点重新施加 Stage074 start-reset ramp。
  - oracle 上界：每个窗口取 `max(Stage052_return, Stage074_return)`；这是不可交易上界，只用于判断互补是否足够。

## 结果

- 期末权益：本阶段未新增交易引擎回测。
- 总收益：本阶段未新增交易引擎回测。
- 最大回撤：本阶段未新增交易引擎回测。
- Sharpe：本阶段未新增交易引擎回测。
- 总滑点：本阶段未新增交易引擎回测。
- 总交易次数：本阶段未新增交易引擎回测。
- 胜率：本阶段未新增交易引擎回测。
- 其他关键指标：
  - 总窗口数 `7,215,647`。
  - base 负窗口 `330,947`。
  - Stage052 负窗口 `252,134`，最差 `-40.3699%`。
  - Stage074 负窗口 `304,693`，最差 `-23.6338%`。
  - oracle 上界负窗口 `194,804`，负窗口率 `2.6997%`，最差 `-23.6338%`。
  - base 负窗口中至少一条路线能修复 `136,242` 个；两条都没修复 `194,705` 个。
  - oracle 剩余最差窗口集中在 `2021-10 -> 2023-10/11` 和 `2022-07 -> 2023-07`。

## 输出文件

- report：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage003_residual_complement_audit/rebuilt_c9_v2_stage003_residual_complement_audit_report_stage003_residual_complement_audit_v1.md`
- summary：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage003_residual_complement_audit/rebuilt_c9_v2_stage003_residual_complement_audit_source_summary_stage003_residual_complement_audit_v1.csv`
- orders：无。
- daily：无。
- quality：
  - `research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage003_residual_complement_audit/rebuilt_c9_v2_stage003_residual_complement_audit_oracle_worst_windows_stage003_residual_complement_audit_v1.csv`
  - `research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage003_residual_complement_audit/rebuilt_c9_v2_stage003_residual_complement_audit_month_cluster_summary_stage003_residual_complement_audit_v1.csv`
- chart：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage003_residual_complement_audit/rebuilt_c9_v2_stage003_residual_complement_audit_negative_overlap_chart_stage003_residual_complement_audit_v1.png`
- decision：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage003_residual_complement_audit/rebuilt_c9_v2_stage003_residual_complement_audit_decision_stage003_residual_complement_audit_v1.json`

## 结论

- 本阶段结论：Stage052 和 Stage074 有一定互补，但互补上界仍远未达标；即使同窗取两者较好者，仍有 `194,804` 个严格负窗口，最差 `-23.6338%`。
- 是否进入下一步：是。
- 下一步：
  - 停止“Stage052 + Stage074 简单叠加/继续扫 OI 阈值/继续扫 ramp 参数”的方向。
  - 下一阶段应针对 oracle 剩余窗口做入场/持仓路径归因，重点看 `2021-10 -> 2023-10/11` 和 `2022-07 -> 2023-07` 剩余段究竟是趋势右尾缺失、恢复段暴露、还是信号池错配。

## 过拟合反思

- 运行前判断：不过拟合。
- 运行后判断：不过拟合。
- 原因：本阶段只使用已冻结的 Stage052/Stage074 两条路线做同窗上界，不新增参数、不选择日期规则、不写交易逻辑。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：Stage003 直接排除了“把两个旧候选简单叠加”的低质量路线，把后续研究聚焦到 oracle 剩余窗口的新机制。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新最新状态。
- 是否更新 `research/registry.md`：是，更新本线最新阶段。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是正式候选、重要突破或路线废弃。

