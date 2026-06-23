# Stage074 初始开仓权威执行源决策审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 09:01 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：initial-entry 执行源选择审计，不是交易规则
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk DataDownloader 官方文档：`https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.tools.download.html`，确认历史数据下载支持 tick 级精度和任意 K 线周期，`dur_sec=0` 为 Tick 数据。
  - TqSdk 行情官方文档：`https://doc.shinnytech.com/tqsdk/latest/usage/mddatas.html`，确认 K 线字段包含 open/high/low/close/volume，tick 序列包含 bid_price1/ask_price1/volume 等盘口字段。
  - vn.py `object.py`：`https://github.com/vnpy/vnpy/blob/master/vnpy/trader/object.py`，确认 `TickData` 是 last trade、orderbook snapshot 和 intraday statistics，`BarData` 是 OHLCV 周期条。
- 我的判断：
  - Stage073 已证明 official open 与 raw/Stage449 zero-volume minute open 同源，但与当前 Tq tick top-book 不同源；Stage074 不能继续抽异源盘口特征。
  - 第一性问题不是“哪个字段预测盈亏”，而是“哪个数据源能解释正式回放的成交价”。没有权威执行源，就没有可信的分钟级进出场研究。
  - 本阶段选择 raw proxy bar authority 作为后续 bar-level 审计源；Tq tick 只能作为异源 TCA 观察，不允许进入开仓过滤、最小风险、恢复风险或退出规则。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage074_initial_entry_authoritative_source_decision_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：继承当前官方 C9/15w 全周期路径与 Stage045/Stage040 initial-entry ledger，覆盖 `2018-2026` 的 `324` 个 initial opens。
- 账户规模：当前官方 C9/15w，`150,000`。
- 成本口径：沿用官方 C9/15w 既有成本，不新增滑点/手续费假设。
- 样本过滤：
  - 固定审计全部 `324` 个 initial opens。
  - `timestamp_ready=1` raw proxy 子集为 `219` 笔。
  - `fallback_daily_next_open_no_proxy` 为 `105` 笔，只标记缺口，不硬补分钟成交源。
  - 不按盈亏、产品、方向、年份、交易所或时段筛选。
- 策略/归因口径：
  - 不改变官方交易。
  - 不新增开仓、减仓、恢复风险或退出规则。
  - 不跑 true engine。
  - 不连接 CTP，不调用订单 API。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - decision：`stage074_select_raw_proxy_bar_authority_for_bar_level_audit_no_tick_rules`
  - initial opens：`324`
  - timestamp-ready raw proxy：`219`
  - fallback no proxy：`105`
  - raw anchor exact/zero-volume/degenerate：`219/219/219`
  - Stage449 anchor ready/exact：`202/202`
  - Stage449 missing but raw fallback ready：`17`
  - Stage861 official-date first exact：`84`
  - Tq proxy batch ready/exact/mismatch：`60/46/14`
  - broker10 峰值：`111.7365%`
  - strategy_rule_created：`False`
  - true_engine_run：`False`
  - ab_triggered：`False`

## 源决策分类

- `raw_stage449_zero_volume_bar_authority` + `stage149_seed_proxy`：`114` 笔，raw exact/zero/degenerate `114/114/114`，Stage449 exact `114`，Tq batch/exact `27/20`，净已实现 PnL `+24,731,456.40`。
- `raw_stage449_zero_volume_bar_authority` + `raw_proxy`：`88` 笔，raw exact/zero/degenerate `88/88/88`，Stage449 exact `88`，Tq batch/exact `31/24`，净已实现 PnL `+10,693,569.30`。
- `raw_stage452_fallback_zero_volume_bar_authority_stage449_missing` + `raw_proxy`：`17` 笔，raw exact/zero/degenerate `17/17/17`，Stage449 missing，Tq batch/exact `2/2`，净已实现 PnL `-3,034,368.20`。
- `fallback_no_proxy_not_minute_authority` + `fallback_daily_next_open_no_proxy`：`105` 笔，timestamp-ready `0`，不具备 raw/Stage449 分钟权威源，只能保持官方路径或先补 raw proxy。

## 视觉观察

- authority route path chart 显示：官方权益路径上，`raw_stage449_zero_volume_bar_authority` 覆盖 `2020` 之后大部分 timestamp-ready initial-entry 事件，并承载主要右尾台阶；`raw_stage452_fallback_zero_volume_bar_authority_stage449_missing` 数量少且累计贡献长期偏负，后续必须单独标记为 Stage449 缺口 fallback，不应混作同一质量信号。
- cumulative PnL route chart 显示：Stage449/raw authority 绿线从 `2021` 后持续抬升，在 `2023`、`2025` 贡献大额右尾；Stage452 fallback 蓝线自 `2022` 后持续低于零。这个差异是源覆盖/缺口结构，不是可交易 alpha 标签。
- source coverage decision chart 显示：`324` 个 initial opens 中，raw proxy timestamp-ready 只有 `219`；raw exact、zero-volume、degenerate 都是 `219`，Stage449 ready/exact 都是 `202`；Tq batch ready 只有 `60`，exact `46`。覆盖不足和异源 exact 率不足都不支持把 Tq spread/depth/imbalance 写成规则。
- year source matrix 显示：`2018-2019` 的 no-proxy 灰色样本最集中，后续年份逐步转入 raw/Stage449 authority；这更像历史数据源覆盖问题，不是市场状态或信号好坏。
- source price delta atlas 显示：timestamp-ready 权威样本中 engine/raw/Stage449 的 delta 基本贴近 `0R`；Stage861 first 与 Tq nearest 多处偏离，no-proxy 样本缺少 raw/Stage449 可点时化证据。atlas 直观支持后续先按 raw proxy bar authority 做 bar-level 审计，而不是混入异源盘口。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage074_initial_entry_authoritative_source_decision_audit/qmt_roll_stage074_c9_minrisk_initial_entry_authoritative_source_decision_audit_report_stage074_initial_entry_authoritative_source_decision_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage074_initial_entry_authoritative_source_decision_audit/qmt_roll_stage074_c9_minrisk_initial_entry_authoritative_source_decision_audit_summary_stage074_initial_entry_authoritative_source_decision_audit_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage074_initial_entry_authoritative_source_decision_audit/qmt_roll_stage074_c9_minrisk_initial_entry_authoritative_source_decision_audit_decision_stage074_initial_entry_authoritative_source_decision_audit_v1.json`
- source decision audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage074_initial_entry_authoritative_source_decision_audit/qmt_roll_stage074_c9_minrisk_initial_entry_authoritative_source_decision_audit_source_decision_audit_stage074_initial_entry_authoritative_source_decision_audit_v1.csv`
- class summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage074_initial_entry_authoritative_source_decision_audit/qmt_roll_stage074_c9_minrisk_initial_entry_authoritative_source_decision_audit_source_decision_class_summary_stage074_initial_entry_authoritative_source_decision_audit_v1.csv`
- year matrix：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage074_initial_entry_authoritative_source_decision_audit/qmt_roll_stage074_c9_minrisk_initial_entry_authoritative_source_decision_audit_year_source_matrix_stage074_initial_entry_authoritative_source_decision_audit_v1.csv`
- authority route path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage074_initial_entry_authoritative_source_decision_audit/qmt_roll_stage074_c9_minrisk_initial_entry_authoritative_source_decision_audit_official_path_authority_route_chart_stage074_initial_entry_authoritative_source_decision_audit_v1.png`
- source coverage decision chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage074_initial_entry_authoritative_source_decision_audit/qmt_roll_stage074_c9_minrisk_initial_entry_authoritative_source_decision_audit_source_coverage_decision_chart_stage074_initial_entry_authoritative_source_decision_audit_v1.png`
- source price delta atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage074_initial_entry_authoritative_source_decision_audit/qmt_roll_stage074_c9_minrisk_initial_entry_authoritative_source_decision_audit_source_price_delta_atlas_stage074_initial_entry_authoritative_source_decision_audit_v1.png`

## 结论

- 本阶段结论：`stage074_select_raw_proxy_bar_authority_for_bar_level_audit_no_tick_rules`
- 是否进入下一步：是，但下一步仍是执行源边界内的 bar-level 审计或同源数据工程，不是直接交易规则。
- 下一步：
  - 若无同源 tick/order-book，下一步只能在 raw proxy bar authority 上做 bar-level execution boundary candidate 或继续补数据，不得使用异源 Tq tick top-book 的 spread、depth、imbalance、mid/last move、volume、range、body 等规则。
  - `fallback_no_proxy_not_minute_authority` 的 `105` 笔保持官方路径或先补 raw proxy，不能用 Stage861 首根、同价匹配或最终盈亏硬补。
  - Stage449 missing 的 `17` 笔可使用 Stage452 raw fallback 做源解释，但必须标记为 fallback，不得混成 Stage449 full-minute authority。
  - 如果要继续盘口规则，必须先取得与 official open 同源的 tick/order-book，或取得能解释 zero-volume open 的授权/vendor 源并重做 Stage073/074 级同源审计。

## 过拟合反思

- 运行前判断：否。本阶段是权威执行源选择，不新增交易规则、不新增阈值、不按盈亏筛选。
- 运行后判断：否，但把 source class 交易化会立刻变成过拟合。
- 原因：
  - 审计覆盖全部 `324` 个 initial opens 和全部 `219` 个 timestamp-ready raw proxy 样本。
  - 决策变量是“能否解释 official open 价格”，不是“盈亏好坏”。
  - 视觉上 source class 的贡献有右尾也有负尾，且 no-proxy 主要受历史覆盖影响，不能被当作市场状态。

## 继续价值反思

- 运行前判断：有价值。Stage073 已把异源 Tq top-book 与 official/raw/Stage449 open 的冲突暴露出来，必须先定权威源。
- 运行后判断：有价值，但价值在约束后续研究边界，而不是产生 alpha。
- 原因：
  - Stage074 证明 raw proxy bar authority 是当前唯一能全量解释 timestamp-ready official open 的源。
  - 同时确认这个源是 zero-volume、OHLC-flat price proxy，不是真实盘口/量能分钟 K；这会阻止我们用伪 volume/range/body 做过拟合规则。
  - 继续推进目标时，要么做 raw authority 下的低自由度 bar-level 候选，要么先补同源 tick/order-book；这比继续在异源 Tq tick 上挖特征更能穿越周期。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage074 状态、视觉结论和下一步执行源边界。
- 是否更新 `research/registry.md`：否，非合入/正式候选/重要突破。
- 是否追加根目录 `memory.md/back_log.md`：否，非重要突破，仅本线执行源审计推进。
