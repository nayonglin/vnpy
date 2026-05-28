# Stage098 Stage079增量保证金预算门控真实引擎验证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-27 19:04 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：冻结结构候选 A/C 验证；不改入场信号、不改品种池、不扫保证金阈值。
- 是否重要突破：否。短持有体验改善真实存在，但收益和高滑点压力不满足“不劣化”。
- 是否触发A/B：是。A 为 Stage079，C 为 `同日增量保证金预算90%且保护pairwise rank1`。

## 外部调研与判断

- 参考资料：
  - Hurst, Ooi, Pedersen, *A Century of Evidence on Trend-Following Investing*：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026
  - Moskowitz, Ooi, Pedersen, *Time Series Momentum*：https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf
- 本轮网络/GitHub 检索关键词：`trend following whipsaw filter signal quality selection portfolio concentration managed futures research`、`GitHub futures trend following signal ranking portfolio selection whipsaw filter python`、`trend following time series momentum carry cross sectional momentum combination drawdown holding period experience`。
- 我的判断：
  - 公开趋势跟随研究更支持横截面选择质量、分散化、风险预算和成本控制，而不是单靠某个信号胜率补丁。
  - 本阶段候选来自既有 Stage125/126 的冻结结构经验，只把它迁移到 Stage079 真引擎验证；不从 Stage079 结果重新找阈值。
  - 结果显示预算门控可以改善3个月/6个月体验，但会牺牲总收益，并且在高滑点下不稳，因此不能作为正式优化。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage398_stage079_incremental_margin_gate_true_engine.py`
- 修改脚本：无正式策略默认修改。
- 删除脚本：无。
- 新增候选参数：
  - `enable_incremental_margin_budget_gate=True`
  - `incremental_margin_budget_gate_usage_ratio=0.90`
  - `incremental_margin_budget_gate_min_openable_candidates=2`
  - `incremental_margin_budget_gate_protected_selection_rank=1`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`。
- 账户规模：Stage079 账户口径 `61.5万`，即 `50万C3下单 + 11.5万外部现金`。
- 成本口径：正常成本 `1x`，并额外做 `2x/3x/5x` 滑点压力。
- 样本过滤：无品种黑名单、无年份排除、无相邻参数扫描。
- 策略口径：候选仅限制同日新增保证金预算，且保护 pairwise 选择排序第1候选；不改变已有持仓、不改变入场信号。

## 结果

- 基准 Stage079：
  - 期末权益 `31,040,650`
  - 总收益 `4947.2602%`
  - 最大回撤 `-29.7007%`
  - Sharpe `1.3188`
  - Ulcer `15.0874`
  - 总滑点 `1,556,750`
  - 总交易次数 `757`
  - 胜率 `45.3826%`
- 候选 `incremental_margin_gate90_rank1_true_engine`：
  - 期末权益 `30,409,165`
  - 总收益 `4844.5797%`
  - 最大回撤 `-29.3358%`
  - Sharpe `1.3282`
  - Ulcer `14.7327`
  - 总滑点 `1,502,360`
  - 总交易次数 `761`
  - 胜率 `46.0733%`
- 3个月任意启动体验：
  - Stage079：5%分位收益 `-11.4702%`，中位收益 `13.5434%`，正收益率 `73.4804%`，年化低于5%概率 `29.4012%`，DD20 触发率 `18.5052%`，Ulcer P95 `17.7786`，体验分 `100`。
  - 候选：5%分位收益 `-11.1472%`，中位收益 `13.6544%`，正收益率 `74.2008%`，年化低于5%概率 `28.4106%`，DD20 触发率 `15.6686%`，Ulcer P95 `17.5550`，体验分 `116.0702`。
- 6个月任意启动体验：
  - Stage079：5%分位收益 `-2.0393%`，中位收益 `33.9947%`，正收益率 `93.4772%`，年化低于5%概率 `9.0099%`，DD20 触发率 `35.7109%`，Ulcer P95 `19.9011`，体验分 `100`。
  - 候选：5%分位收益 `-1.1600%`，中位收益 `33.4108%`，正收益率 `93.8057%`，年化低于5%概率 `7.8836%`，DD20 触发率 `28.7189%`，Ulcer P95 `19.7628`，体验分 `134.2389`。
- 成本压力：
  - 候选 `1x/2x/3x/5x` 最大回撤为 `-29.3358%/-35.8095%/-40.4562%/-45.0405%`。
  - Stage079 `1x/2x/3x/5x` 最大回撤为 `-29.7007%/-35.7770%/-33.0393%/-41.1430%`。
  - 候选在 `2x/3x/5x` 压力下差于 Stage079。
- 候选归因：正常成本下入口候选快照 `1082` 行；增量门控阻断 `5` 次，保护 rank1 `314` 次；阻断候选 pairwise 中位 rank `2`、AI pool 中位 rank `3`。
- 晋级闸门：`no_promotion`。失败项为 `total_return_not_lower,cost_stress_not_worse`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage398_stage079_incremental_margin_gate_true_engine_report_stage398_stage079_incremental_margin_gate_true_engine_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage398_stage079_incremental_margin_gate_true_engine_summary_stage398_stage079_incremental_margin_gate_true_engine_v1.csv`
- horizon：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage398_stage079_incremental_margin_gate_true_engine_horizon_stage398_stage079_incremental_margin_gate_true_engine_v1.csv`
- score：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage398_stage079_incremental_margin_gate_true_engine_score_stage398_stage079_incremental_margin_gate_true_engine_v1.csv`
- promotion：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage398_stage079_incremental_margin_gate_true_engine_promotion_stage398_stage079_incremental_margin_gate_true_engine_v1.csv`
- cost stress：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage398_stage079_incremental_margin_gate_true_engine_cost_stress_stage398_stage079_incremental_margin_gate_true_engine_v1.csv`
- candidate summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage398_stage079_incremental_margin_gate_true_engine_candidate_summary_stage398_stage079_incremental_margin_gate_true_engine_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage398_stage079_incremental_margin_gate_true_engine_daily_stage398_stage079_incremental_margin_gate_true_engine_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage398_stage079_incremental_margin_gate_true_engine_decision_stage398_stage079_incremental_margin_gate_true_engine_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage398_stage079_incremental_margin_gate_true_engine_equity_drawdown_stage398_stage079_incremental_margin_gate_true_engine_v1.png`

## 结论

- 本阶段结论：增量保证金预算门控能改善3个月/6个月任意启动体验，但不能在不降低收益和不劣化成本压力的前提下晋级。
- 是否进入下一步：本路线不继续。
- 下一步：停止围绕保证金预算阈值、保护rank、同日候选数量做救援；若继续优化短持有体验，需要寻找真实低相关收益源、成本更低承载或不砍趋势右尾的外生状态变量。

## 过拟合反思

- 运行前判断：不是过拟合。只验证一个冻结结构，不扫 `0.80/0.85/0.95`，不扫保护 rank。
- 运行后判断：当前验证不是过拟合，但如果继续调阈值、rank 或补风险把收益救回来，会过拟合。
- 原因：候选已经在固定规则下暴露出收益和高滑点压力缺陷，继续小数救援是在历史路径上挤结果。

## 继续价值反思

- 运行前判断：有价值。该候选具有清晰交易含义：限制同日新增风险预算，理论上可能改善任意启动短窗口体验。
- 运行后判断：该子路线继续价值低；总目标仍有价值。
- 原因：短持有体验改善是真实的，但失败项正好是硬目标里的收益不降低和成本压力不劣化，无法作为 Stage079 的正式优化。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage098 边界。
- 是否更新 `research/registry.md`：否，未形成正式候选。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md` 摘要；`memory.md` 暂不更新。
