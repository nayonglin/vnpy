# Stage223 Stage520收益损失归因审计

- 时间：2026-06-01 20:27 CST
- 所属研究线：`futures_trend_drawdown30_preserve_return`
- 阶段性质：只读机制归因，不改策略、不改入场/出场、不新增品种、不扫小数参数。
- 决策标签：`usage_gate_too_blunt_seek_surgical_peak_margin_or_low_margin_alpha`
- 是否重要突破版本：是。它解释了 Stage520 风控壳收益保留不足的核心原因，并改变下一步方向。

## 开始前反思

- 是否过拟合：否。本阶段只比较既有 Stage519/Stage520 固定路径的日度 PnL 差、保证金桶和年度归因，没有新增交易规则，也没有按坏日期或坏品种筛选。
- 是否还有价值继续做：是。Stage222 已证明加现金不能提升资本效率，本阶段用于判断收益到底被哪层风控削掉，避免继续在错误参数附近消耗。

## 外部调研与判断

- 调研参考：公开 managed futures / trend following 风险预算、风险平价与组合保证金资料，以及交易所/监管侧关于 spread/portfolio margin 必须符合规则认定的资料。
- 判断：组合分散、风险预算和低相关收益源是正确先验，但保证金下降不能靠回测中主观净掉相关品种；必须以券商/交易所实际认可的 exact position margin 为硬约束。Stage223 因此不发明组合净额规则，只做现有路径损失归因。

## 新增/修改/删除

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage523_stage520_return_loss_attribution.py`
- 新增输出：
  - `qmt_roll_stage523_stage520_return_loss_attribution_pair_summary_stage523_stage520_return_loss_attribution_v1.csv`
  - `qmt_roll_stage523_stage520_return_loss_attribution_daily_gap_stage523_stage520_return_loss_attribution_v1.csv`
  - `qmt_roll_stage523_stage520_return_loss_attribution_year_gap_stage523_stage520_return_loss_attribution_v1.csv`
  - `qmt_roll_stage523_stage520_return_loss_attribution_margin_bucket_gap_stage523_stage520_return_loss_attribution_v1.csv`
  - `qmt_roll_stage523_stage520_return_loss_attribution_top_loss_days_stage523_stage520_return_loss_attribution_v1.csv`
  - `qmt_roll_stage523_stage520_return_loss_attribution_decision_stage523_stage520_return_loss_attribution_v1.json`
  - `qmt_roll_stage523_stage520_return_loss_attribution_report_stage523_stage520_return_loss_attribution_v1.md`
  - `qmt_roll_stage523_stage520_return_loss_attribution_chart_stage523_stage520_return_loss_attribution_v1.png`
- 新增参数：无正式策略参数；只新增审计 pair。
- 修改参数：无。
- 删除参数：无。
- 修改/删除回测结果：无。

## 审计口径

固定比较：

1. `r070_legacy_nocap_control -> r070_productcap30`
2. `r070_productcap30 -> r070_pc30_u80`
3. `r070_productcap30 -> r070_pc30_u75`
4. `r080_productcap30 -> r080_pc30_u80`
5. `r080_productcap30 -> r080_pc30_u75`
6. `r080_pc30_u80 -> r080_pc25_u75`

核心指标：

- `gap_pnl_source_minus_target`：source 日净损益减 target 日净损益。
- `positive_loss_pnl`：target 相对 source 少赚或多亏的正向损失。
- `low_margin_loss_share_pct`：这些损失中，source 当日 broker10 保证金/权益不超过 90% 的占比。
- `over100_loss_share_pct`：这些损失中，source 当日 broker10 保证金/权益超过 100% 的占比。

## 关键结果

### 单产品 cap 不是收益塌缩来源

`r070_legacy_nocap_control -> r070_productcap30`：

- source 总收益：`3348.8675%`
- target 总收益：`3492.1366%`
- 收益差：`-143.2691pp`
- source 最大回撤：`-38.5861%`
- target 最大回撤：`-35.6884%`
- source broker10 最大保证金/权益：`140.3161%`
- target broker10 最大保证金/权益：`116.0430%`
- source 穿100天数：`25`
- target 穿100天数：`5`

结论：单产品 cap 不但没有造成收益崩塌，反而改善了收益、回撤和保证金尖峰。

### 总资金占用 gate 是主要收益损失来源

`r080_productcap30 -> r080_pc30_u80`：

- source 总收益：`4240.0268%`
- target 总收益：`3188.2171%`
- 收益差：`1051.8098pp`
- source 最大回撤：`-36.4617%`
- target 最大回撤：`-34.2241%`
- source broker10 最大保证金/权益：`123.1621%`
- target broker10 最大保证金/权益：`103.6087%`
- source 穿100天数：`5`
- target 穿100天数：`4`
- total gap PnL：`6,468,630`
- positive loss PnL：`27,017,820`
- top5 loss 占 positive loss：`12.1816%`
- source 保证金不超过90%的损失占比：`99.2326%`
- source 保证金超过100%的损失占比：`0.7674%`

`r080_productcap30 -> r080_pc30_u75`：

- source 总收益：`4240.0268%`
- target 总收益：`2659.3821%`
- 收益差：`1580.6447pp`
- target broker10 最大保证金/权益：`98.8782%`
- target 穿100天数：`0`
- total gap PnL：`9,720,965`
- positive loss PnL：`39,362,095`
- top5 loss 占 positive loss：`12.6785%`
- source 保证金不超过90%的损失占比：`99.1734%`
- source 保证金超过100%的损失占比：`0.8266%`

这说明 usage gate 为解决少数 broker100 尖峰，主要砍掉了大量普通保证金状态下的趋势利润日。

## 图表复盘

图：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage523_stage520_return_loss_attribution_chart_stage523_stage520_return_loss_attribution_v1.png`

视觉结论：

- 左上累计收益差显示，`productcap30 -> usage` 的损失从 2023 年后持续阶梯式扩大，2025 年快速拉开，不是少数极端保证金日的一次性损失。
- 左上的 `r070_no_cap_to_productcap30` 曲线长期在 0 下方，说明 product cap 相对 no-cap 反而有正贡献。
- 左下保证金桶显示，`usage80` 的 positive loss 最大桶是 `<=50%`，其次是 `50-75%`；`>100%` 桶损失很小。
- 右下散点显示大额损失点主要落在 source broker10 `30%-60%` 区间，而非 100% 附近。

## 本阶段结论

Stage520 收益保留不足的本质不是单产品集中度治理，而是总资金占用 gate 太钝。它不是“少吃几个爆仓边缘的大波段”，而是在正常保证金状态下反复拒绝/压低趋势利润腿。

因此：

- 不继续扫 `usage=76/77/78` 或 `productcap=26/27/28/29`。
- 不继续用外部现金救 `r080_pc30_u80`。
- 下一步如果沿策略本体，应测试更外科式的峰值保证金治理：只在 projected/exact broker10 接近超限时处理新增或最小必要减仓，而不是长期设置总 usage 上限。
- 如果外科式治理仍失败，则接受低收益可执行壳，或寻找真正低保证金、低相关、可真实成交的独立收益源。

## 标准结果字段

本阶段不产生新候选策略，只引用固定版本：

- `r080_productcap30`：总收益 `4240.0268%`，最大回撤 `-36.4617%`，Sharpe `1.5953`，总滑点 `1,555,370`，穿100天数 `5`。
- `r080_pc30_u80`：总收益 `3188.2171%`，最大回撤 `-34.2241%`，Sharpe `1.5901`，总滑点 `1,145,220`，穿100天数 `4`。
- `r080_pc30_u75`：总收益 `2659.3821%`，最大回撤 `-33.0780%`，Sharpe `1.5781`，总滑点 `957,220`，穿100天数 `0`。
- 期末权益、总交易次数、胜率：本阶段不重跑策略交易账本，沿用 Stage519/520 固定输出；Stage223 自身只新增 daily gap 归因表。

## 结束反思

- 是否过拟合：否。结论来自既有路径的损失归因，且明确否决继续扫小数参数。
- 是否还有价值继续做：是，但方向必须收窄。继续在 usage/cash 上救参价值低；值得做的是外科式峰值保证金测试，或者完全独立的低保证金收益源。

## TODO

1. 固定 `r080_productcap30` 作为高收益但少数保证金尖峰的 source，测试“只在接近 broker100 时处理”的外科式结构。
2. 外科式结构必须用 exact position margin 审计，不能用 Stage213 proxy。
3. 若外科式结构仍把普通利润腿砍掉，则停止保证金治理方向，转向低保证金独立收益源。
