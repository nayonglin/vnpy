# Stage090 Stage079暴涨冷却诊断

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-27 17:23 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：由 Stage089 短窗口失败归因引出的 PnL 层结构诊断；不修改真实引擎。
- 是否重要突破：强线索，但不是正式候选。
- 是否触发A/B：是。A 为 Stage079，C 为暴涨冷却/恢复再风险 PnL 层诊断。

## 外部调研与判断

- 参考资料：
  - 趋势跟踪与CTA研究中常见经验是：趋势策略的收益来自大趋势，但拥挤/暴涨后的反转会显著恶化短期持有体验。
  - 风险预算和波动目标研究支持用低自由度账户层状态管理风险，但真实引擎落地经常与净值层结果不同，必须复验。
- 我的判断：
  - Stage089 说明最差3个月窗口往往不是深水下启动，而是 C3 近高位且20/60日暴涨后反转。
  - 因此“暴涨后冷却”比“深回撤后刹车”更贴近3个月体验问题本质。
  - 但本阶段阈值来自历史归因，且是 PnL 层缩放，不能直接作为正式候选。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage390_stage079_overheat_cooldown_diagnostic.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - 近高位定义：C3 当前回撤不深于 `-5%`。
  - 短期暴涨：前20日收益 `>50%` 或 `>75%`。
  - 中期暴涨：前60日收益 `>75%`。
  - 冷却风险减少：`10万` C3 风险预算。
  - 恢复再风险：C3 回撤不浅于 `-15%` 且前20日收益转正后，增加 `5万` 风险预算。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2020-01-01` 至 `2026-04-30`。
- 账户规模：`61.5万`，不增加资金占用。
- 成本口径：C3 日PnL与滑点压力 `1x/2x/3x/5x`，delta 风险预算同步放大/缩小滑点。
- 样本过滤：无。
- 策略/归因口径：只使用前一日可见的 C3 权益回撤、20日收益、60日收益；PnL 层缩放，不是实盘引擎。

## 结果

- Stage079 基准：
  - 期末权益：`31,040,650`
  - 总收益：`4947.2602%`
  - 最大回撤：`-29.7007%`
  - Sharpe：`1.3182`
  - Ulcer：`15.0931`
  - 3个月体验分：`100.0000`
  - 6个月体验分：`100.0000`
- 最强诊断 `hot20_50_or60_75_brake100_recovery50`：
  - 规则：近高位前20日收益 `>50%` 或前60日收益 `>75%` 时冷却减 `10万` 风险；深回撤恢复确认后加 `5万` 风险。
  - 期末权益：`31,277,918`
  - 总收益：`4985.8403%`
  - 最大回撤：`-27.9019%`
  - Sharpe：`1.3504`
  - Ulcer：`13.9092`
  - 252/504日滚动破30回撤率：`0% / 0%`
  - 年度/季度回撤30内通过率：`100% / 100%`
  - 2x/3x/5x滑点压力下最大回撤分别为 `-29.3948%/-30.9743%/-38.7742%`，均不差于 Stage079 对应的 `-31.2917%/-33.0035%/-40.1055%`。
  - 3个月体验：
    - 5%分位收益：`-11.0449%`，优于 Stage079 `-11.4702%`
    - 中位收益：`14.0609%`，优于 `13.5155%`
    - 正收益率：`73.5374%`，略优于 `73.4473%`
    - 年化低于5%概率：`29.7030%`，差于 `29.4329%`
    - 最差期内回撤：`-27.9019%`，优于 `-29.1988%`
    - 破20回撤率：`17.2367%`，优于 `18.4968%`
    - Ulcer P95：`16.3507`，优于 `17.7760`
    - P95最长水下：`88` 天，持平
    - 3个月8项改善数：`6/8`
    - 3个月体验分：`111.8074`
  - 6个月体验：
    - 5%分位收益：`-0.9147%`，优于 `-2.0884%`
    - 中位收益：`35.4374%`，优于 `33.9211%`
    - 正收益率：`94.6060%`，优于 `93.4334%`
    - 年化低于5%概率：`8.3959%`，优于 `9.0525%`
    - 最差期内回撤：`-27.9019%`，优于 `-29.7007%`
    - 破20回撤率：`37.3827%`，差于 `35.7411%`
    - Ulcer P95：`18.4691`，优于 `19.9008`
    - P95最长水下：`163` 天，优于 `167` 天
    - 6个月8项改善数：`7/8`
    - 6个月体验分：`136.4792`
  - 综合短持有体验分：`125.3769`
- 次强诊断 `hot20_50_brake100_recovery50`：
  - 总收益：`4983.7050%`
  - 最大回撤：`-28.1002%`
  - Sharpe：`1.3444`
  - Ulcer：`13.9899`
  - 3个月分：`110.4194`
  - 6个月分：`136.0536`
  - 3个月/6个月8项改善数：`6/8`、`7/8`
- 正式晋级候选数：`0`
- 诊断门禁通过数：`2`
- 总滑点：沿用 C3 并按 delta 风险预算估算压力；未重跑真实撮合。
- 总交易次数/胜率：本阶段 PnL 层缩放不生成逐笔交易，沿用 C3 统计不可直接作为候选真实交易次数。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage390_stage079_overheat_cooldown_diagnostic_report_stage390_stage079_overheat_cooldown_diagnostic_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage390_stage079_overheat_cooldown_diagnostic_summary_stage390_stage079_overheat_cooldown_diagnostic_v1.csv`
- horizon：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage390_stage079_overheat_cooldown_diagnostic_horizon_stage390_stage079_overheat_cooldown_diagnostic_v1.csv`
- constraints：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage390_stage079_overheat_cooldown_diagnostic_constraints_stage390_stage079_overheat_cooldown_diagnostic_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage390_stage079_overheat_cooldown_diagnostic_cost_stress_stage390_stage079_overheat_cooldown_diagnostic_v1.csv`
- score：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage390_stage079_overheat_cooldown_diagnostic_score_stage390_stage079_overheat_cooldown_diagnostic_v1.csv`
- promotion：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage390_stage079_overheat_cooldown_diagnostic_promotion_stage390_stage079_overheat_cooldown_diagnostic_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage390_stage079_overheat_cooldown_diagnostic_decision_stage390_stage079_overheat_cooldown_diagnostic_v1.json`

## 结论

- 本阶段结论：`strong_pnl_diagnostic_requires_real_engine_not_promoted`
- 是否进入下一步：进入真实引擎可执行性验证前置设计，但不能直接晋级。
- 下一步：
  - 先检查真实引擎能否按“前一日账户权益路径状态”动态调整 C3 风险预算。
  - 若能落地，固定 `hot20_50_or60_75_brake100_recovery50` 和 `hot20_50_brake100_recovery50` 两个诊断，不再扫阈值。
  - 真实引擎复验必须重新计算逐笔、保证金、拒单、滑点、交易次数、胜率、多起点和3/6个月体验。

## 过拟合反思

- 运行前判断：有过拟合风险，但值得做诊断。
- 运行后判断：仍不能视为正式通过，过拟合风险中等偏高。
- 原因：
  - 线索来自 Stage089 对最差短窗口的归因，天然可能贴合 2021/2022 的暴涨反转。
  - 但规则使用账户权益状态而非品种黑名单，且不是小数连续扫描；结果跨硬指标、3个月、6个月和成本压力同时改善，所以值得进入真实引擎验证。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，且这是 Stage087 以来最强线索。
- 原因：
  - 它首次在诊断层同时满足全周期不劣化、3个月分数提升、6个月分数提升和 5/8 改善要求。
  - 但真实引擎落地可能复现不了 PnL 层缩放，因此下一步必须先验证可执行性。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否，尚非正式候选。
- 是否追加根目录 `memory.md/back_log.md`：是，作为强诊断线索。
