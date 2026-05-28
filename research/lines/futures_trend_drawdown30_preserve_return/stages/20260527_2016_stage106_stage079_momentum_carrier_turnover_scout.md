# Stage106 Stage079动量承载降换手Scout

- 时间：2026-05-27 20:16 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 阶段性质：Stage105 正向线索的执行降换手验证；不调品种、月份或坏窗口状态。
- 是否重要突破版本：否。重要边界确认：横截面动量承载很强，但目前无法同时通过高滑点和 `start_2022` 冷启动；Stage103 仍是当前最优执行相对候选。
- 是否触发 A/B/C：是。A=`Stage079`；C0=`Stage103 broker10_guard`；C1=`60日横截面动量周频对照`；C2=`60日横截面动量月频承载`；C3=`120日横截面动量月频承载`。
- 本次脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage406_stage079_momentum_carrier_turnover_scout.py`
- 输出报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage406_stage079_momentum_carrier_turnover_scout_report_stage406_stage079_momentum_carrier_turnover_scout_v1.md`
- 输出图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage406_stage079_momentum_carrier_turnover_scout_chart_stage406_stage079_momentum_carrier_turnover_scout_v1.png`

## 开始前反思

- 是否在过拟合：否。Stage106 只验证 Stage105 已暴露的正向线索是否可通过降换手改善执行鲁棒性；没有按失败窗口加日期、品种或阈值过滤。
- 是否仍有价值继续做：是。Stage105 的 `mom60_weekly` 全周期和短持有体验显著优于 Stage103，但失败集中在高滑点与 `start_2022`，值得做一次低频承载验证。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage406_stage079_momentum_carrier_turnover_scout.py`
- 新增参数：
  - `mom60_weekly_min1_guard`：Stage105 周频动量对照，保留用于比较。
  - `mom60_monthly_min1_guard`：每20个交易日再平衡，买近60日强者、卖近60日弱者，各3个品种，每品种1手。
  - `mom120_monthly_min1_guard`：每20个交易日再平衡，买近120日强者、卖近120日弱者，各3个品种，每品种1手。
  - 所有 overlay 仍受 `1.10` 倍保证金闸门约束。
- 修改参数：无正式策略默认修改。
- 删除参数：无。

## 回测结果

Stage079：期末权益 `31,040,650`，总收益 `4947.2602%`，最大回撤 `-29.7007%`，Sharpe `1.3188`，Ulcer `15.0874`，总滑点 `1,556,750`，总交易次数 `757`，胜率 `45.3826%`。

Stage103 `broker10_guard`：期末权益 `31,730,915`，总收益 `5059.4984%`，最大回撤 `-28.9792%`，Sharpe `1.3681`，Ulcer `14.3132`，3个月分 `121.2041`，6个月分 `134.4513`，成本压力 `1x/2x/3x/5x` 最大回撤 `-28.9792%/-30.4073%/-31.9135%/-39.1469%`。

`mom60_weekly_min1_guard`：期末权益 `32,437,815`，总收益 `5174.4415%`，最大回撤 `-27.3580%`，Sharpe `1.4044`，Ulcer `13.4922`，3个月分 `143.2053`，6个月分 `152.0460`，用户目标8项改善 `8/8` 与 `8/8`，换手 `1052` 手。失败项：`start_2022` 最大回撤 `-35.3241%`，5倍滑点最大回撤 `-40.9311%`。决策：强 paper 线索，不晋级。

`mom60_monthly_min1_guard`：期末权益 `32,391,345`，总收益 `5166.8854%`，最大回撤 `-27.4470%`，Sharpe `1.3948`，Ulcer `13.8191`，3个月分 `130.3164`，6个月分 `92.3545`，换手 `650` 手。失败项：3个月/6个月综合目标不达、`start_2022` 最大回撤 `-39.2690%`，3倍/5倍滑点最大回撤 `-35.8308%/-45.3200%`。决策：降换手没有改善本质风险，反证。

`mom120_monthly_min1_guard`：期末权益 `32,316,005`，总收益 `5154.7976%`，最大回撤 `-28.1362%`，Sharpe `1.3802`，Ulcer `13.8712`，3个月分 `149.2911`，6个月分 `158.4432`，用户目标8项改善 `8/8` 与 `8/8`，换手 `538` 手，Stage104底部5%窗口相对 Stage103：3个月 `+0.3686pp`，6个月 `-0.2194pp`。失败项：`start_2022` 最大回撤 `-39.7689%`，10%保证金上浮下部分窗口有拒单风险，5倍滑点最大回撤 `-40.4304%`。决策：最强体验分线索，但不能晋级。

## 结论

- 降换手没有解决 Stage105 暴露的失败根因。月频版本降低了换手，但 `start_2022` 更差，说明问题不是单纯成本，而是这类动量承载在某些启动周期会与 C3 同向承压。
- `mom120_monthly` 是非常强的 paper 研究线索：全周期收益、Sharpe、Ulcer、3个月/6个月体验分都优于 Stage103；但它没通过 `fresh_start_dd30_pass` 和高滑点压力，所以不能作为当前 Stage079 正式晋级版本。
- 当前可晋级/执行相对候选仍是 Stage103 `xsmom_vt10_q_momq_round_half_true_broker10_guard`。

## 后续规划和 TODO

1. 不再继续救 `mom60/mom120` 的 top_n、再平衡天数、具体月份、品种过滤或坏窗口条件。
2. 动量承载可保留为独立 paper 研究线索，但不能进入当前正式候选流程。
3. 若后续要再提升 Stage103 的短持有理想目标，必须找真正不同状态暴露的来源，或使用外生/跨资产承载；同一商品趋势/动量承载大概率会在 `start_2022` 类窗口同向承压。

## 结束后反思

- 是否在过拟合：不是。Stage106 没有按结果继续补条件；周频/月频/120日对照均按结构性理由预声明。
- 是否还有价值继续做：本子路线继续价值低。总目标仍有价值，但不应继续围绕同商品横截面动量参数做救援。
