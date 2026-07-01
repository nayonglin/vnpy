# Stage158 当前重建版 C9/C4 回撤压力归因

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-07-01 00:42 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读归因；基于 Stage157 已生成日级差异与 stop/retry 事件，不重跑策略、不连接 CTP、不调用订单 API
- 是否重要突破：否，但它把下一步优化方向从“扫 C9 stop/retry 参数”转向“账户层 heat/survival 治理”
- 是否触发A/B：否，本阶段没有新策略候选，也没有准备接入正式版本

## 外部调研与判断

- 参考资料：本阶段按用户约束不再搜索外部资料；只使用本仓库 `memory.md/back_log.md` 已梳理的正式路线、Stage156 三臂对比、Stage157 C9 stop/retry 归因输出。
- 我的判断：当前问题不是“AI 是否还在”或“开仓日实时止损重试是否生效”的二选一；Stage155/156/157 已显示 AI 和 C9 都有价值，但 C9 的收益优势伴随部分窗口更深回撤。Stage158 需要判断这些回撤是绝对亏损更差，还是高峰值后的百分比回吐更难看。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage158_current_rebuild_c9_c4_drawdown_pressure_attribution.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数；新增归因标签 `gap_shape`、`trough_shape`、`c9_window_*`、`gap_window_*`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：年度起点 `2018-01` 至 `2026-01`，终点沿用 Stage157 输出到 `2026-06-30`
- 账户规模：沿用当前重建版 `15w` 口径
- 成本口径：沿用 Stage156/157 输出，不新增成本假设
- 样本过滤：9 个年度起点；只比较 Stage819/C4 broker10 cap 与 Stage847/C9 stop retry
- 策略/归因口径：
  - 读取 `qmt_roll_stage157_current_rebuild_c9_stop_retry_attribution_daily_delta_stage157_current_rebuild_c9_stop_retry_attribution_v1.csv`
  - 读取 `qmt_roll_stage157_current_rebuild_c9_stop_retry_attribution_stop_retry_events_stage157_current_rebuild_c9_stop_retry_attribution_v1.csv`
  - 对每个年度起点计算 C4/C9 最大回撤、C9-C4 回撤差最差日期、C9 最大回撤 peak-to-trough 窗口、回撤差最差日正负 30 天窗口
  - 对窗口内 stop/retry 事件数、retry_failed、reentered、broker10 保证金/权益差做聚合

## 结果

- 期末权益：不新增回测，沿用 Stage156/157；本阶段不重复统计
- 总收益：不新增回测，沿用 Stage156/157；本阶段不重复统计
- 最大回撤：归因结果显示 C9 最大回撤劣于 C4 的年度起点为 `5/9`
- Sharpe：不新增回测，沿用 Stage156/157；本阶段不重复统计
- 总滑点：沿用 Stage156/157 输出；本阶段不新增滑点假设
- 总交易次数：沿用 Stage156/157 输出；本阶段不新增交易
- 胜率：不适用
- 其他关键指标：
  - C9 最大回撤劣于 C4：`5/9`
  - 在 C9-C4 回撤差最差日期，C9 百分比回撤更差但绝对权益仍高于 C4：`3/9`
  - 在 C9 自身最大回撤谷底，C9 百分比回撤更深但绝对权益仍高于 C4：`5/9`
  - C9 最大回撤 peak-to-trough 窗口内 stop/retry 事件合计：`2`
  - C9 最大回撤 peak-to-trough 窗口内 retry_failed 合计：`0`
  - 回撤差最差日正负 30 天窗口内 stop/retry 事件合计：`9`
  - 回撤差最差日正负 30 天窗口内 retry_failed 合计：`0`
  - 最严重回撤差发生在 `2018-01` 起点的 `2020-10-27`：C9 回撤 `-9.7348%`、C4 回撤 `-0.8448%`，差值 `-8.8900pp`，但 C9 绝对权益 `428,802.2` 高于 C4 `248,828.0`
  - `2021-01`、`2022-01`、`2024-01` 起点的回撤差窗口出现较大的 broker10 保证金/权益差，分别约 `59.10pp`、`27.86pp`、`26.08pp`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage158_current_rebuild_c9_c4_drawdown_pressure_attribution_report_stage158_current_rebuild_c9_c4_drawdown_pressure_attribution_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage158_current_rebuild_c9_c4_drawdown_pressure_attribution_window_summary_stage158_current_rebuild_c9_c4_drawdown_pressure_attribution_v1.csv`
- orders：无
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage158_current_rebuild_c9_c4_drawdown_pressure_attribution_pressure_days_stage158_current_rebuild_c9_c4_drawdown_pressure_attribution_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage158_current_rebuild_c9_c4_drawdown_pressure_attribution_decision_stage158_current_rebuild_c9_c4_drawdown_pressure_attribution_v1.json`
- event summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage158_current_rebuild_c9_c4_drawdown_pressure_attribution_event_window_summary_stage158_current_rebuild_c9_c4_drawdown_pressure_attribution_v1.csv`

## 结论

- 本阶段结论：
  - C9 的主要回撤压力不能简单归因于 stop/retry 失败；C9 最大回撤窗口内 `retry_failed=0`，多数旧起点的大回撤窗口甚至没有 stop/retry 事件。
  - C9 回撤更深有相当部分是“赚到更高峰值后回吐更多”的百分比问题，而不是绝对权益必然低于 C4。
  - 因此不应按某个日期、品种、方向、retry 状态做回看过滤；那会把 C9 的正向复利路径一起砍掉。
  - 更合理的下一步是研究账户层生存线、保证金热度、权益高水位后的锁定/分层，而不是继续扫描 C9 的 `0.5R`、重试次数、月份或品种黑名单。
- 是否进入下一步：是
- 下一步：
  - 做 Stage159 只读账户层 heat/survival 反事实：不改入场信号，基于 Stage156/157 日级结果模拟外层保证金热度上限、权益高水位保护、出金/锁盈或仓位冷却的影响。
  - 重点验证这种外层治理是否能降低 2021/2022/2024 起点的 broker10 压力和回撤差，同时尽量不破坏 C9 相对 C4 的收益/Sharpe 优势。

## 过拟合反思

- 运行前判断：否。只读 Stage157/156 固定输出，分析回撤窗口和账户状态，不改策略参数。
- 运行后判断：否。本阶段只给压力标签和窗口，不生成产品、日期、状态过滤规则。
- 原因：如果用 `2020-10-27`、`2021-12-31`、`lh/SH` 等局部样本做过滤，会明显过拟合；但把它们作为账户层压力诊断样本是合理的。

## 继续价值反思

- 运行前判断：是。Stage157 显示 C9 优势主要在后续路径，必须定位回撤差是否来自绝对亏损、峰值回吐或保证金压力。
- 运行后判断：是。Stage158 证明 stop/retry 本身不是主要风险源，后续更应看账户层治理；这延续了历史正式版从 Stage372 recovery/margin governance 到 C9 的原思路。
- 原因：当前目标不是完全复刻旧产物，而是恢复并延续有价值的正式路线。账户层治理更符合“穿越周期”，比继续扫 AI 池、品种、日期和 C9 参数更稳。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，等待 Stage159 账户层反事实后再合并摘要
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：暂不追加；若 Stage159 出现稳定账户层改进，再追加重要摘要
