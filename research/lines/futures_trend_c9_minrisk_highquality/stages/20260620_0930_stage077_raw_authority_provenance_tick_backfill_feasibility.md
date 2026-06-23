# Stage077 raw authority 来源追溯与 tick 回填可行性审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 09:30 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：Stage076 后 R2 同源 tick/orderbook 数据工程可行性审计，不是交易规则
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk DataDownloader 官方文档：`https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.tools.download.html`。文档说明历史下载支持 tick 级别和任意 K 线周期，`dur_sec=0` 为 Tick 数据；但它需要专业版/授权使用。
  - vn.py `object.py`：`https://github.com/vnpy/vnpy/blob/master/vnpy/trader/object.py`。`TickData` 与 `BarData` 是不同数据对象，TickData 包含 last trade、orderbook snapshot 和统计字段；BarData 是周期 OHLCV。
  - vn.py README/Gitee：`https://gitee.com/vnpy/vnpy/blob/master/README_ENG.md?skip_mobile=true`。Chart/data/recorder 模块说明历史数据、实时 Tick 推送和记录是不同链路。
  - LSEG Tick History：`https://www.lseg.com/en/data-analytics/market-data/data-feeds/tick-history`。机构级历史 tick/quote/depth 通常需要专门授权、字段选择和交付机制。
- 我的判断：
  - Stage448/449 的来源链是 `TqBacktest + get_kline_serial(duration_seconds=60)` 的 60 秒分钟 K 缓存，能解释官方 open 价格，但不是同源 tick/orderbook。
  - TqSdk `dur_sec=0` 或 vendor tick 是下一步可行出口，但必须先证明能按同一 transform 重建 Stage449/raw open；同 vendor 不等于同 transform。
  - 现有 Tq tick/top-book 批次已有 `60` 个锚点、`14` 个 mismatch，当前只能做 TCA，不允许直接写 spread/depth/imbalance/last move 规则。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage077_raw_authority_provenance_tick_backfill_feasibility.py`
- 新增输出目录：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage077_raw_authority_provenance_tick_backfill_feasibility/`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：继承 Stage074/076 全量 `324` 个 initial opens，覆盖 `2018-2026`。
- 账户规模：当前官方 C9/15w，`150,000`。
- 成本口径：沿用官方 C9/15w 既有成本，不新增滑点/手续费假设。
- 样本过滤：
  - 固定读取 Stage074 source decision audit、Stage076 summary、Stage045 official curve。
  - 固定读取 Stage449 full minute bars/status/detail 与 Stage448/452/501/502 源码链路。
  - 不按收益、年份、品种、方向、交易所或时段筛选。
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
  - decision：`stage077_r2_requires_same_source_tick_transform_no_rule`
  - next_step：`acquire_same_source_tick_or_authorized_external_preentry_source_before_rules`
  - initial opens：`324`
  - timestamp-ready：`219`
  - fallback no-proxy：`105`
  - raw anchor exact / zero-degenerate：`219 / 219`
  - Stage449 anchor exact / zero-degenerate：`202 / 202`
  - raw authority tick/orderbook local files：`0`
  - same-source tick/orderbook ready：`0`
  - existing Tq proxy ready/exact/mismatch：`60 / 46 / 14`
  - rule_candidate_allowed_source_count：`0`
  - Stage449 total bar rows：`1,453,601`
  - Stage449 zero-volume rate：`100.0000%`
  - Stage449 degenerate-OHLC rate：`100.0000%`
  - broker10 峰值：`111.7365%`

## 来源链结论

- `S1_stage448_449_tqsdk_backtest_60s_minute`：本地 evidence `202`，总分钟条 `1,453,601`；源码检测到 `TqBacktest` 与 `duration_seconds=60`，未检测到 tick API；same-source price authority 为 `1`，tick/orderbook 为 `0`，rule allowed 为 `0`。
- `S2_raw_authority_roots_minute_files`：本地 minute 文件 `274`，解释 raw anchor `219`；但全是 price boundary，不是微观结构源。
- `S3_stage452_1455_proxy_backfill`：解释 fallback gap `17`，属于覆盖补丁，不是 alpha。
- `S4_existing_tq_tick_batch`：已有 Tq tick/top-book evidence `60`，但 exact 仅 `46`，mismatch `14`；same transform 未验证。
- `S5_same_source_tick_orderbook`：本地 evidence `0`，这是当前真正缺失的 R2。
- `S6_fallback_no_proxy_gap`：`105` 笔 no-proxy 是覆盖缺口，只能补数，不能作为交易状态。

## 视觉观察

- official path provenance chart：官方资金曲线和回撤曲线保持 Stage847-C9-15w 原路径；最大回撤仍在 `2022-2023` 深水区。第三层 provenance contribution 显示 `stage449_raw_price_boundary` 承载主要右尾台阶，`stage452_raw_fallback_gap` 偏负，`fallback_no_proxy_gap` 很小；这说明 source route 与历史覆盖/右尾分布绑定，不是可交易 alpha。
- provenance readiness atlas：`S1/S2/S3` 只有 historical、same-source price authority 和 same-transform price proxy 为 `1`，nondegenerate anchor 与 tick/orderbook 全为 `0`；`S4` 有 tick/orderbook 但 same-source price authority 与 transform verified 为 `0`；所有来源的 `rule_candidate_allowed` 都是 `0`。
- bar quality chart：anchor evidence 显示 raw exact `219` 与 raw zero+degenerate `219` 完全重合，Stage449 exact `202` 与 Stage449 zero+degenerate `202` 完全重合；Stage449 全量 `1,453,601` 行分钟条 zero-volume rate 与 degenerate-OHLC rate 均为 `100%`，没有 bid/ask 或 last_price 字段。

## 输出文件

- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage077_raw_authority_provenance_tick_backfill_feasibility/qmt_roll_stage077_c9_minrisk_raw_authority_provenance_tick_backfill_feasibility_summary_stage077_raw_authority_provenance_tick_backfill_feasibility_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage077_raw_authority_provenance_tick_backfill_feasibility/qmt_roll_stage077_c9_minrisk_raw_authority_provenance_tick_backfill_feasibility_decision_stage077_raw_authority_provenance_tick_backfill_feasibility_v1.json`
- source lineage：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage077_raw_authority_provenance_tick_backfill_feasibility/qmt_roll_stage077_c9_minrisk_raw_authority_provenance_tick_backfill_feasibility_source_lineage_stage077_raw_authority_provenance_tick_backfill_feasibility_v1.csv`
- action scorecard：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage077_raw_authority_provenance_tick_backfill_feasibility/qmt_roll_stage077_c9_minrisk_raw_authority_provenance_tick_backfill_feasibility_action_scorecard_stage077_raw_authority_provenance_tick_backfill_feasibility_v1.csv`
- bar quality：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage077_raw_authority_provenance_tick_backfill_feasibility/qmt_roll_stage077_c9_minrisk_raw_authority_provenance_tick_backfill_feasibility_bar_quality_summary_stage077_raw_authority_provenance_tick_backfill_feasibility_v1.csv`
- official path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage077_raw_authority_provenance_tick_backfill_feasibility/qmt_roll_stage077_c9_minrisk_raw_authority_provenance_tick_backfill_feasibility_official_path_provenance_chart_stage077_raw_authority_provenance_tick_backfill_feasibility_v1.png`
- readiness atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage077_raw_authority_provenance_tick_backfill_feasibility/qmt_roll_stage077_c9_minrisk_raw_authority_provenance_tick_backfill_feasibility_provenance_readiness_atlas_stage077_raw_authority_provenance_tick_backfill_feasibility_v1.png`
- bar quality chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage077_raw_authority_provenance_tick_backfill_feasibility/qmt_roll_stage077_c9_minrisk_raw_authority_provenance_tick_backfill_feasibility_bar_quality_chart_stage077_raw_authority_provenance_tick_backfill_feasibility_v1.png`

## 结论

- 本阶段结论：`stage077_r2_requires_same_source_tick_transform_no_rule`
- 是否进入下一步：是，但仍然不能写交易规则。
- 下一步：
  - 第一优先：尝试获取 TqSdk `dur_sec=0` 或等价同 vendor tick，但必须把 tick/orderbook 聚合回 Stage449 60s transform，并证明 initial open anchor exact；若仍 mismatch，只能 TCA。
  - 第二优先：若无法取得同源 tick，寻找授权 vendor/raw exchange 历史 tick/quote/depth，并先做 symbology、时间戳、合约映射和 exact replay 审计。
  - 第三优先：补 `105` 笔 no-proxy raw authority 覆盖，但只作为覆盖治理。
  - 第四优先：换真正外生、入场前可见、覆盖完整的数据源，并先做点时化覆盖审计。
  - 明确禁止：不得把 Stage449/raw source class、zero-volume、degenerate OHLC、Stage452 fallback、Tq tick ready/exact/mismatch、产品、年份、方向写成开仓过滤、最小风险、恢复仓或退出规则。

## 过拟合反思

- 运行前判断：否。本阶段只审计数据来源链、字段语义和可回填性，不做收益优化。
- 运行后判断：否，并且进一步降低过拟合风险。
- 原因：
  - 判定条件是来源可追溯、same-source transform、tick/orderbook 与 nondegenerate OHLCV 是否存在，而不是某类样本收益好坏。
  - 视觉图虽然显示 Stage449 source class 承载主要右尾，但本阶段明确把它判为 source distribution，不允许交易化。
  - 所有 source/action 的可写规则权限均为 `0`。

## 继续价值反思

- 运行前判断：有价值。Stage076 指出 R2 是第一优先出口，但还需要确认 raw authority 的真实来源链。
- 运行后判断：有价值，但价值从“立刻研究分钟 K 规则”转为“先补同源数据资产”。
- 原因：
  - Stage077 把 raw authority 锁定为 TqSdk 60s price proxy，证明现有数据不能支持真实分钟 K 进出场规则。
  - 下一步验收门槛清晰：同源 tick/orderbook 必须能重建 Stage449/raw open exact，不能只凭同 vendor 或少量 tick 文件进入策略。
  - 这符合“能穿越周期”的要求：先保证可见信息和数据语义真实，再谈普世规则。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage077 状态、视觉结论和下一步数据工程门槛。
- 是否更新 `research/registry.md`：否，非合入/正式候选/重要突破。
- 是否追加根目录 `memory.md/back_log.md`：否，非重要突破，仅本线数据来源追溯审计。
