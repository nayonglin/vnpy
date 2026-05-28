# Stage087 Stage079短持有体验优化候选门禁

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-27 17:00 CST
- 阶段性质：首批候选筛查与统一评分器；目标是在不劣化 Stage079 核心指标的前提下改善 3个月/6个月持有体验
- 是否重要突破：否。建立了可复用门禁，但首批候选没有晋级。
- 是否触发A/B：是，按 `skills/version-ab-experiment/SKILL.md` 处理。候选可能进入 Stage079 组合/部署层，因此使用 A/C 门禁；本阶段没有候选通过晋级。

## 外部调研与判断

- 参考方向：趋势策略短持有体验改善通常来自低相关收益源、波动/风险预算、组合相关性管理、rolling/walk-forward 验证。
- 判断：不能围绕 3个月/6个月结果扫小数；候选必须是低自由度、可解释、可复验的结构变化。
- 本阶段优先测试两个低过拟合方向：
  - 不增加 `61.5万` 总资金，把 Stage079 的部分现金备用资金替换为已冻结、已做真实整手复核的股票账户曲线。
  - 只做诊断的 C3 创新高后备用风险预算，验证“顺势加风险”是否可能改善短持有体验。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage387_stage079_short_holding_candidates.py`
- 修改策略脚本：无。
- 新增参数：
  - 基准：`Stage079 = 50万C3下单 + 11.5万现金`
  - 候选资金：`2.5万/5万/10万` 真实股票整手账户 + 剩余现金
  - 保守现金收益探针：年化 `2%`
  - 诊断项：`11.5万` 按30万股票账户净值线性缩放；`2.5万` C3创新高后备用风险预算
  - 3个月/6个月体验评分权重：5%分位收益 `25%`，正收益率 `20%`，年化低于5%概率 `15%`，破20回撤率 `20%`，Ulcer P95 `10%`，P95最长水下 `10%`
- 修改参数：无。
- 删除参数：无。

## 输出文件

- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage387_stage079_short_holding_candidates_summary_stage387_stage079_short_holding_candidates_v1.csv`
- horizon：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage387_stage079_short_holding_candidates_horizon_stage387_stage079_short_holding_candidates_v1.csv`
- constraints：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage387_stage079_short_holding_candidates_constraints_stage387_stage079_short_holding_candidates_v1.csv`
- score：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage387_stage079_short_holding_candidates_score_stage387_stage079_short_holding_candidates_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage387_stage079_short_holding_candidates_decision_stage387_stage079_short_holding_candidates_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage387_stage079_short_holding_candidates_report_stage387_stage079_short_holding_candidates_v1.md`

## 基准

- Stage079 期末权益：`31,040,650`
- Stage079 总收益：`4947.2602%`
- Stage079 最大回撤：`-29.7007%`
- Stage079 Sharpe：`1.3182`
- Stage079 Ulcer：`15.0931`
- Stage079 总滑点：沿用 C3 `1,556,750`
- Stage079 总交易次数：沿用 C3 `757`
- Stage079 胜率：沿用 C3 `45.3826%`

## 首批候选结果

| 候选 | 全周期收益 | 最大回撤 | Sharpe | Ulcer | 短持有体验分 | 硬约束 | 晋级 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `Stage079` | `4947.2602%` | `-29.7007%` | `1.3182` | `15.0931` | `100.0000` | 通过 | 否，基准 |
| `现金年化2%` | `4949.7580%` | `-29.6456%` | `1.3200` | `15.0483` | `101.6558` | 通过 | 否 |
| `2.5万股票整手+9万现金` | `4947.4780%` | `-29.6889%` | `1.3187` | `15.0739` | `100.7980` | 通过 | 否 |
| `5万股票整手+6.5万现金年化2%` | `4950.7599%` | `-29.5944%` | `1.3222` | `14.9913` | `103.0572` | 通过 | 否 |
| `10万股票整手+1.5万现金年化2%` | `4955.8766%` | `-29.5057%` | `1.3261` | `14.9107` | `105.6214` | 通过 | 否 |
| `11.5万股票线性缩放诊断` | `4959.8436%` | `-29.4634%` | `1.3240` | `14.9109` | `108.7172` | 不通过：诊断项 | 否 |
| `C3创新高后2.5万备用风险预算诊断` | `4979.0148%` | `-30.0078%` | `1.3160` | `15.2374` | `98.5426` | 不通过 | 否 |

## 3个月/6个月关键观察

- 最佳真实候选 `10万股票整手+1.5万现金年化2%`：
  - 3个月：5%分位收益从 `-11.4702%` 改到 `-11.0092%`，正收益率从 `73.4473%` 到 `73.6724%`，破20回撤率从 `18.4968%` 到 `18.2718%`。
  - 6个月：5%分位收益从 `-2.0884%` 改到 `-1.7951%`，正收益率从 `93.4334%` 到 `93.4803%`，但6个月中位收益从 `33.9211%` 降到 `33.4068%`。
  - 结论：改善太小，且6个月中位收益劣化，不能晋级。
- `11.5万股票线性缩放诊断` 分数最高，但它忽略真实整手约束，不允许作为正式候选。
- `C3创新高后备用风险预算` 增加收益但打穿 `-30%`，且 Sharpe/Ulcer 劣化，直接废弃。

## 决策

- 晋级候选数：`0`
- 决策：`no_candidate_promoted_stage079_remains_baseline`
- 当前 Stage079 仍是基准，不替换、不升级新版本。

## 过拟合与继续价值反思

- 运行前判断：不是过拟合。候选来自既有冻结股票账户、现金管理和预声明诊断项，没有因目标窗口临时调参数。
- 运行后判断：不是过拟合。没有候选晋级，失败后不继续调股票资金小数、现金收益率或创新高加仓金额。
- 运行前判断：有价值。Stage079 已解决长期回撤，下一阶段必须量化短持有体验改善门槛。
- 运行后判断：有价值。首批候选反证了“简单把备用现金换成已有股票腿/现金收益”只能小幅改善，不足以满足目标；下一步需要更强低相关收益源或更本质的风险预算结构。

## 后续规划和 TODO

- 不继续救 `2.5万/5万/10万/11.5万` 股票资金小数。
- 不继续救现金年化收益率假设。
- 不继续救 C3 创新高后小额加仓形状。
- 下一步优先研究：
  - 更强且小资金可承载的低相关收益源；
  - 不破坏利润腿的低自由度风险预算结构；
  - C3 弱窗口中能提前识别且全样本不伤收益的外生状态变量。
