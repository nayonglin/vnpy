# Stage008 no-follow 30m 降风险真实引擎反证

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-19 18:29`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：冻结 A vs C 真实组合引擎；不改正式配置，不连接 CTP，不调用订单 API。
- 是否重要突破：否。本阶段反证一条看似合理的 no-follow 降风险形状。
- 是否触发A/B：否。候选未通过收益保留、回撤和 broker10 闸门。

## 外部调研与判断

- 参考资料：
  - Graham Capital `Trend-Following Primer`：`https://www.grahamcapital.com/blog/trend-following-primer/`
  - BNP Paribas `Know the essentials of trend following`：`https://wealthmanagement.bnpparibas/en/insights/market-strategy/trend-following-2024.html`
  - Trendfollowing.com `Trend Following Theory`：`https://www.trendfollowing.com/trend/`
  - SSRN `Trend Following Strategies: A Practical Guide`：`https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5140633`
  - `Intraday Time Series Momentum: International Evidence`：`https://centaur.reading.ac.uk/95566/1/Accepted-Version.pdf`
  - Concretum `Backtesting Data Quality: Can Your Data Provider Be Trusted?`：`https://concretumgroup.com/backtesting-data-quality-can-your-data-provider-be-trusted/`
  - Freqtrade `Lookahead analysis`：`https://www.freqtrade.io/en/stable/lookahead-analysis/`
- 我的判断：趋势跟随可以随趋势确认逐步建立或降低风险，但核心仍是保留右尾和正偏。Stage007 的 no-follow 是负质量线索，不是删除信号；因此 Stage008 只允许测试一个“降到最小风险但不删仓”的冻结规则。外部数据质量资料同时要求缺失 entry-day 分钟K不能插值或用未来K线替代，本阶段对缺失样本保持官方路径。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage008_no_follow_reduce_true_engine.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无可调交易参数；冻结候选常量：
  - `WINDOW_MINUTES=30`
  - `REDUCE_FRACTION=0.50`
  - `target_volume=max(1, floor(active_volume * 0.50))`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2018-01-01` 至 `2026-06-15`。
- 账户规模：当前官方正式口径 `150000`。
- 成本口径：正常成本 `1x`，另输出 `2x/3x` 压力。
- A：当前官方 C9/15w `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。
- C：官方 C9/15w + `no_follow_30m_reduce_to_half`。
- 策略/归因口径：
  - 官方 C9 正常开仓，保留 C2 stop、broker10 cap、`0.5R` stop/retry-once。
  - 若 C9 自身 `0.5R` stop/retry 已触发，优先执行 C9，不叠加 Stage008。
  - 若入场日已有分钟K，且前 `30` 根分钟K收盘相对入场价的方向性 R `<=0`，把 active volume 降到 `floor(50%)`，最低保留 `1` 手。
  - 若缺失 entry-day 分钟K、风险距离无效或原仓位只有 `1` 手，则保持官方路径。
  - 不恢复、不二次判断、不按品种/方向/年份/月度分支。

## 结果

- A 期末权益：`39,176,437.60`
- C 期末权益：`30,453,543.80`
- A 总收益：`26017.6251%`
- C 总收益：`20202.3625%`
- 收益保留：`77.6488%`
- A 最大回撤：`-45.0827%`
- C 最大回撤：`-46.2114%`
- 回撤改善：`-1.1288pp`，即 C 反而更差
- A Sharpe：`1.6331`
- C Sharpe：`1.5463`
- A 总滑点：`2,730,130`
- C 总滑点：`2,399,440`
- A 总交易次数：`787`
- C 总交易次数：`822`
- A 胜率：`53.2560%`
- C 胜率：`52.4779%`
- A broker10 峰值：`111.7365%`
- C broker10 峰值：`119.1849%`
- A `days_over_100pct`：`5`
- C `days_over_100pct`：`8`
- Stage008 触发降风险事件：`36` 次，合计 reduce volume `2376`
- 成本压力：
  - C `2x`：期末权益 `28,054,103.80`、总收益 `18602.7359%`、最大回撤 `-51.0988%`、Sharpe `1.4531`
  - C `3x`：期末权益 `25,654,663.80`、总收益 `17003.1092%`、最大回撤 `-56.4407%`、Sharpe `1.3608`、broker10 峰值 `162.6153%`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage008_no_follow_reduce_true_engine/qmt_roll_stage008_c9_minrisk_no_follow_reduce_true_engine_report_stage008_no_follow_reduce_true_engine_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage008_no_follow_reduce_true_engine/qmt_roll_stage008_c9_minrisk_no_follow_reduce_true_engine_summary_stage008_no_follow_reduce_true_engine_v1.csv`
- comparison：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage008_no_follow_reduce_true_engine/qmt_roll_stage008_c9_minrisk_no_follow_reduce_true_engine_comparison_stage008_no_follow_reduce_true_engine_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage008_no_follow_reduce_true_engine/qmt_roll_stage008_c9_minrisk_no_follow_reduce_true_engine_decision_stage008_no_follow_reduce_true_engine_v1.json`
- curve：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage008_no_follow_reduce_true_engine/qmt_roll_stage008_c9_minrisk_no_follow_reduce_true_engine_curve_stage008_no_follow_reduce_true_engine_v1.csv`
- cost_stress：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage008_no_follow_reduce_true_engine/qmt_roll_stage008_c9_minrisk_no_follow_reduce_true_engine_cost_stress_stage008_no_follow_reduce_true_engine_v1.csv`
- no_follow_reduce_events：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage008_no_follow_reduce_true_engine/qmt_roll_stage008_c9_minrisk_no_follow_reduce_true_engine_no_follow_reduce_events_stage008_no_follow_reduce_true_engine_v1.csv`
- closed_lots：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage008_no_follow_reduce_true_engine/qmt_roll_stage008_c9_minrisk_no_follow_reduce_true_engine_closed_lots_stage008_no_follow_reduce_true_engine_v1.csv`
- path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage008_no_follow_reduce_true_engine/qmt_roll_stage008_c9_minrisk_no_follow_reduce_true_engine_path_chart_stage008_no_follow_reduce_true_engine_v1.png`
- atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage008_no_follow_reduce_true_engine/qmt_roll_stage008_c9_minrisk_no_follow_reduce_true_engine_atlas_page001_stage008_no_follow_reduce_true_engine_v1.png` 至 `page003`

## 视觉观察

- 资金曲线图显示 C 从 `2021` 后明显低于 A，说明早段 no-follow 降风险削弱了后续复利底座。
- 最大回撤图显示 A 的谷值在 `2022-06-29`，C 的谷值后移到 `2023-03-08` 且更深，说明它没有解决原始大回撤，反而把削弱权益分母后的风险拖到后面。
- broker10 图显示 C 峰值 `119.1849%` 高于 A 的 `111.7365%`，这不是降风险应有的形态；主要原因是权益分母被削弱，后续同类持仓压力反而更危险。
- atlas page001 中 `AP210`、`AP501`、`SH405`、`SH607` 都被 30m no-follow 降风险；其中 `SH405` 是 Stage007 已识别的大额正收益反例，说明 no-follow 后仍可能展开趋势。
- atlas page002/page003 中 `au2412`、`lh2409`、`SM109`、`fu2209`、`MA305` 等进一步显示：前 30 分钟不跟随经常只是趋势启动的噪声，而不是错误充分条件。

## 结论

- 本阶段结论：`stage008_failed_return_retention_no_param_rescue`。
- 是否进入下一步：不进入多起点、不进入 A/B、不接正式版。
- 下一步：
  - 停止 `no_follow_30m_reduce_to_half` 形状，不扫 `15/30/60`、`0.25/0.5/0.75`、品种、方向、年份、月份。
  - `no_follow_30m` 只能保留为复盘标签或未来更强第一性规则的辅助证据，不能作为单独降风险规则。
  - 后续若继续分钟级方向，优先处理权威分钟数据覆盖，或寻找“入场前/入场当刻可见的结构质量”而不是入场后 30 分钟机械降仓。

## 过拟合反思

- 运行前判断：否。规则来自 Stage007 的负质量线索，冻结为单一形状，不按年份、品种、方向、月份或最终盈亏分支。
- 运行后判断：否，但如果继续调 `30` 分钟或 `50%` 就会过拟合。
- 原因：真实引擎已经证明这个形状收益保留不足、回撤和 broker10 更差。继续围绕窗口和比例救参，本质是在拟合少数右尾/左尾事件。

## 继续价值反思

- 运行前判断：有。Stage007 只有 closed-lot 贡献线索，必须用真实资金路径验证是否能保留 C9 右尾。
- 运行后判断：这个具体形状没有继续价值。
- 原因：C 只触发 `36` 次，却把收益保留打到 `77.6488%` 并恶化回撤/broker10，说明“不跟随就机械降半仓”会误伤关键右尾。研究线仍有价值，但下一步必须换第一性原则，不能围绕 no-follow 参数补丁化。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。当前属于并行研究线日常推进，暂不频繁改总索引。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是候选合入、正式候选、路线废弃、跨线合并或记录体系迁移，只是候选反证。
