# Stage040 开仓成交 proxy 点时化审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 01:31 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：成交 proxy timestamp 覆盖审计 / 只读数据语义修复
- 是否重要突破：否。它修正后续 replay 可用样本边界，不产生新交易规则。
- 是否触发A/B：否。本阶段没有新策略版本接入正式候选，也不修改正式配置。

## 外部调研与判断

- 参考资料：
  - vn.py `BacktestingEngine` GitHub 源码：https://github.com/vnpy/vnpy_ctastrategy/blob/main/vnpy_ctastrategy/backtesting.py
  - Backtrader order execution 文档：https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/
  - Backtrader order/broker 文档：https://www.backtrader.com/docu/order/
  - QuantConnect LEAN trade fills 文档：https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/trade-fills/key-concepts
  - NautilusTrader backtesting 文档：https://nautilustrader.io/docs/latest/concepts/backtesting/
- 我的判断：成熟回测框架共同强调，成交必须按前向订单流、下一可用价格、明确的 OHLC/timestamp convention 和 fill model 定义；不能用最终成交价或最终盈亏反向挖分钟成交时点。Stage040 因此只审计 `_resolve_trade_price` 可重建的 proxy timestamp，不把缺口、首根同价或 Stage861 首根 open 写成交易规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage040_open_proxy_timestamp_reconstruction_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数。新增审计状态 `raw_exact_engine_selected`、`raw_exact_shadow_for_stage149_seed`、`no_engine_open_proxy_timestamp`。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage039 / Stage010 官方 C9/15w 输入，`2018-01-01` 至本地官方数据末端。
- 账户规模：`150000`
- 成本口径：官方 C9/15w 原始成本口径；本阶段不重跑候选策略。
- 样本过滤：Stage039 `initial_only_official_open_anchor` 中 `matched_initial_open_trade` 的 initial orders。
- 策略/归因口径：当前官方正式 C9/15w `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`；只审计 `_resolve_trade_price` 的 Stage149 seed proxy、raw proxy 和 fallback/missing proxy。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：closed-lot 胜率 `36.0902%`
- 其他关键指标：
  - matched initial orders：`324`
  - timestamp-ready initial orders：`219`，占 `67.5926%`
  - no-timestamp initial orders：`105`
  - Stage149 seed proxy orders：`114`
  - raw proxy orders：`105`
  - fallback/missing proxy orders：`105`
  - raw exact engine selected：`105`
  - raw exact shadow for Stage149 seed：`114`
  - Stage861 first-bar exact official：`84`
  - bound initial closed lots：`335`
  - timestamp-ready initial realized PnL：`32,390,657.50`
  - no-timestamp initial realized PnL：`7,968,239.10`
  - not-initial / unmatched realized PnL：`2,695,716.00`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage040_open_proxy_timestamp_reconstruction_audit/qmt_roll_stage040_c9_minrisk_open_proxy_timestamp_reconstruction_audit_report_stage040_open_proxy_timestamp_reconstruction_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage040_open_proxy_timestamp_reconstruction_audit/qmt_roll_stage040_c9_minrisk_open_proxy_timestamp_reconstruction_audit_summary_stage040_open_proxy_timestamp_reconstruction_audit_v1.csv`
- open proxy ledger：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage040_open_proxy_timestamp_reconstruction_audit/qmt_roll_stage040_c9_minrisk_open_proxy_timestamp_reconstruction_audit_open_proxy_ledger_stage040_open_proxy_timestamp_reconstruction_audit_v1.csv`
- closed lot binding：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage040_open_proxy_timestamp_reconstruction_audit/qmt_roll_stage040_c9_minrisk_open_proxy_timestamp_reconstruction_audit_closed_lot_proxy_binding_stage040_open_proxy_timestamp_reconstruction_audit_v1.csv`
- daily：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage040_open_proxy_timestamp_reconstruction_audit/qmt_roll_stage040_c9_minrisk_open_proxy_timestamp_reconstruction_audit_proxy_timestamp_contribution_curve_stage040_open_proxy_timestamp_reconstruction_audit_v1.csv`
- quality：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage040_open_proxy_timestamp_reconstruction_audit/qmt_roll_stage040_c9_minrisk_open_proxy_timestamp_reconstruction_audit_source_year_summary_stage040_open_proxy_timestamp_reconstruction_audit_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage040_open_proxy_timestamp_reconstruction_audit/qmt_roll_stage040_c9_minrisk_open_proxy_timestamp_reconstruction_audit_decision_stage040_open_proxy_timestamp_reconstruction_audit_v1.json`
- 资金/贡献曲线：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage040_open_proxy_timestamp_reconstruction_audit/qmt_roll_stage040_c9_minrisk_open_proxy_timestamp_reconstruction_audit_proxy_timestamp_path_chart_stage040_open_proxy_timestamp_reconstruction_audit_v1.png`
- 分年分布图：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage040_open_proxy_timestamp_reconstruction_audit/qmt_roll_stage040_c9_minrisk_open_proxy_timestamp_reconstruction_audit_source_year_distribution_chart_stage040_open_proxy_timestamp_reconstruction_audit_v1.png`
- atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage040_open_proxy_timestamp_reconstruction_audit/qmt_roll_stage040_c9_minrisk_open_proxy_timestamp_reconstruction_audit_proxy_timestamp_atlas_page001_stage040_open_proxy_timestamp_reconstruction_audit_v1.png` 至 `page003`

## 结论

- 本阶段结论：`stage040_proxy_timestamp_partial_reconstruction_no_trade_rule`。官方 initial open 中 `219/324` 可由 raw proxy 或 raw shadow 精确重建成交开盘窗口，但 `105/324` 仍是 fallback/missing proxy，不能用于分钟开仓规则测试。
- 是否进入下一步：是，但只能进入更窄的账本一致性审计，不进入策略候选。
- 下一步：只在 `timestamp_ready=1` 的 initial orders 上做 replay 一致性子集审计，确认 C9/C2 事件、成交锚点和 same-exit PnL 在可点时样本内是否可复验；若要纳入 `fallback_daily_next_open_no_proxy`，必须先补 raw proxy 或正式可执行窗口。

## 视觉观察

- path chart 显示 timestamp-ready initial lots 和 no-timestamp initial lots 都承担过重要 PnL，不能因为历史贡献好坏把有无 timestamp 当成信号筛选条件。
- source-year chart 显示无 timestamp 缺口主要集中在 `2018-2019`，`2020` 后主要由 raw/Stage149 proxy 解释；这更像数据覆盖/成交源演进，不是市场状态。
- atlas 显示 raw-ready 样本能画出可解释的 raw/seed proxy 价格线；no-timestamp 样本即使 Stage861 首根同价，也没有 `_resolve_trade_price` 证据，不能硬补成可执行成交时点。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段不新增规则、不筛年份/品种/方向/时段、不用最终盈亏选样本，只审计成交源覆盖和 timestamp 可重建性。若后续把 `timestamp_ready/no_timestamp` 当成信号好坏标签，或用首根同价补缺口，就会转为过拟合和数据泄漏。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有。
- 原因：Stage039 已证明 official open anchor 能修复事件语义，但它不是可执行时点；Stage040 进一步确认 `219` 笔可以点时，`105` 笔不能点时。下一步在 timestamp-ready 子集上审计 replay，一方面能避免错误锚点，另一方面能判断分钟级规则研究是否还有可靠账本底座。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage040 摘要和下一步边界。
- 是否更新 `research/registry.md`：否。本阶段不是正式候选、重要突破或路线迁移。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是本线内部账本审计，不改变正式版或跨线结论。
