# Stage226 动态sizing软上限最小验证

- line_id：`futures_trend_risk_overlay`
- 当前模式：`day`
- 记录时间：`2026-05-10 19:20 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：新研究线启动 + A vs C最小验证
- 是否重要突破：是，确认风险覆盖层方向有明确价值，但当前v1不适合直接合入正式基准
- 是否触发A/B：是，按`version-ab-experiment`规则做`A=78-1`与`C=78-1+动态sizing软上限`

## 外部调研与判断

- 参考资料：
  - Trend-following/tail-risk overlay研究强调，覆盖层应同时考虑成本、可交易性和尾部风险，而不是只看平均收益。
  - 资金覆盖层实践资料强调显式杠杆/保证金预算、流动性缓冲和压力测试，避免平静期放大到危险规模。
  - 回撤控制资料强调回撤恢复具有非线性不对称，风险治理重点应是阻断大回撤，而不是事后恢复。
- 我的判断：
  - `78-1`经Stage225已证明AI选品有价值，继续调AI名单容易过拟合。
  - 当前最值得做的是“资金暴露随权益增长的非线性治理”，即保留alpha但改变暴露曲线。
  - 动态sizing软上限是结构性规则，不是针对某一窗口或某一品种的补丁，适合作为首个候选。

## 本次变更

- 新增研究线：
  - `research/lines/futures_trend_risk_overlay/LINE.md`
- 修改索引：
  - `research/registry.md`
- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage226_risk_overlay_dynamic_soft_cap.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `enable_dynamic_sizing_equity_soft_cap=True`
  - `dynamic_sizing_equity_soft_cap_base=1_000_000.0`
  - `dynamic_sizing_equity_soft_cap_max=3_000_000.0`
  - `dynamic_sizing_equity_soft_cap_participation=0.30`
  - `dynamic_sizing_equity_soft_cap_margin_start_ratio=0.55`
  - `dynamic_sizing_equity_soft_cap_margin_full_ratio=0.75`
  - `dynamic_sizing_equity_soft_cap_drawdown_start_ratio=0.05`
  - `dynamic_sizing_equity_soft_cap_drawdown_full_ratio=0.20`
- 修改参数：无正式参数修改，仅实验覆盖项。
- 删除参数：无。

## 回测/归因参数

- 数据区间：
  - 全样本：`2020-01-01`至`2026-04-30`
  - 近期冷启动：`2026-01-01`至`2026-04-30`
- 账户规模：`500,000`
- 成本口径：沿用`78-1`默认成本，另做`1x/2x/3x/5x`滑点压力。
- 样本过滤：沿用`78-1`产品宇宙、AI选品、FU卫星规则和短空门禁。
- 策略/归因口径：
  - A：`baseline_78_1`
  - C：`dynamic_soft_cap_v1`
  - Monte Carlo：`daily_block_bootstrap`与`trade_block_bootstrap`各`1000`次。

## 结果

- A `baseline_78_1` 全样本：
  - 期末权益：`25,542,885`
  - 总收益：`5008.5770%`
  - 最大回撤：`-40.0607%`
  - Sharpe：`1.1295`
  - 总滑点：`1,968,150`
  - 总交易次数：`880`
  - 胜率：`43.2432%`
- C `dynamic_soft_cap_v1` 全样本：
  - 期末权益：`8,482,695`
  - 总收益：`1596.5390%`
  - 最大回撤：`-39.2765%`
  - Sharpe：`1.2663`
  - 总滑点：`519,270`
  - 总交易次数：`846`
  - 胜率：`42.8571%`
- `2026`冷启动：
  - A与C相同，均为期末权益`450,540`、总收益`-9.8920%`、最大回撤`-28.5861%`、Sharpe`-0.6975`
  - 原因判断：2026年权益尚未超过软上限触发区，动态cap不生效。
- 滑点压力：
  - A在`5x`滑点下总收益`3434.0570%`、最大回撤`-66.4314%`
  - C在`5x`滑点下总收益`1181.1230%`、最大回撤`-48.6547%`
- Monte Carlo：
  - A daily亏损概率`2.0%`，C daily亏损概率`0.5%`
  - A daily回撤超过40%概率`95.9%`，C为`50.4%`
  - A trade-block破产/穿仓概率`52.6%`，C为`4.5%`
  - A trade-block回撤超过40%概率`88.6%`，C为`43.7%`
- 其他关键指标：
  - C把全样本收益从`5008.5770%`压到`1596.5390%`，收益牺牲较大。
  - C把总滑点从`1,968,150`压到`519,270`，显示容量压力显著降低。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage226_risk_overlay_dynamic_soft_cap_report_stage226_risk_overlay_dynamic_soft_cap_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage226_risk_overlay_dynamic_soft_cap_summary_stage226_risk_overlay_dynamic_soft_cap_v1.csv`
- orders：无。
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage226_risk_overlay_dynamic_soft_cap_daily_stage226_risk_overlay_dynamic_soft_cap_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage226_risk_overlay_dynamic_soft_cap_monte_carlo_summary_stage226_risk_overlay_dynamic_soft_cap_v1.csv`

## 结论

- 本阶段结论：
  - 风险覆盖层方向成立：动态sizing软上限显著降低Monte Carlo尾部风险和滑点压力。
  - `dynamic_soft_cap_v1`不应直接合入正式`78-1`：它把收益压得过多，且对2026冷启动无改善。
  - 更好的下一步不是微调小数，而是设计更贴近实盘目标的“收益保留型风险覆盖层”。
- 是否进入下一步：是。
- 下一步：
  - 方案1：分层出金/权益锁定覆盖层，保留策略账户内复利但定期把高水位收益转为不可再加杠杆的保守权益。
  - 方案2：保证金预算门禁，只在组合保证金压力过高时限制新增仓，而不是长期压低sizing equity。
  - 方案3：软上限v2只约束极端权益扩张区，不影响中前期复利。

## 过拟合反思

- 运行前判断：否。规则是结构性风险覆盖层，不针对某一品种、某一窗口或某一亏损样本。
- 运行后判断：否。本阶段没有根据结果继续调阈值；结果本身暴露了收益-风险权衡。
- 原因：候选改善尾部风险的同时牺牲收益，符合风险预算机制的预期，不是单窗口拟合。

## 继续价值反思

- 运行前判断：有。Stage225明确显示trade-block路径风险高，必须研究资金暴露治理。
- 运行后判断：有。C把trade-block破产/穿仓概率从`52.6%`降到`4.5%`，证明方向有价值。
- 原因：风险覆盖层能改变尾部分布，但v1收益代价过高，值得继续寻找更好的覆盖层形态。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：已更新，新增`futures_trend_risk_overlay`。
- 是否追加根目录 `memory.md/back_log.md`：追加`back_log.md`，`memory.md`追加研究政策摘要。
