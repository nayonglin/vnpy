# Stage097 Stage079活跃品种广度上限真实引擎验证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-05-27 18:47 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage096 固定后续候选的真实引擎 A/C 验证。
- 是否重要突破：否。重要反证：压并发能改善部分 6 个月体验，但会劣化收益与高滑点压力，不满足“现有指标不能劣化”。
- 是否触发A/B：是。A 为 Stage079，C 为 `Stage079 + max_concurrent_positions=3`。

## 外部调研与判断

- 参考资料：
  - Moskowitz / Ooi / Pedersen, Time Series Momentum：https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf
  - Hurst / Ooi / Pedersen, A Century of Evidence on Trend-Following Investing：https://research.cbs.dk/en/publications/a-century-of-evidence-on-trend-following-investing/
  - Baltas, Trend-Following, Risk-Parity and the Influence of Correlations：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2673124
- 我的判断：文献支持风险预算、相关性、组合权重约束这类方向，但 Stage079 的收益主要来自趋势右尾。并发上限如果只是少开仓，很可能改善部分水下体验，同时错过右尾收益；必须以真实引擎硬闸门为准。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage397_stage079_active_breadth_cap3_true_engine.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：候选 profile `active_breadth_cap3_true_engine`，仅设置 `max_concurrent_positions=3`。
- 修改参数：无正式默认参数修改；Stage079 默认仍不变。
- 删除参数：无。

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30。
- 账户规模：Stage079 口径，50万 C3 下单 + 11.5万外部现金，总账户 `615,000`。
- 成本口径：正常成本 + `2x/3x/5x` 滑点压力。
- 样本过滤：所有自然日启动窗口，90日和180日未来体验。
- 策略/归因口径：真实引擎 A/C；候选只改变最大并发活跃品种上限，不改信号、品种池、AI池、供需过滤、单笔风险。

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
- 候选 `active_breadth_cap3_true_engine`：
  - 期末权益：`28,507,570`
  - 总收益：`4535.3772%`
  - 最大回撤：`-29.2131%`
  - Sharpe：`1.3334`
  - Ulcer：`14.2345`
  - 总滑点：`1,387,400`
  - 总交易次数：`620`
  - 胜率：`46.3023%`
- 3个月体验：
  - Stage079：5%分位 `-11.4702%`，中位 `13.5434%`，正收益率 `73.4804%`，年化低于5%概率 `29.4012%`，最差回撤 `-29.1988%`，DD20 触发率 `18.5052%`，Ulcer P95 `17.7786`。
  - cap3：5%分位 `-12.0851%`，中位 `13.6154%`，正收益率 `73.3904%`，年化低于5%概率 `30.2116%`，最差回撤 `-26.8201%`，DD20 触发率 `18.2350%`，Ulcer P95 `17.0018`。
  - 结论：3个月没有达到 +10% 体验提升，且 5%分位、正收益率、低增长概率劣化。
- 6个月体验：
  - Stage079：5%分位 `-2.0393%`，中位 `33.9947%`，正收益率 `93.4772%`，年化低于5%概率 `9.0099%`，最差回撤 `-29.7007%`，DD20 触发率 `35.7109%`，Ulcer P95 `19.9011`。
  - cap3：5%分位 `1.0130%`，中位 `32.4123%`，正收益率 `95.8236%`，年化低于5%概率 `6.2412%`，最差回撤 `-29.2131%`，DD20 触发率 `35.3824%`，Ulcer P95 `18.4958`。
  - 结论：6个月体验确实改善，分数 `193.3726`，但中位收益略低，且硬约束失败。
- 成本压力：
  - Stage079 `1x/2x/3x/5x` 最大回撤：`-29.7007%/-35.7770%/-33.0393%/-41.1430%`。
  - cap3 `1x/2x/3x/5x` 最大回撤：`-29.2131%/-29.9559%/-29.8184%/-47.1242%`。
  - cap3 在 `5x` 滑点下劣于 Stage079，成本压力不劣化失败。
- 晋级闸门：
  - `promotion_pass=0`
  - 失败项：`total_return_not_lower`、`cost_stress_not_worse`
  - 3个月 +10% 改善失败；3/6个月各至少5/8项改善失败。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage397_stage079_active_breadth_cap3_true_engine_report_stage397_stage079_active_breadth_cap3_true_engine_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage397_stage079_active_breadth_cap3_true_engine_summary_stage397_stage079_active_breadth_cap3_true_engine_v1.csv`
- horizon：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage397_stage079_active_breadth_cap3_true_engine_horizon_stage397_stage079_active_breadth_cap3_true_engine_v1.csv`
- score：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage397_stage079_active_breadth_cap3_true_engine_score_stage397_stage079_active_breadth_cap3_true_engine_v1.csv`
- promotion：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage397_stage079_active_breadth_cap3_true_engine_promotion_stage397_stage079_active_breadth_cap3_true_engine_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage397_stage079_active_breadth_cap3_true_engine_cost_stress_stage397_stage079_active_breadth_cap3_true_engine_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage397_stage079_active_breadth_cap3_true_engine_daily_stage397_stage079_active_breadth_cap3_true_engine_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage397_stage079_active_breadth_cap3_true_engine_equity_drawdown_stage397_stage079_active_breadth_cap3_true_engine_v1.png`

## 结论

- 本阶段结论：`max_concurrent_positions=3` 不是可晋级优化。它解释了部分 6个月持有体验改善，但代价是总收益从 `4947.2602%` 降到 `4535.3772%`，且 5x 成本压力回撤从 Stage079 的 `-41.1430%` 恶化到 `-47.1242%`。
- 是否进入下一步：不进入并发上限路线下一步。
- 下一步：停止围绕活跃品种并发上限做 `2/3/4/5` 扫描。若继续优化 3/6个月体验，只能寻找真实低相关收益源、成本更低承载，或能不减少趋势右尾捕获的外生状态变量。

## 过拟合反思

- 运行前判断：否。只验证 Stage096 诊断后冻结的一组粗整数候选。
- 运行后判断：当前验证不是过拟合，但继续扫 `2/4/5` 或通过提高风险补收益会过拟合。
- 原因：候选有明确经济含义且单次验证；结果失败后必须停止，不应按结果修阈值。

## 继续价值反思

- 运行前判断：有价值。Stage096 给出了可验证的广度风险状态。
- 运行后判断：并发上限子路线继续价值低；总目标仍有价值。
- 原因：cap3 改善的是体验局部，不满足“现有指标不能劣化”；说明直接压趋势暴露不是当前目标的解法。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage097 约束。
- 是否更新 `research/registry.md`：否，未产生正式候选。
- 是否追加根目录 `memory.md/back_log.md`：建议追加 `back_log.md`，因为这是一个明确的反证边界。
