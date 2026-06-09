# Stage001 连败风险地板 0.5 A/C

- line_id：`futures_trend_loss_streak_risk_floor`
- 当前模式：`day`
- 记录时间：`2026-06-09 00:40 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：当前正式版 Stage372/20万风控参数 A/C 回测
- 是否重要突破：否；重要反证
- 是否触发A/B：是，按 `skills/version-ab-experiment/SKILL.md` 做 A/C；B 无独立意义

## 外部调研与判断

- 参考资料：
  - [Backtrader Sizers - Smart Staking](https://www.backtrader.com/blog/posts/2016-07-23-sizers-smart-staking/sizers-smart-staking/)：仓位 sizing 是独立于入场信号的资金管理层。
  - [Trend following](https://en.wikipedia.org/wiki/Trend_following)：趋势跟随里 money management / initial risk 对交易规模有决定作用。
  - [TurtleTrader Drawdown Recovery](https://www.turtletrader.com/recovery/)：回撤期降低 unit size 是典型防守思路。
- 我的判断：把正式版 `0.1` 地板改成 `0.5` 不是 alpha 改进，而是放松防守闸门。它必须证明能恢复右尾且不显著放大坏路径；本阶段结果显示它没有通过。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage742_loss_streak_risk_floor05_ac.py`
- 修改脚本：无策略默认参数修改；仅修正 Script742 entry stats 使用 `selected_volume>0` 识别实际开仓。
- 删除脚本：无
- 新增参数：`CANDIDATE_MULTIPLIERS="1.0,1.0,1.0,0.5"`
- 修改参数：仅回测运行期把 `streak_risk_multipliers` 从 `1.0,1.0,1.0,0.1` 改为 `1.0,1.0,1.0,0.5`
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`
- 账户规模：20万官方 Stage372/20万口径
- 成本口径：正常成本 + 2x/3x 滑点压力
- 样本过滤：11 个独立窗口，含全周期、`since_2021` 至 `since_2026`、`phase_2020_2021/2022_2023/2024_2025/2026_latest`
- 策略/归因口径：A 为当前正式 `official_live_stage372_20w_recovery_sleeve`；C 只改连败风险地板为 `0.5`；不改 AI、不改品种池、不改 maxpos、不改保证金强制减仓、不连接 CTP、不调用下单。

## 结果

- A 正式版期末权益：`8,728,285`
- A 总收益：`4264.1425%`
- A 最大回撤：`-38.6713%`
- A Sharpe：`1.6279`
- A 总滑点：`506,220`
- A 总交易次数：`633`
- A 胜率：`52.2586%`（非零日胜率）
- C 期末权益：`2,804,090`
- C 总收益：`1302.0450%`
- C 最大回撤：`-61.1653%`
- C Sharpe：`1.2083`
- C 总滑点：`263,330`
- C 总交易次数：`634`
- C 胜率：`52.3723%`（非零日胜率）
- C 相对 A：期末权益 `-5,924,195`，收益保留 `30.5347%`，最大回撤恶化 `-22.4940pp`，Sharpe 降低 `-0.4195`
- 成本压力：A 2x/3x DD 为 `-40.6555%/-42.7649%`；C 2x/3x DD 为 `-64.9580%/-69.0709%`
- 多起点：C 在 `since_2022/since_2023/since_2024/since_2025` 和 `phase_2022_2023/phase_2024_2025` 局部收益更高，但 `since_2021` 回撤恶化到 `-64.5738%`，`since_2026` 转负 `-4.1500%`，全周期失败。
- 开仓风险诊断：全周期 A 严重连败实际开仓 `65` 次，其中 `52` 次为 `0.1` 地板、`13` 次恢复为 full risk，严重连败实际风险 `620,957.4`；C 严重连败实际开仓同为 `65` 次，全部为 `0.5` 地板，严重连败实际风险 `1,547,987.4`，约为 A 的 `2.49` 倍。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage742_loss_streak_risk_floor05_ac_report_stage742_loss_streak_risk_floor05_ac_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage742_loss_streak_risk_floor05_ac_summary_stage742_loss_streak_risk_floor05_ac_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage742_loss_streak_risk_floor05_ac_cost_stress_stage742_loss_streak_risk_floor05_ac_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage742_loss_streak_risk_floor05_ac_curves_stage742_loss_streak_risk_floor05_ac_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage742_loss_streak_risk_floor05_ac_chart_stage742_loss_streak_risk_floor05_ac_v1.png`
- entry_risk：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage742_loss_streak_risk_floor05_ac_entry_risk_stage742_loss_streak_risk_floor05_ac_v1.csv`
- entry_stats：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage742_loss_streak_risk_floor05_ac_entry_risk_stats_stage742_loss_streak_risk_floor05_ac_v1.csv`

## 结论

- 本阶段结论：`loss_streak_floor05_not_promoted`
- 是否进入下一步：不进入正式候选；不建议直接把正式版 `0.1` 改成 `0.5`
- 下一步：若继续，只能做一个机制隔离验证：`0.5` 地板是否应同时调整 recovery sleeve 的触发上限；但这已是另一个参数联动实验，不能把本次失败版本救参为正式版。

## 过拟合反思

- 运行前判断：中等风险。`0.5` 是单点倍率，容易被近端局部窗口诱导。
- 运行后判断：继续扫倍率会过拟合。
- 原因：C 在 `since_2022`、`since_2023`、`phase_2024_2025` 局部改善，但全周期、`since_2021`、`since_2026`、2x/3x成本和回撤闸门全面失败；这不是稳定风控原则。

## 继续价值反思

- 运行前判断：有价值。它直接回答正式版 `0.1` 是否过保守。
- 运行后判断：本倍率地板方向继续价值低。
- 原因：`0.5` 不是轻微失败，而是把坏路径暴露显著放大；后续更有价值的是账户级 selector、新外生特征或 forward watch，而不是 `0.2/0.3/0.4/0.6` 扫参。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是，新增研究线
- 是否追加根目录 `memory.md/back_log.md`：是，正式风控候选被反证
