# Stage002 目标几何与路径缺口审计

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02 02:41 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：目标几何/路径缺口审计
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Bailey、Borwein、Lopez de Prado、Zhu：The Probability of Backtest Overfitting，https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253
  - Hurst、Ooi、Pedersen：Demystifying Managed Futures，https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/Demystifying-Managed-Futures.pdf
  - Rob Carver / pysystemtrade：Capital correction，https://qoppac.blogspot.com/2016/06/capital-correction-pysystemtrade.html
- 我的判断：
  - 当前目标是路径性质，不是终点收益性质；只看 `2026-06-30` 终点曲线会误判。
  - 继续优化前必须把“完整面板可比”和“半样本压力验证”拆开，否则会把样本少导致的低负窗口数误当成候选强。
  - 趋势右尾仍是核心资产，后续不能用简单暂停、缩手、锁盈或冷启动降风险换局部平滑。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage002_goal_geometry_gap_audit.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增测试：
  - `tests/test_rebuilt_c9_v2_stage002_goal_geometry_gap_audit.py`
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：读取上游已冻结输出，目标起点范围 `2020-01-01` 至 `2025-06-30`。
- 账户规模：沿用各上游阶段既有账户口径，主线为 C9/15w。
- 成本口径：沿用各上游阶段既有成本口径，本阶段不重新跑交易引擎。
- 样本过滤：完整面板可比候选要求 `all_gt1y_window_count = 7,215,647`；半样本压力验证候选保留在表中但不作为主排名依据。
- 策略/归因口径：汇总 Stage009/013/020/021/024/039/046/052/062/070/074/075 的 `goal_aggregate` 与 `worst_windows`。

## 结果

- 期末权益：本阶段未新增交易引擎回测。
- 总收益：本阶段未新增交易引擎回测。
- 最大回撤：本阶段未新增交易引擎回测。
- Sharpe：本阶段未新增交易引擎回测。
- 总滑点：本阶段未新增交易引擎回测。
- 总交易次数：本阶段未新增交易引擎回测。
- 胜率：本阶段未新增交易引擎回测。
- 其他关键指标：
  - 审计候选数 `30`。
  - 完整面板可比候选数 `28`，最大严格窗口数 `7,215,647`。
  - `start_to_2026_06_30_only` 终点口径通过候选数 `30/30`。
  - 严格任意 `>365` 天窗口目标通过候选数 `0/30`。
  - 完整面板负窗口最少候选：`Stage052:stage052_contract_oi_share_ge50_add_risk_proxy`，负窗口 `252,134/7,215,647`，最差收益 `-40.3699%`，终点口径最差 `24.7554%`。
  - 完整面板最差收益最高候选：`Stage074:full_market_ai_top8_and_active_positions_lt3_cold_start_ramp`，负窗口 `304,693/7,215,647`，最差收益 `-23.6338%`，终点口径最差 `13.5359%`。
  - 原始/早期高质量代理最差窗口仍集中在 `2022-07 -> 2023-07`，例如 `Stage009:base_stage006` 最差 `-55.2146%`。

## 输出文件

- report：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage002_goal_geometry_gap_audit/rebuilt_c9_v2_stage002_goal_geometry_gap_audit_report_stage002_goal_geometry_gap_audit_v1.md`
- summary：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage002_goal_geometry_gap_audit/rebuilt_c9_v2_stage002_goal_geometry_gap_audit_variant_metrics_stage002_goal_geometry_gap_audit_v1.csv`
- orders：无。
- daily：无。
- quality：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage002_goal_geometry_gap_audit/rebuilt_c9_v2_stage002_goal_geometry_gap_audit_worst_window_clusters_stage002_goal_geometry_gap_audit_v1.csv`
- chart：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage002_goal_geometry_gap_audit/rebuilt_c9_v2_stage002_goal_geometry_gap_audit_variant_goal_gap_chart_stage002_goal_geometry_gap_audit_v1.png`
- decision：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage002_goal_geometry_gap_audit/rebuilt_c9_v2_stage002_goal_geometry_gap_audit_decision_stage002_goal_geometry_gap_audit_v1.json`

## 结论

- 本阶段结论：当前已知重建版候选全部满足终点正收益口径，但没有任何候选满足严格任意 `>365` 天窗口无负收益；因此目标未达成。
- 是否进入下一步：是。
- 下一步：
  - 以完整面板为准，拆 `Stage052` 减少负窗口但最差仍深的原因，以及 `Stage074` 抬高最差收益但终点收益/保留不足的原因。
  - 下一阶段优先做“Stage052 vs Stage074 互补残差地图”，看两类改善是否互补，而不是继续扫 OI 阈值、冷启动天数或袖数。

## 过拟合反思

- 运行前判断：不过拟合。
- 运行后判断：不过拟合。
- 原因：本阶段只汇总已冻结候选的目标表现，并新增完整面板可比性约束；没有根据坏窗口创建交易规则或搜索参数。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：审计明确了“终点曲线好”和“严格路径目标未达”之间的差别，下一步可以针对剩余路径缺口设计因果实验。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新最新状态。
- 是否更新 `research/registry.md`：是，更新本线最新阶段。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段是路径审计，不是正式候选、重要突破或路线废弃。

