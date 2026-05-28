# Stage092 Stage079暴涨冷却机制拆解

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-05-27 17:51 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：机制拆解；拆分 Stage091 中的“新仓/加仓缩放、已有仓位减仓、恢复加风险”三类效果。
- 是否重要突破：否。重要反证：暴涨冷却真实引擎版本没有正常成本晋级候选。
- 是否触发A/B：是。A 为 Stage079，C 为四个固定机制拆解版本。

## 外部调研与判断

- 参考资料：
  - Man Institute 关于 trend following 在危机和不同市场状态中的表现讨论。
  - backtesting.py / finmarketpy 等开源回测工具对多周期、滚动窗口和风险指标的常见实践。
- 我的判断：
  - 文献和工具实践支持“趋势暴涨后降风险/波动缩放”作为低自由度风险管理假设，但必须经过真实交易引擎验证。
  - 本阶段不是继续调参，而是拆解 Stage091 的失败来源；若拆解后仍无候选，暴涨冷却路线应停止，避免围绕坏窗口做过拟合救援。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage392_stage079_overheat_cooldown_mechanism_ablation.py`
- 修改脚本：无正式策略默认修改；继续使用 Stage091 已加入且默认关闭的真实引擎过热冷却钩子。
- 删除脚本：无。
- 新增参数：
  - `hot20_full_deleverage_recovery`：新仓/加仓缩放 + 已有仓位减仓 + 恢复加风险。
  - `hot20_entry_recovery_no_deleverage`：仅新仓/加仓缩放 + 恢复加风险。
  - `hot20_deleverage_brake_only`：新仓/加仓缩放 + 已有仓位减仓，不恢复加风险。
  - `hot20_entry_brake_only`：仅新仓/加仓缩放，不恢复加风险。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage079/Stage091 可比全周期日线回放。
- 账户规模：Stage079 口径，`50万C3下单 + 11.5万外部现金`。
- 成本口径：正常成本；机制拆解阶段若无正常成本候选，不进入成本压力复跑。
- 样本过滤：无新增过滤。
- 策略/归因口径：真实引擎逐日回放，新增钩子默认关闭，仅在指定 profile 中开启。

## 结果

- 基准 Stage079：
  - 期末权益：`31,040,650`
  - 总收益：`4947.2602%`
  - 最大回撤：`-29.7007%`
  - Sharpe：`1.3188`
  - Ulcer：`15.0874`
  - 总滑点：`1,556,750`
  - 总交易次数：`757`
  - 胜率：`45.3826%`
- `hot20_full_deleverage_recovery`：
  - 总收益：`4843.4325%`
  - 最大回撤：`-27.5860%`
  - Sharpe：`1.3124`
  - Ulcer：`14.2614`
  - 总滑点：`1,504,050`
  - 总交易次数：`798`
  - 胜率：`49.5215%`
  - 3个月体验分：`106.8695`
  - 6个月体验分：`156.4918`
  - 综合短持有体验分：`134.1618`
  - 失败项：总收益低于 Stage079、Sharpe 低于 Stage079、3个月分未达到 +10%。
- `hot20_entry_brake_only`：
  - 总收益：`4936.1577%`
  - 最大回撤：`-29.4649%`
  - Sharpe：`1.3010`
  - Ulcer：`14.9499`
  - 3个月体验分：`104.3562`
  - 6个月体验分：`124.3826`
  - 综合短持有体验分：`115.3707`
  - 失败项：总收益低于 Stage079、Sharpe 低于 Stage079、3个月分未达到 +10%。
- `hot20_deleverage_brake_only`：
  - 总收益：`4870.9309%`
  - 最大回撤：`-28.1673%`
  - Sharpe：`1.3247`
  - Ulcer：`14.4498`
  - 3个月体验分：`96.0050`
  - 6个月体验分：`97.6478`
  - 综合短持有体验分：`96.9085`
  - 失败项：总收益低于 Stage079，且3个月/6个月体验分均未达到 +10%。
- `hot20_entry_recovery_no_deleverage`：
  - 总收益：`3098.5203%`
  - 最大回撤：`-30.8751%`
  - Sharpe：`1.1751`
  - Ulcer：`16.2017`
  - 252/504日滚动破30回撤率：`2.5243% / 16.8142%`
  - 综合短持有体验分：`44.4571`
  - 失败项：收益、回撤、Sharpe、Ulcer、滚动破30和短持有体验全部不合格。

## 3个月/6个月持有体验

- Stage079 3个月：5%分位收益 `-11.4702%`，中位收益 `13.5434%`，正收益率 `73.4804%`，年化低于5%概率 `29.4012%`，最差期内回撤 `-29.1988%`，破20回撤率 `18.5052%`，破30回撤率 `0%`，Ulcer P95 `17.7786`。
- Stage079 6个月：5%分位收益 `-2.0393%`，中位收益 `33.9947%`，正收益率 `93.4772%`，年化低于5%概率 `9.0099%`，最差期内回撤 `-29.7007%`，破20回撤率 `35.7109%`，破30回撤率 `0%`，Ulcer P95 `19.9011`。
- `hot20_full_deleverage_recovery` 3个月：5%分位收益 `-13.4715%`，中位收益 `12.5188%`，正收益率 `73.5254%`，年化低于5%概率 `30.4367%`，最差期内回撤 `-25.1159%`，破20回撤率 `12.4268%`，破30回撤率 `0%`，Ulcer P95 `16.5115`。
- `hot20_full_deleverage_recovery` 6个月：5%分位收益 `0.1309%`，中位收益 `32.0921%`，正收益率 `95.2135%`，年化低于5%概率 `9.0568%`，最差期内回撤 `-27.5860%`，破20回撤率 `36.7433%`，破30回撤率 `0%`，Ulcer P95 `17.2192`。
- 解释：完整版本明显改善6个月左尾和水下痛感，但3个月左尾更差、中位收益更低，同时长期收益和 Sharpe 下降，因此不能晋级。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage392_stage079_overheat_cooldown_mechanism_ablation_report_stage392_stage079_overheat_cooldown_mechanism_ablation_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage392_stage079_overheat_cooldown_mechanism_ablation_summary_stage392_stage079_overheat_cooldown_mechanism_ablation_v1.csv`
- horizon：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage392_stage079_overheat_cooldown_mechanism_ablation_horizon_stage392_stage079_overheat_cooldown_mechanism_ablation_v1.csv`
- score：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage392_stage079_overheat_cooldown_mechanism_ablation_score_stage392_stage079_overheat_cooldown_mechanism_ablation_v1.csv`
- gate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage392_stage079_overheat_cooldown_mechanism_ablation_gate_stage392_stage079_overheat_cooldown_mechanism_ablation_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage392_stage079_overheat_cooldown_mechanism_ablation_daily_stage392_stage079_overheat_cooldown_mechanism_ablation_v1.csv`
- scale_history：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage392_stage079_overheat_cooldown_mechanism_ablation_scale_history_stage392_stage079_overheat_cooldown_mechanism_ablation_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage392_stage079_overheat_cooldown_mechanism_ablation_decision_stage392_stage079_overheat_cooldown_mechanism_ablation_v1.json`

## 结论

- 本阶段结论：`no_normal_gate_candidate`。Stage079 仍为唯一基准。
- 是否进入下一步：暴涨冷却阈值族不进入继续优化；仅保留经验。
- 下一步：
  - 不继续扫 `hot20`、`hot60`、冷却比例、恢复比例或减仓金额小数。
  - 如果继续提升3个月/6个月体验，方向应转向真实低相关收益源、成本更低的承载工具，或不直接来自坏窗口归因的外生状态变量。

## 过拟合反思

- 运行前判断：过拟合风险中等。规则来自 Stage089 坏窗口归因，但本阶段固定机制拆解，不扫阈值。
- 运行后判断：不应晋级，也不应继续调小数救援。完整版本体验分最高但牺牲收益/Sharpe；仅刹车版本接近基准但改善不够；恢复无减仓版本明显失败。
- 原因：真实引擎把 PnL 层诊断的理想缩放还原成实际下单、持仓和减仓后，收益路径与成本暴露发生变化，短持有改善无法免费获得。

## 继续价值反思

- 运行前判断：有价值。需要确认 Stage091 的失败来自哪个机制，避免过早放弃或误判。
- 运行后判断：继续暴涨冷却路线价值不大；继续整体目标仍有价值。
- 原因：机制拆解已经说明这类权益过热冷却无法在不劣化现有指标的前提下稳定提升3个月和6个月体验；目标本身仍有价值，但需要新信息源或新承载，而不是坏窗口阈值修补。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage092 执行约束和阶段记录。
- 是否更新 `research/registry.md`：否，本阶段不是正式候选更新，且避免频繁修改总索引。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`，不追加 `memory.md`。
