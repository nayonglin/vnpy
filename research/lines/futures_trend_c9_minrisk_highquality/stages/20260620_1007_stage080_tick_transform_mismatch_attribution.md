# Stage080 tick transform mismatch attribution

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 10:07 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：Stage079 后 TqSdk dur0 tick transform mismatch 归因闸门，不是交易规则
- 是否重要突破：否；但属于关闭错误数据路线的硬闸门
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk DataDownloader 官方文档：`https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.tools.download.html`。历史数据支持 tick 下载，`dur_sec=0` 为 tick；这只证明数据通路，不证明同源 transform。
  - TqSdk 行情与历史数据文档：`https://tqsdk-python.readthedocs.io/en/latest/usage/mddatas.html`。`get_tick_serial` 的 tick 序列包含 `last_price`、买卖一档、成交量、持仓等字段，可用于行情序列归因。
  - vn.py `object.py`：`https://github.com/vnpy/vnpy/blob/master/vnpy/trader/object.py`。`TickData` 的 last trade/orderbook snapshot 与 `BarData` 的 OHLCV 是不同层级对象。
  - vn.py `utility.py`：`https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py`。`BarGenerator.update_tick` 的分钟 bar open 应来自新分钟第一笔 `last_price`。
- 我的判断：
  - 如果 Stage449/raw open 是可交易 tick transform，最少应该被一个统一、可解释、非样本选择的字段或 transform 复现。
  - `first_tick_state_union=28/28` 只是把 `last/bid/ask/average/highest/lowest` 混成集合后的诊断上界；它不是可执行 transform，更不是交易信号。
  - Stage080 证明 Tq dur0 tick 可以做 TCA 和成交质量观察，但不能作为同源 initial-entry 微观规则数据源。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage080_tick_transform_mismatch_attribution.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无；全部读取 Stage079 本地落盘 tick 和 audit。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage079 `28` 行 fixed manifest，覆盖 `2020-2026`，每年 `4` 行；官方资金曲线继承 Stage045/C9 15w。
- 账户规模：当前官方 C9/15w，`150,000`。
- 成本口径：沿用官方 C9/15w 既有成本，不新增滑点/手续费假设。
- 样本过滤：
  - 不下载新数据。
  - 不按收益、回撤、品种、方向、交易所筛选。
  - 固定比较 Stage079 的 `28` 行 target minute tick。
- 策略/归因口径：
  - 预声明候选 transform：`first_last`、`first_bid1`、`first_ask1`、`first_mid1`、`first_average`、`first_highest`、`first_lowest`、`last_last`、`target_min_last`、`target_max_last`。
  - 诊断上界：minute 内任意 `last/bid/ask` touch、official 是否落入任意 bid/ask spread、official 是否等于第一 tick 的任意状态字段。
  - 不改变官方交易，不写真引擎，不新增开仓、减仓、恢复风险或退出规则，不连接 CTP，不调用订单 API。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - decision：`stage080_no_unified_topbook_transform_tq_tick_downgraded_to_tca_no_rule`
  - next_step：`stop_tq_tick_as_same_source_microstructure_and_use_only_tca_or_authorized_vendor_tick`
  - manifest size / year count：`28 / 7`
  - best deterministic transform：`first_average`
  - best deterministic exact：`17 / 28`
  - strict BarGenerator-compatible `first_last` exact：`8 / 28`
  - `first_bid1` exact：`11 / 28`
  - `first_lowest` exact：`13 / 28`
  - minute 内任意 `last/bid/ask` touch：`24 / 28`
  - official inside any spread：`24 / 28`
  - first tick state union exact：`28 / 28`
  - topbook 或 spread miss：`4 / 28`
  - transform class：`strict_vnpy_first_last_exact=8`，`topbook_touch_but_not_first_last=16`，`first_tick_state_only_not_topbook=4`
  - rule candidate allowed：`0`

## 视觉观察

- official path transform class chart：官方资金曲线与回撤曲线保持不变；三类 transform 状态分布在长期资金路径上，不是收益信号。底部贡献曲线只是 manifest 分布，不能把红/橙/绿类别当成过滤条件。
- candidate transform chart：只有诊断上界 `first_tick_state_union` 达到 `28/28`；可执行 top-book 相关字段全部失败，严格 `first_last` 只有 `8/28`。最佳单字段 `first_average=17/28` 也没有跨年全满。
- year heatmap：`first_last` 在 `2021` 为 `0/4`，`first_average` 只有 `2026` 为 `4/4`，`first_bid1` 在 `2023` 为 `0/4`；不存在跨年稳定的单字段 transform。
- mismatch tick atlas：`cu2303/fu2405/lc2505/MA605` 等 topbook/spread miss 样本中，official/raw 线落在第一 tick 的 `lowest/average` 一类状态字段，而不在 last/bid/ask 可成交路径里。这更像 60s price proxy 或 cumulative tick state 的生成痕迹，不是可交易盘口规则。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage080_tick_transform_mismatch_attribution/qmt_roll_stage080_c9_minrisk_tick_transform_mismatch_attribution_report_stage080_tick_transform_mismatch_attribution_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage080_tick_transform_mismatch_attribution/qmt_roll_stage080_c9_minrisk_tick_transform_mismatch_attribution_summary_stage080_tick_transform_mismatch_attribution_v1.csv`
- detail：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage080_tick_transform_mismatch_attribution/qmt_roll_stage080_c9_minrisk_tick_transform_mismatch_attribution_detail_stage080_tick_transform_mismatch_attribution_v1.csv`
- candidate matrix：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage080_tick_transform_mismatch_attribution/qmt_roll_stage080_c9_minrisk_tick_transform_mismatch_attribution_candidate_matrix_stage080_tick_transform_mismatch_attribution_v1.csv`
- year matrix：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage080_tick_transform_mismatch_attribution/qmt_roll_stage080_c9_minrisk_tick_transform_mismatch_attribution_year_matrix_stage080_tick_transform_mismatch_attribution_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage080_tick_transform_mismatch_attribution/qmt_roll_stage080_c9_minrisk_tick_transform_mismatch_attribution_decision_stage080_tick_transform_mismatch_attribution_v1.json`
- official path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage080_tick_transform_mismatch_attribution/qmt_roll_stage080_c9_minrisk_tick_transform_mismatch_attribution_official_path_transform_class_chart_stage080_tick_transform_mismatch_attribution_v1.png`
- candidate transform chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage080_tick_transform_mismatch_attribution/qmt_roll_stage080_c9_minrisk_tick_transform_mismatch_attribution_candidate_transform_chart_stage080_tick_transform_mismatch_attribution_v1.png`
- year heatmap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage080_tick_transform_mismatch_attribution/qmt_roll_stage080_c9_minrisk_tick_transform_mismatch_attribution_year_transform_heatmap_stage080_tick_transform_mismatch_attribution_v1.png`
- mismatch tick atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage080_tick_transform_mismatch_attribution/qmt_roll_stage080_c9_minrisk_tick_transform_mismatch_attribution_mismatch_tick_atlas_stage080_tick_transform_mismatch_attribution_v1.png`

## 结论

- 本阶段结论：`stage080_no_unified_topbook_transform_tq_tick_downgraded_to_tca_no_rule`
- 是否进入下一步：是，但不是沿 Tq tick 写规则，而是换数据源或回到已校准 replay 子集。
- 下一步：
  - 第一优先：停止把 Tq dur0 tick 当作 Stage449/raw 同源微观结构源；只允许做 TCA、成交质量观察或 forward watch。
  - 第二优先：若继续盘口/微观路线，必须取得授权 vendor/raw exchange tick/quote/depth，或找到 Stage449/raw 生成端真实 `open`/quote transform 字段；拿到前不能写真引擎。
  - 第三优先：若继续本目标，应回到 Stage045 timestamp-ready replay 子集，提出一个不依赖 tick 同源性的第一性候选；fallback/no-proxy 样本保持官方路径。
  - 明确禁止：不得把 `first_tick_state_union`、`first_average`、topbook touch、inside spread、exact/mismatch、产品、年份、方向或交易所写成开仓过滤、最小风险、恢复仓或退出规则。

## 过拟合反思

- 运行前判断：否。本阶段只验证固定 manifest 的 transform，不看收益选样，不写交易规则。
- 运行后判断：否，并且进一步降低过拟合风险。
- 原因：
  - 结果没有为了 exact 去挑字段；最佳单字段只有 `17/28`，严格 first-last 只有 `8/28`，因此直接关闭而不是救参。
  - `first_tick_state_union=28/28` 被明确降级为诊断上界，因为它混合多个字段，无法作为统一可执行口径。
  - 图形证据显示 mismatch 不稳定且跨年不满，不存在能穿越周期的 transform。

## 继续价值反思

- 运行前判断：有价值。Stage079 留下的核心问题就是 mismatch 是否有统一 transform；不回答这个问题会在伪盘口数据上反复打转。
- 运行后判断：有价值，但价值在于关闭错误路线。
- 原因：
  - 现在可以明确 Tq tick 通路可用但不同源，不应再把它当 initial-entry 微观规则底座。
  - 关闭该路线能避免后续在 tick index、bid/ask 侧、累计 high/low/average 字段上过拟合。
  - 下一步应把精力转到授权同源 tick/quote/depth，或回到 Stage045 已校准 replay 子集设计真正普世候选。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage080 状态、视觉结论和 Tq tick 降级边界。
- 是否更新 `research/registry.md`：否，非合入/正式候选/重要突破。
- 是否追加根目录 `memory.md/back_log.md`：否，非重要突破，仅本线数据路线关闭。
