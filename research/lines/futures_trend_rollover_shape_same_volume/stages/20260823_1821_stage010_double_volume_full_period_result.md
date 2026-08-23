# Stage010 30日方向与成交量翻倍联合加风险全周期结果

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：A/B 最小全周期真引擎验证；已停止
- 记录时间：2026-08-23 18:21 CST
- 工作区/分支：`.worktrees/rollover-shape-same-volume` / `codex/rollover-shape-same-volume`
- 冻结提交：`7492d06ac`（18:10:53 CST）
- 结果时间：2026-08-23 18:14:59 CST
- 阶段性质：Stage008 失败后的单点量能阈值反证
- 是否重要突破：否
- 是否触发A/B：是
- 最终决策：`stop_double_volume_boost_after_full_period`

## 外部调研与判断

- CME 支持把成交量作为市场参与度、流动性和换月迁移的辅助信息，但成交量本身不能识别买卖方向：<https://www.cmegroup.com/education/courses/introduction-to-futures/what-is-volume>
- Lee 与 Swaminathan 支持价格动量与历史成交量存在交互，但没有为 `2.0` 阈值提供直接理论依据：<https://papers.ssrn.com/sol3/papers.cfm?abstract_id=92589>
- 我的判断：H 的 `12.7371%` 诊断增强覆盖证明量能翻倍条件具有选择性；但选择性不等于可晋级，必须同时满足预声明风险门。

## 本次版本变更

- 新增参数：`directional_30d_volume_ratio_threshold=1.0`，默认维持 F 的严格 `recent > prior` 行为。
- H 实验参数：`directional_30d_volume_ratio_threshold=2.0`；30日价格方向同向且 `T-9..T` 成交量严格大于 `T-19..T-10` 的两倍时，风险金额乘 `1.2`。
- 修改参数：无正式参数修改；只在 H 实验臂覆盖阈值为 `2.0`。
- 删除参数：无。
- 新增脚本：`tools/stage010_directional_double_volume_full_period_acfh.py`。
- 新增测试：`tests/test_rollover_shape_stage010_runner.py`，并扩展策略聚焦测试。
- 新增回测结果：A/C/F/H summary、comparison、curve、H entry risk、trades、trade events、volume contract、decision。
- 修改/删除回测结果：无；Stage008 产物保持原样。
- 正式配置、正式物料、master、production、CTP、订单接口均未修改；订单/撤单 API `0/0`。

## 回测参数

- 数据区间：`2018-01-01 -> 2026-05-29`。
- 账户规模：`150,000`。
- 成本、保证金、品种、信号、换月和硬风控：继承 Stage008。
- A：当前正式 C9/15万。
- C：A + 换月连续历史形态续仓。
- F：C + 30日同向且最近10日量能大于前10日时风险 `×1.2`。
- H：C + 30日同向且最近10日量能严格大于前10日两倍时风险 `×1.2`。

## 全周期结果

| 臂 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | broker10峰值 | 超100%天数 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 13,071,214.10 | 8614.1427% | -56.2069% | 1.362230 | 1,525,590 | 808 | 52.5841% | 91.4950% | 0 |
| C | 13,338,365.80 | 8792.2439% | -56.9876% | 1.362669 | 1,517,200 | 825 | 52.6812% | 100.4112% | 1 |
| F | 16,361,436.10 | 10807.6241% | -61.9911% | 1.389323 | 2,053,480 | 829 | 52.9151% | 102.5885% | 2 |
| H | 15,553,660.10 | 10269.1067% | -60.3470% | 1.410168 | 1,701,240 | 823 | 52.2312% | 95.2240% | 0 |

## 对照与闸门

- H 相对 A：收益 `+1654.9640pp`、Sharpe `+0.047938`，但最大回撤恶化 `4.1400pp`，滑点为 A 的 `111.5136%`，broker10 峰值恶化 `3.7291pp`；回撤、成本、broker 三门失败。
- H 相对 C：收益 `+1476.8629pp`、Sharpe `+0.047499`，broker10 峰值改善 `5.1871pp` 且超100%天数从 `1` 降为 `0`；但最大回撤恶化 `3.3593pp`，滑点为 C 的 `112.1302%`；回撤、成本两门失败。
- H 相对 F：收益少 `538.5173pp`，但最大回撤改善 `1.6441pp`、Sharpe提高 `0.020845`、滑点降至 F 的 `82.8467%`、broker10峰值改善 `7.3645pp`；说明提高阈值有防守作用，但仍没有恢复到 A/C 可接受风险边界。
- A_vs_H 和 C_vs_H 均未通过预声明全周期门，`escalate_to_multicycle=false`。

## 规则与真实成交合同

- H 诊断 `375` 条：30日价格方向同向 `369`、成交量翻倍增强 `47`、量能门抑制 `322`、方向反向 `6`；增强覆盖 `47/369=12.7371%`。
- 方向：多头 `39/301` 增强，空头 `8/74` 增强。
- 上下文：普通开仓 `47/352` 增强，换月重开 `0/23` 增强；本样本没有量能翻倍换月重开。
- 全部诊断的阈值、严格大于关系、`applied` 和风险金额 `×1.2/×1.0` 合同逐行通过。
- H 共 `403` 个 OPEN，其中 `30` 个为 C9 日内 retry，真实初始 OPEN `373`；按合约+方向时序确定性配对 `373` 条，`2` 条诊断未成交，实际增强 `47/373=12.6005%`，全部47条诊断增强均真实成交。
- 当前产物分别保存诊断与 trades/events，但没有另存这份逐笔匹配表；这是非阻断溯源边界，不影响本次停止判定。

## 身份与验证

- A/C/F 的全周期全部关键指标及各 `2,037` 行资金曲线与 Stage008 对应臂逐值完全一致。
- 聚焦测试：本地主流程 `35 tests passed`；独立 reviewer 扩展验证 `53 tests + 13 subtests passed`。
- `py_compile`、`git diff --check` 通过。
- 独立 reviewer：核心实现、产物、合同和停止决策未发现 P0/P1；最终 P2 仅为未持久化诊断到真实初始 OPEN 的逐笔 join。

## 输出文件

- summary：`artifacts/stage010/stage010_acfh_summary.csv`
- comparison：`artifacts/stage010/stage010_acfh_comparison.csv`
- daily curves：`artifacts/stage010/stage010_acfh_curve.csv`
- H diagnostics：`stage010_full_h_entry_risk.csv`
- H trades/events：`stage010_full_h_trades.csv`、`stage010_full_h_trade_events.csv`
- contract：`stage010_full_h_volume_contract_summary.csv`
- decision：`artifacts/stage010/stage010_decision.json`

## 结论

- 本阶段结论：H 的量能翻倍门确有选择性，且比 F 更防守；但相对正式 A 和换月 C，回撤分别恶化 `4.1400pp/3.3593pp`，滑点分别升至 `111.5136%/112.1302%`，未达到晋级风险边界。
- 是否进入下一步：否；按冻结合同不运行多周期、不生成多周期五图、不晋升、不发布正式物料。
- 下一步：停止这条历史阈值优化；不扫描其他量能倍数、窗口、风险倍率、品种、方向、年份或起点。

## 过拟合反思

- 运行前判断：是，中高风险；`2.0` 是看到 F 失败后提出的后验阈值。
- 运行后判断：本次单点冻结验证没有结果内扫参；若继续根据 H 的高收益或更高 Sharpe 扫阈值救回撤/成本，就是过拟合。
- 原因：同一底层30日趋势信息仍在放大风险，量能筛选虽更窄，却没有让风险代价回到 A/C 门内。

## 继续价值反思

- 运行前判断：有，限于一次最小全周期验证。
- 运行后判断：该固定 H 没有继续跑多周期或历史优化价值；保留为失败证据有价值。
- 原因：预声明的两个核心晋级对照都失败，新增滚动窗口不会改变完整周期已暴露的成本和回撤机制。

## 合入建议

- 更新本线 `LINE.md`：是。
- 更新 `research/registry.md`：否，研究线状态不变。
- 追加根目录 `memory.md/back_log.md`：是，属于一条历史阈值路线的明确关闭。
