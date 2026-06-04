# Stage337 lh 同日 monitor rerun gate

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 09:06 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：`lh.DCE` 官方月度源同日重复采集去重闸门
- 是否重要突破：否；source pipeline 防污染修正，不是策略晋级
- 是否触发A/B：否；没有策略版本进入正式候选、paper 或交易白名单

## 外部调研与判断

- 参考资料：
  - QuantConnect custom data / live reconciliation 与 look-ahead 约束：`https://www.quantconnect.com/docs/v2/writing-algorithms/live-trading/reconciliation`
  - FactSet point-in-time database 白皮书：`https://www.insight.factset.com/hubfs/Resources%20Section/White%20Papers/ID11996_point_in_time.pdf`
  - pyauth/tsp-client timestamp/hash attestation 参考实现：`https://github.com/pyauth/tsp-client`
- 我的判断：
  - PIT 数据的核心不是“抓了几行”，而是“在多少个真实可用时点形成了独立信息”。
  - Stage636 的 exact dedupe key 包含 `received_at_utc`，能处理完全重复行；但如果同一天重新抓取，`received_at_utc` 会变化，存在同一信息日被误当作新增样本的风险。
  - 因此 selector 样本深度必须基于 `product + source_url + pit_date` 的自然日去重，不能基于原始行数或 exact timestamp 行数。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage637_lh_same_day_monitor_rerun_gate.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 输入 fetch ledger：Stage635 `lh.DCE` 官方月度源 fetch ledger
  - 输入 master ledger：Stage636 `qmt_roll_lh_monthly_official_source_master_pit_ledger.csv`
  - exact dedupe key：`product_vt_symbol + source_url + received_at_utc + raw_sha256`
  - daily source key：`product_vt_symbol + source_url + pit_date`
  - daily hash key：`product_vt_symbol + source_url + pit_date + raw_sha256`
  - selector PIT 日期阈值：`20`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：本阶段不做收益回测；只模拟 Stage635 的 `2026-06-04` 同日重复采集
- 账户规模：不适用
- 成本口径：不适用
- 样本过滤：
  - rerun candidate 来自 Stage635 两条官方月度源记录
  - 保留原始 source/raw hash，只把 `received_at_utc` 改成 Stage637 当前运行时点
  - 要求同日同源候选不得追加 master 行
  - 要求同日同源候选不得计入 selector sample
- 策略/归因口径：
  - 不联网抓新数据
  - 不追加 master ledger
  - 不重放策略、不看收益、不改交易规则
  - 不生成 selector/paper/交易白名单、不连接 CTP

## 结果

- 期末权益：不适用；本阶段不是收益回测
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - decision：`lh_same_day_monitor_rerun_locked_selector_locked`
  - rerun candidate rows：`2`
  - strict daily append rows：`0`
  - same-day hold rows：`2`
  - selector sample rows：`0`
  - PIT dates before：`1`
  - PIT dates after strict rerun：`1`
  - required PIT dates for selector：`20`
  - promotion allowed：`false`
  - paper selector allowed：`false`
  - trading whitelist allowed：`false`
  - hard gates：`8/8`
  - classification：两条记录均为 `same_day_same_hash_hold`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage637_lh_same_day_monitor_rerun_gate_report_stage637_lh_same_day_monitor_rerun_gate_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage637_lh_same_day_monitor_rerun_gate_decision_stage637_lh_same_day_monitor_rerun_gate_v1.json`
- orders：不适用
- daily：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage637_lh_same_day_monitor_rerun_gate_rerun_candidate_stage637_lh_same_day_monitor_rerun_gate_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage637_lh_same_day_monitor_rerun_gate_classification_stage637_lh_same_day_monitor_rerun_gate_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage637_lh_same_day_monitor_rerun_gate_product_progress_stage637_lh_same_day_monitor_rerun_gate_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage637_lh_same_day_monitor_rerun_gate_gates_stage637_lh_same_day_monitor_rerun_gate_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage637_lh_same_day_monitor_rerun_gate_chart_stage637_lh_same_day_monitor_rerun_gate_v1.png`

## 图表视觉复盘

- 左上图：
  - rerun candidate 为 `2`，strict daily append 为 `0`，same-day hold 为 `2`，selector sample 为 `0`。
  - 这说明同日重复抓取被 hold，而不是被追加为新的 PIT 或 selector 样本。
- 右上图：
  - 当前 PIT dates 为 `1`，strict rerun 后仍为 `1`，红线为 selector 阈值 `20`。
  - 视觉结论很明确：同日重复运行不能推动 `1/20` 变成 `2/20`。
- 左下图：
  - exact duplicate 为 `0`，因为 `received_at_utc` 确实变化。
  - same-day source duplicate 和 same-day hash duplicate 都为 `2`，strict daily append allowed 为 `0`。
  - 这正好覆盖 Stage636 exact dedupe 剩余漏洞：不同 timestamp 的同日同源同 hash 行仍必须被锁住。
- 右下图：
  - hard gates 全绿，但绿色含义是 fail-closed 和去重纪律有效。
  - 这不是 `lh.DCE` 晋级信号；selector、paper、交易白名单仍为 `0`。

## 结论

- 本阶段结论：
  - Stage637 补上了 Stage636 exact dedupe 的剩余风险：同一天重新抓 MOA/NAHS，即使 `received_at_utc` 不同，也不能追加 master 行，不能增加 selector 样本，不能增加 PIT 日期。
  - `lh.DCE` 官方月度源 pipeline 现在具备“同日重复不膨胀”的闸门。
  - 当前仍只有 `1/20` 个 PIT 日期，不能做 selector、paper、A/B 或交易白名单。
- 是否进入下一步：继续，但只做未来新自然日 monitor 累计。
- 下一步：
  - 停止同日重复抓取作为“样本扩张”。
  - 后续真正有价值的是新自然日采集、raw hash 稳定性、字段 revision 记录、20 个 received_at 日期、12 个月跨度、独立 episode、预测力审计和真实 TCA。
  - 若未来同日同源但 raw hash 发生变化，应作为 revision hold 单独记录，不得自动进入 selector。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段完全没有使用收益、回撤、Sharpe 或品种表现排名。
  - 只审计数据源时点、去重键和 selector 样本计数规则。
  - 结果是更严格地锁住样本，而不是放宽交易或选择更多品种。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但价值边界很清楚。
- 原因：
  - 有价值的是保证扩池/选品路线的数据基础不被同日重复采集污染。
  - 继续重复同日跑没有新增信息价值；下一步必须等新自然日或补真实 TCA/事件 outcome。
  - 对“低单笔风险、扩大品种池、避免高相关风险”的主线来说，这一步是在建立选品前的数据资格闸门，不是选品本身。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage337 当前状态。
- 是否更新 `research/registry.md`：是，更新当前阶段摘要。
- 是否追加根目录 `memory.md/back_log.md`：否；本阶段不是正式候选、路线废弃、跨线合并或重大突破。
