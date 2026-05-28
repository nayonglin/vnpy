# Stage088 Stage079结构性短持有体验候选门禁

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-27 17:14 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage079 短持有体验优化的结构候选诊断；不修改 C3、78-1 或震荡策略代码。
- 是否重要突破：否，形成一条反证和一个弱线索。
- 是否触发A/B：是，沿用 Stage087 的 Stage079 baseline vs 结构候选门禁。

## 外部调研与判断

- 参考资料：
  - `Trend Following: Equity and Bond Crisis Alpha`：趋势策略的组合价值来自分散和危机/尾部互补，但仍需承认路径性回撤。
  - `finmarketpy` / `backtesting.py` 等开源回测工具与 QuantStats/PerformanceAnalytics 评价习惯都强调滚动收益、回撤、Ulcer、成本压力和多窗口检查。
  - trend following + volatility/risk targeting 文献给出的共同经验是：短持有体验不能靠事后单窗口补丁，必须用低相关收益源或低自由度风险预算。
- 我的判断：
  - Stage087 已反证现金收益、股票整手账户和创新高加仓；本阶段只允许测试结构更清晰的三类：真实震荡卫星、深回撤恢复再风险、下跌刹车+恢复再风险。
  - 这些候选都只使用前一日 C3 权益回撤和20日权益变化，不用未来收益；但 PnL 层再风险/刹车仍只能算诊断，不能直接晋级实盘。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage388_stage079_structural_short_holding_candidates.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `recovery_confirmed`：前一日 C3 回撤不浅于 `-15%` 且20日权益变化为正。
  - `falling_drawdown`：前一日 C3 回撤不浅于 `-10%` 且20日权益变化为负。
  - 备用风险预算诊断档位：`2.5万 / 5万`。
  - 下跌刹车诊断档位：`2.5万 / 5万`。
  - 真实震荡卫星：Stage324 `10万` 独立震荡账户。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2020-01-01` 至 `2026-04-30`。
- 账户规模：统一 `61.5万`，即 `50万 C3 + 11.5万缓冲/承载资金`。
- 成本口径：
  - C3 正常成本沿用 Stage383/Stage336 日度 PnL 与滑点。
  - C3 滑点压力 `1x/2x/3x/5x`，候选不能比 Stage079 更差。
  - 震荡卫星沿用 Stage324 独立 `10万` 日权益，已含其原始回测成本；本阶段不额外放大震荡腿滑点。
- 样本过滤：无。
- 策略/归因口径：
  - Stage079 基准。
  - `range100_cash15`：`50万C3 + 10万真实震荡卫星 + 1.5万现金`。
  - `recovery_rerisk_25k/50k`：深回撤恢复确认后增加 C3 PnL 层风险预算。
  - `storm_brake25/50_recovery50`：下跌段降低风险，恢复确认后再风险。
  - `range100_cash0_recovery15`：`10万震荡卫星 + 1.5万恢复再风险`。

## 结果

- Stage079 基准：
  - 期末权益：`31,040,650`
  - 总收益：`4947.2602%`
  - 最大回撤：`-29.7007%`
  - Sharpe：`1.3182`
  - Ulcer：`15.0931`
  - 252/504日滚动破30回撤率：`0% / 0%`
- 唯一真实可晋级非诊断项 `range100_cash15`：
  - 期末权益：`31,043,850`
  - 总收益：`4947.7805%`
  - 最大回撤：`-29.6880%`
  - Sharpe：`1.3182`
  - Ulcer：`15.0900`
  - 硬约束：通过
  - 3个月体验分：`100.0115`
  - 6个月体验分：`100.3817`
  - 综合短持有体验分：`100.2151`
  - 结论：改善几乎为零，不能晋级。
- 最强诊断项 `storm_brake50_recovery50`：
  - 总收益：`4935.5611%`，低于 Stage079，硬约束失败。
  - 最大回撤：`-29.1344%`
  - Sharpe：`1.3126`，低于 Stage079，硬约束失败。
  - 3个月体验分：`103.4671`
  - 6个月体验分：`119.0772`
  - 综合短持有体验分：`112.0527`
  - 结论：能改善回撤和6个月，但用收益/Sharpe换体验，不符合目标。
- 最强硬指标诊断项 `recovery_rerisk_50k`：
  - 总收益：`4998.7954%`
  - 最大回撤：`-29.5503%`
  - Sharpe：`1.3188`
  - Ulcer：`14.9749`
  - 3个月体验分：`100.0742`
  - 6个月体验分：`120.1849`
  - 综合短持有体验分：`111.1351`
  - 结论：6个月改善明显，但3个月基本没改善，且仍是 PnL 层诊断，不能晋级。
- 晋级候选数：`0`。
- 总滑点：C3 基准沿用 `1,556,750`；诊断项滑点压力按 C3 delta 同步放大/缩小估算。
- 总交易次数：C3 基准 `757`；震荡卫星候选额外沿用 Stage324 震荡账户 `72` 次，组合仅用于审计不改变入口。
- 胜率：C3 基准 `45.3826%`；震荡卫星账户胜率约 `47.2222%`，组合层不重新定义单一胜率。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage388_stage079_structural_short_holding_candidates_report_stage388_stage079_structural_short_holding_candidates_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage388_stage079_structural_short_holding_candidates_summary_stage388_stage079_structural_short_holding_candidates_v1.csv`
- horizon：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage388_stage079_structural_short_holding_candidates_horizon_stage388_stage079_structural_short_holding_candidates_v1.csv`
- constraints：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage388_stage079_structural_short_holding_candidates_constraints_stage388_stage079_structural_short_holding_candidates_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage388_stage079_structural_short_holding_candidates_cost_stress_stage388_stage079_structural_short_holding_candidates_v1.csv`
- score：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage388_stage079_structural_short_holding_candidates_score_stage388_stage079_structural_short_holding_candidates_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage388_stage079_structural_short_holding_candidates_decision_stage388_stage079_structural_short_holding_candidates_v1.json`

## 结论

- 本阶段结论：`no_candidate_promoted_stage079_remains_baseline`
- 是否进入下一步：不把本阶段任一候选提升为正式候选。
- 下一步：
  - 不继续救 `10万震荡卫星+现金`，因为真实改善只有 `0.2151` 分。
  - 不继续救 `下跌刹车+恢复再风险` 的金额，因为它已经显示改善来自牺牲长期收益和 Sharpe。
  - 若继续推进，只能找更强低相关承载，或寻找真正外生、低自由度、能提前识别短期坏窗口的状态变量。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：本阶段不是过拟合，但继续在这些结构的金额上细调会过拟合。
- 原因：
  - 本阶段候选是少数粗结构，不是为 3个月/6个月目标扫小数。
  - 所有候选使用同一硬约束、成本压力和 Stage087 评分器。
  - 结果显示 3个月体验最难改善；刹车能改善左尾但很快牺牲收益和 Sharpe。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：当前 Stage079 目标仍有继续价值，但本阶段这批结构继续价值低。
- 原因：
  - Stage088 明确区分了两件事：恢复再风险能改善6个月，但不解决3个月；下跌刹车能改善3个月部分回撤，但会损伤长期收益和 Sharpe。
  - 因此继续方向不应是金额微调，而应换信息源或承载源。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage088 反证和后续禁区。
- 是否更新 `research/registry.md`：否，本阶段不是正式候选或跨线里程碑。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`，作为短持有优化路线反证摘要。
