# Stage425 连败严重度门控反证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-08 14:50 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：当前正式 Stage372/20万连败风控替代机制验证
- 是否重要突破：否，关键负结论
- 是否触发A/B：是，A/C 隔离验证

## 外部调研与判断

- 参考资料：
  - Van Tharp Institute position sizing calculator：强调按账户规模、止损距离和单笔风险百分比计算仓位，核心是控制每笔风险并用 risk unit/R-multiple 评估。
  - Headge position sizing 文章：说明固定 `1%` 风险下，连续亏损是常见事件，但风险单位决定亏损串对账户的真实伤害。
  - Trend following 风控资料：趋势策略通常用止损、风险预算和回撤控制维持生存，而不是只看入场信号。
- 我的判断：用“连续亏损段的累计亏损是否达到一个标准风险单位”来决定是否触发严重 `0.1` 降仓，有第一性原理依据；它不是按品种/年份补丁，也不是连败小数扫参。但如果实测表明绝大多数 `0.1` 已经对应实质亏损连败，就不能继续扫阈值救它。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage711_loss_streak_severity_gate_multiperiod.py`
- 修改脚本：无正式策略修改；仅新增 wrapper，并在回测期间 monkeypatch，运行结束恢复原方法。
- 删除脚本：无
- 新增参数：
  - `SEVERITY_MODE=stage711_loss_streak_severity_gate`
  - `SEVERITY_MIN_CUM_LOSS_RATIO=0.01`
  - `GATE_AUDIT` 审计计数
- 修改参数：
  - C 分支保持 `streak_risk_multipliers=1.0,1.0,1.0,0.1` 不变。
  - C 分支仅在连续亏损段累计已实现亏损达到当前权益/资金基数约 `1%` 时，才保留三连败后的严重 `0.1`；否则暂按 `1.0` 处理。
  - 通过 `streak_profit_recovery_mode=stage711_loss_streak_severity_gate` 作为候选哨兵启用，A 正式分支不启用。
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01-01` 至 `2026-04-30`
- 账户规模：`200,000`
- 成本口径：正常成本，并补 `2x/3x` 滑点压力
- 样本过滤：Stage707 同口径多起点与阶段独立启动窗口
- 策略/归因口径：
  - A：当前正式 Stage372/20万 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`
  - C：A + 连败严重度门控 `1%`，正式配置不变、不连接 CTP、不调用下单

## 结果

- 决策：`loss_streak_severity_gate_not_promoted`
- hard_fail_checks：`full_dd30_pass`、`cost2_full_dd40_pass`
- A 全周期：
  - 期末权益 `8,728,285`
  - 总收益 `4264.1425%`
  - 最大回撤 `-38.6713%`
  - Sharpe `1.6279`
  - 总滑点 `506,220`
  - 总交易次数 `633`
  - 胜率 `52.2586%`
- C 全周期：
  - 期末权益 `8,728,285`
  - 总收益 `4264.1425%`
  - 最大回撤 `-38.6713%`
  - Sharpe `1.6279`
  - 总滑点 `506,220`
  - 总交易次数 `633`
  - 胜率 `52.2586%`
- 多起点/分段：所有窗口 A/C 完全一致，收益保留均 `100%`，交易次数、回撤、Sharpe 全部无差异。
- 成本压力：全周期 C 的 `2x` 成本 DD 仍为 `-40.6555%`，与正式 A 完全一致，仍触发成本压力硬失败。
- 门控审计：
  - `severity_mode_calls=32,244`
  - `severe_tier_calls=11,260`
  - `severe_floor_kept_calls=11,254`
  - `mild_streak_bypass_calls=6`
  - `min_loss_to_threshold_ratio=0.3294`
  - `max_loss_to_threshold_ratio=20.3771`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage711_loss_streak_severity_gate_multiperiod_report_stage711_loss_streak_severity_gate_multiperiod_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage711_loss_streak_severity_gate_multiperiod_summary_stage711_loss_streak_severity_gate_multiperiod_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage711_loss_streak_severity_gate_multiperiod_comparison_stage711_loss_streak_severity_gate_multiperiod_v1.csv`
- checks：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage711_loss_streak_severity_gate_multiperiod_checks_stage711_loss_streak_severity_gate_multiperiod_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage711_loss_streak_severity_gate_multiperiod_decision_stage711_loss_streak_severity_gate_multiperiod_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage711_loss_streak_severity_gate_multiperiod_chart_stage711_loss_streak_severity_gate_multiperiod_v1.png`

## 结论

- 本阶段结论：不晋级，不接正式版。
- 关键原因：这个机制几乎没有改变真实路径。候选分支进入严重档 `11,260` 次，其中 `11,254` 次仍保留 `0.1`，只有 `6` 次绕过，且没有造成任何交易路径差异。
- 机制含义：当前正式版里的三连败 `0.1` 大多不是“三次小亏噪音”导致，而是连续亏损段累计亏损已经达到或超过一个常规风险单位。`0.1` 的粗糙问题仍存在，但不是用“亏损严重度 1% 门控”能解决的。
- 是否进入下一步：否。
- 下一步：不要继续扫 `0.5%/1.5%/2%` 阈值。若继续总目标，应从账户级 selector、外生风险源、或真正独立且事前有正期望的 risk slot/paper forward 入手。

## 过拟合反思

- 运行前判断：不是过拟合。候选用现有 `1%` 标准风险单位解释连败严重度，不按历史窗口、品种或小数收益优化。
- 运行后判断：继续扫阈值会过拟合。
- 原因：`1%` 门控几乎没有命中路径差异；如果为了制造差异去调阈值，就变成用历史交易分布反推 cutoff，而不是结构性风控。

## 继续价值反思

- 运行前判断：有价值，因为它验证“0.1 是否经常被小亏噪音触发”这个本质问题。
- 运行后判断：该形状无继续价值；总目标仍有价值。
- 原因：本阶段把“小亏连败误伤”基本排除为主因。更合理的方向不是继续修主账户 `0.1`，而是寻找能事前区分假突破质量/账户状态的 selector，或把新增机会放到非挤占式独立风险槽中积累 OOS。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage425 当前状态。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：是，记录关键负结论和后续禁止扫阈值。
