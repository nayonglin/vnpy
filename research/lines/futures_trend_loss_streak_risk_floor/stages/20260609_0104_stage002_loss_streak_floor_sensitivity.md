# Stage002 连败风险地板 0.2/0.3/0.4 敏感性审计

- line_id：`futures_trend_loss_streak_risk_floor`
- 当前模式：`day`
- 记录时间：2026-06-09 01:04 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：正式 Stage372/20万连败风险地板敏感性 A/C 审计
- 是否重要突破：是，路线级反证，确认不应继续用 `0.2/0.3/0.4/0.5` 这类小数地板救参
- 是否触发A/B：是，已按 `skills/version-ab-experiment/SKILL.md` 做隔离 A/C；本阶段不改正式配置

## 外部调研与判断

- 参考资料：
  - Backtrader sizer / smart staking：`https://www.backtrader.com/blog/posts/2016-07-23-sizers-smart-staking/sizers-smart-staking/`
  - Trend following：`https://en.wikipedia.org/wiki/Trend_following`
  - TurtleTrader drawdown recovery：`https://www.turtletrader.com/recovery/`
- 我的判断：
  - 连败后的 `risk floor` 本质是资金管理层的生存闸门，不是 alpha 过滤器。
  - 放宽风险地板必须同时通过全周期收益、最大回撤、成本压力和多起点验证；不能只看 `since_2022` 或 `phase_2024_2025` 的局部改善。
  - Stage001 已反证 `0.5`，本阶段应作为敏感性边界验证，而不是救参数扫描。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage743_loss_streak_risk_floor_sensitivity.py`
- 修改脚本：无正式策略修改；脚本运行中修正曲线绘图日期归一化，避免 mixed date type 报错
- 删除脚本：无
- 新增参数：
  - `LOSS_STREAK_FLOORS=(0.2, 0.3, 0.4)`
  - 候选 profile：
    - `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_lossfloor02_stage743`
    - `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_lossfloor03_stage743`
    - `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_lossfloor04_stage743`
- 修改参数：
  - A：正式 `streak_risk_multipliers=1.0,1.0,1.0,0.1`
  - C：仅分别改为 `1.0,1.0,1.0,0.2`、`1.0,1.0,1.0,0.3`、`1.0,1.0,1.0,0.4`
- 删除参数：无

## 回测/归因参数

- 数据区间：全周期 `2020` 至 `2026-04-30`，并包含 `since_2021` 至 `since_2026`、`phase_2020_2021/2022_2023/2024_2025/2026_latest`
- 账户规模：20万
- 成本口径：正常成本，并做 `2x/3x` 滑点成本压力
- 样本过滤：不重新训练 AI，不改变 AI 池，不改变品种池，不改变 `maxpos4`，不改变 recovery sleeve，不连接 CTP，不调用下单
- 策略/归因口径：以当前官方实盘 `official_live_stage372_20w_recovery_sleeve` 为 A；候选只改变连败严重档风险地板

## 结果

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A 正式 `0.1` | `8,728,285` | `4264.1425%` | `-38.6713%` | `1.6279` | `506,220` | `633` | `52.2586%` |
| C `0.2` | `5,464,445` | `2632.2225%` | `-46.6202%` | `1.4605` | `373,940` | `624` | `52.4887%` |
| C `0.3` | `4,220,145` | `2010.0725%` | `-51.6497%` | `1.3613` | `339,730` | `634` | `52.6553%` |
| C `0.4` | `2,558,700` | `1179.3500%` | `-57.3563%` | `1.2098` | `257,430` | `630` | `51.7972%` |

- 其他关键指标：
  - `0.2` 全周期相对 A 少 `3,263,840`，收益保留 `61.7292%`，最大回撤恶化 `7.9489pp`；`2x/3x` 成本 DD 为 `-49.5669%/-52.7446%`。
  - `0.3` 全周期相对 A 少 `4,508,140`，收益保留 `47.1390%`，最大回撤恶化 `12.9783pp`；`2x/3x` 成本 DD 为 `-54.9075%/-58.4314%`。
  - `0.4` 全周期相对 A 少 `6,169,585`，收益保留 `27.6574%`，最大回撤恶化 `18.6850pp`；`2x/3x` 成本 DD 为 `-60.9103%/-64.7613%`。
  - 局部窗口：`0.4` 在 `since_2022/since_2023/phase_2024_2025` 有改善，但全周期和 `since_2021` 生存线失败；这是典型局部窗口诱导，不足以改正式版。
  - 机制诊断：正式 A 全周期严重连败开仓 `65` 行，`recovery_applied_rows=13`；`0.2/0.3/0.4` 的 `recovery_applied_rows=0`，同时把严重连败实际风险分别提高到约 `1,135,990/1,385,142/1,467,448`。换句话说，小数地板不是稳定释放右尾，而是放大普通连败坏路径，并破坏原本 `0.1 + recovery_sleeve` 的结构。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage743_loss_streak_risk_floor_sensitivity_report_stage743_loss_streak_risk_floor_sensitivity_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage743_loss_streak_risk_floor_sensitivity_summary_stage743_loss_streak_risk_floor_sensitivity_v1.csv`
- orders：无订单文件；本阶段不下单
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage743_loss_streak_risk_floor_sensitivity_curves_stage743_loss_streak_risk_floor_sensitivity_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage743_loss_streak_risk_floor_sensitivity_checks_stage743_loss_streak_risk_floor_sensitivity_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage743_loss_streak_risk_floor_sensitivity_chart_stage743_loss_streak_risk_floor_sensitivity_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage743_loss_streak_risk_floor_sensitivity_decision_stage743_loss_streak_risk_floor_sensitivity_v1.json`

## 结论

- 本阶段结论：`0.2/0.3/0.4` 全部不晋级；结合 Stage001 的 `0.5`，正式版不应把连败风险地板从 `0.1` 放宽成固定小数地板。
- 是否进入下一步：不沿固定小数风险地板继续。
- 下一步：
  - 保持正式版 `1.0,1.0,1.0,0.1 + recovery_sleeve`。
  - 若继续研究，只能转向 recovery sleeve 触发结构隔离、账户级 selector、外生特征或 forward watch；不再扫 `0.15/0.25/0.35/0.45/0.6`。

## 过拟合反思

- 运行前判断：有中等过拟合风险。用户要求扫 `0.2/0.3/0.4`，容易被刚看到的 `0.5` 局部窗口结果牵引。
- 运行后判断：继续沿倍率小数扫描就是过拟合。
- 原因：全周期 A 仍最强；候选只在部分近端/阶段窗口表现更好，但破坏 `2020-2021/2021起点` 的复利底座和成本压力。选择其中某个小数，本质是在历史窗口上找局部平衡点，不是发现新特征。

## 继续价值反思

- 运行前判断：有价值，因为它能回答 `0.5` 失败是否只是太大，还是整条固定地板路线有问题。
- 运行后判断：固定地板路线没有继续价值。
- 原因：`0.2` 已经是三档里最不差，但仍显著低于正式版且 DD40 失败；更高地板只是在局部窗口释放风险，无法穿越全周期。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新为 Stage002 已完成且固定小数地板路线停止。
- 是否更新 `research/registry.md`：是，路线级结论更新。
- 是否追加根目录 `memory.md/back_log.md`：是，属于重要路线废弃/停止扫参结论。
