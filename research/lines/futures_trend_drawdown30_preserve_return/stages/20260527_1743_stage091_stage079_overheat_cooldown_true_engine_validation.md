# Stage091：Stage079 暴涨冷却真实引擎验证

- 时间：2026-05-27 17:43 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 工作模式：`day`
- 阶段性质：固定规则真实引擎验证；承接 Stage090 的 PnL 层强诊断，检验其是否能在逐笔/逐日真实引擎中复现。
- 是否重要突破：否。重要反证：Stage090 最强 PnL 层形状不能直接晋级为真实可执行候选。
- 是否触发 A/B：是。A 为 Stage079，C 为两个 Stage090 冻结候选；未扫相邻阈值、金额或现金小数。

## 调研和判断

- 外部调研参考：动量/趋势策略在强上涨后出现尾部反转和 crash risk 的文献中，常见处理是 volatility scaling、crash indicator、动态风险预算；GitHub/vn.py 资料也支持必须用事件驱动回测验证真实成交、滑点、持仓变化。
- 本阶段判断：账户权益过热后冷却是有经济含义的方向，但 Stage090 是 PnL 层理想化缩放，必须在真实引擎中落地后再判断；不能因为诊断曲线好看就晋级。

参考：
- `Momentum has its moments` / Barroso-Santa Clara 类 volatility scaling 思路。
- NBER / momentum crash literature：动量策略收益伴随偶发左尾风险。
- vn.py CTA/Portfolio backtesting：真实引擎需要纳入持仓、滑点、成交路径。

## 版本变更

- 新增默认关闭的真实引擎钩子：`qmt_roll_portfolio_strategy.py`
  - `enable_portfolio_overheat_cooldown`
  - `portfolio_overheat_cooldown_near_high_drawdown_pct`
  - `portfolio_overheat_cooldown_hot20_threshold`
  - `portfolio_overheat_cooldown_hot60_threshold`
  - `portfolio_overheat_cooldown_brake_scale`
  - `portfolio_overheat_cooldown_recovery_drawdown_pct`
  - `portfolio_overheat_cooldown_recovery_ret20_threshold`
  - `portfolio_overheat_cooldown_recovery_scale`
  - `portfolio_overheat_cooldown_entry_contexts`
  - `enable_portfolio_overheat_cooldown_deleverage`
- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage391_stage079_overheat_cooldown_true_engine_validation.py`
- 输出：
  - `qmt_roll_stage391_stage079_overheat_cooldown_true_engine_validation_summary_stage391_stage079_overheat_cooldown_true_engine_validation_v1.csv`
  - `..._horizon_...csv`
  - `..._score_...csv`
  - `..._cost_stress_...csv`
  - `..._promotion_...csv`
  - `..._scale_history_...csv`
  - `..._report_...md`
  - `..._equity_drawdown_...png`

## 新增参数

- 冷却触发：历史账户权益回撤不深于 `5%`，且前20日权益收益 `>50%`；复杂版额外允许前60日权益收益 `>75%`。
- 冷却强度：真实引擎风险缩放 `0.80`，并允许对已有仓位真实减仓。
- 恢复触发：历史账户权益回撤 `>=15%` 且前20日收益转正。
- 恢复强度：真实引擎风险缩放 `1.10`。
- 验证版本：
  - `stage079`
  - `hot20_50_or60_75_brake100_recovery50_true_engine`
  - `hot20_50_brake100_recovery50_true_engine`
- 滑点压力：`1x/2x/3x/5x` 真实引擎复跑。

## 修改参数

- 无正式策略默认参数修改；所有新增钩子默认关闭。
- 本阶段只通过脚本 override 开启候选，不改变 Stage079/C3 默认行为。

## 删除参数

- 无。

## 主要结果

### 全周期账户口径

| 版本 | 总收益 | 最大回撤 | Sharpe | Ulcer | 252/504日滚动破30 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Stage079 | `4947.2602%` | `-29.7007%` | `1.3188` | `15.0874` | `0% / 0%` |
| hot20_or60真实引擎 | `2350.0423%` | `-36.9649%` | `1.1494` | `16.1662` | `4.3689% / 19.1925%` |
| hot20真实引擎 | `4843.4325%` | `-27.5860%` | `1.3124` | `14.2614` | `0% / 0%` |

### 3个月/6个月持有体验

| 版本 | 90日5%分位 | 90日中位 | 90日破20 | 180日5%分位 | 180日中位 | 180日破20 | 综合短持有分 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079 | `-11.4702%` | `13.5434%` | `18.5052%` | `-2.0393%` | `33.9947%` | `35.7109%` | `100.0000` |
| hot20_or60真实引擎 | `-15.5540%` | `10.1838%` | `14.3629%` | `-15.4708%` | `24.8240%` | `38.3388%` | `-81.3357` |
| hot20真实引擎 | `-13.4715%` | `12.5188%` | `12.4268%` | `0.1309%` | `32.0921%` | `36.7433%` | `134.1618` |

### 成本压力

| 版本 | 1x回撤 | 2x回撤 | 3x回撤 | 5x回撤 | 成本压力结论 |
| --- | ---: | ---: | ---: | ---: | --- |
| Stage079 | `-29.7007%` | `-35.7770%` | `-33.0393%` | `-41.1430%` | 基准 |
| hot20_or60真实引擎 | `-36.9649%` | `-30.6431%` | `-42.6085%` | `-48.3945%` | 1x/3x/5x 差于 Stage079 |
| hot20真实引擎 | `-27.5860%` | `-30.8589%` | `-31.6934%` | `-57.9774%` | 5x 差于 Stage079 |

### 触发摘要

- hot20真实引擎：冷却 `25` 天，恢复 `240` 天，真实减仓 `38` 次。
- hot20_or60真实引擎：冷却 `34` 天，恢复 `289` 天，真实减仓 `38` 次。

## 决策

- 决策：`no_promotion`
- `hot20_50_brake100_recovery50_true_engine` 的 6个月体验明显改善，短持有分 `134.1618`，但不满足硬约束：
  - 总收益低于 Stage079：`4843.4325% < 4947.2602%`
  - Sharpe 低于 Stage079：`1.3124 < 1.3182`
  - 5x 滑点压力回撤差于 Stage079：`-57.9774% < -41.1430%`
  - 3个月改善项仅 `3/8`，6个月改善项仅 `3/8`，未达每个周期至少 `5/8`。
- `hot20_50_or60_75_brake100_recovery50_true_engine` 直接失败，复杂热度条件在真实引擎里破坏收益与回撤。

## 归因判断

- Stage090 的强效果主要来自 PnL 层按日缩放，不需要真实平仓、换仓、再开仓，也没有真实滑点和整数手数路径冲击。
- 真实引擎中，冷却会造成实际减仓，恢复会在深回撤后频繁提高新仓风险，路径与理想日度缩放明显不同。
- 复杂 `hot20_or60` 版本触发更频繁，实际效果更差，说明线索存在明显路径敏感性。

## 过拟合反思

- 运行前：过拟合风险中等，因为 Stage090 规则来自坏窗口归因；但本阶段固定规则做真实引擎复验，没有继续扫阈值，属于反过拟合验证。
- 运行后：不把 Stage091 失败结果继续用相邻阈值救援。Stage090 降级为诊断线索，不能作为正式候选。

## 继续价值反思

- 继续有价值，但不在 `20日50%/60日75%/10万/5万` 这些小数上继续搜索。
- 下一步如果继续，只能做机制归因：拆分“真实减仓”“新仓缩放”“恢复加风险”三件事，判断失败来自成交路径成本还是过热状态变量本身。

## 后续规划 / TODO

- 固定阈值不变，做 Stage092 机制拆解：
  - 只缩放新开仓/加仓，不主动减已有仓位。
  - 只做冷却，不做恢复加风险。
  - 只作为归因，不作为参数扫描。
- 若机制拆解仍无法在不劣化收益/Sharpe/成本压力的前提下改善 3个月和6个月体验，则停止该过热冷却路线，转向低相关收益源或更外生的状态变量。

