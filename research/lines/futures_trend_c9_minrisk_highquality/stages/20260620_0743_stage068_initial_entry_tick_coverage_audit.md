# Stage068 初始开仓 tick/盘口覆盖审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 07:43 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：数据覆盖/执行可行性审计，不是交易规则
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - HftBacktest GitHub / docs：完整 tick、L2/L3 order book、feed/order latency、queue position 是短周期成交回放的关键要素。
  - Deep Limit Order Book Forecasting：LOB 预测能力不等于可交易成交能力，需用完整交易可执行框架评估。
  - Columbia optimal execution in LOB：短时间成交成本受盘口队列、深度、价差、订单流不平衡和订单规模影响。
  - CME liquidity note：单看 displayed depth 可能误判流动性，应结合成交量密度、冲击成本等指标。
- 我的判断：
  - 初始开仓盘口路线有研究价值，但第一步只能做“可执行性/流动性覆盖”审计，不能把 5 笔 smoke tick 的相关性当成方向信号。
  - 盘口字段应优先用于价差、深度、订单规模相对盘口容量和价格基准一致性检查；在全量覆盖和价格基准归一前，不进入 true engine、A/B 或候选规则。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage068_initial_entry_tick_coverage_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `STAGE068_ENABLE_TQSDK`：默认 `0`，避免默认批量联网下载引入临时样本偏差。
  - `STAGE068_MAX_EVENTS`：默认 `0`，代表全量计划；本次曾以 `5` 做 smoke 下载，随后恢复全量输出。
  - `STAGE068_DOWNLOAD_WINDOW_MINUTES=3`
  - `STAGE068_MAX_SECONDS_PER_EVENT=60`
  - `STAGE068_TICK_DATA_LENGTH=12000`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`Stage045 timestamp_ready=1` 初始开仓子集，`2020-01-09` 至 `2026-03-16`。
- 账户规模：官方 C9/15w，`150,000`。
- 成本口径：沿用官方 Stage045/Stage046 基准成本，不新增交易成本假设。
- 样本过滤：
  - 仅使用 Stage045 `full_event_sync_exact=1` 的 `219` 笔初始开仓。
  - Stage044 variant 固定为 `stage827_directional_c2_stop_start0_stop_first`。
  - Stage047 realized PnL 仅作 open trade 贡献绑定，不用作规则训练。
- 策略/归因口径：
  - 不改变官方交易。
  - 不新增开仓/减仓/退出规则。
  - tick 下载窗口为 initial-entry anchor 前后各 `3` 分钟，target minute 为 anchor 所在分钟。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - planned initial entries：`219`
  - microstructure ready：`5`
  - missing：`214`
  - ready rate：`2.2831%`
  - download status：`cached_stage068=5`，`planned_not_downloaded=214`
  - ready tick 的价格锚点 exact：`0/5`
  - ready tick 的价格锚点 mismatch：`5/5`
  - all initial entries realized PnL：`32,390,657.50`
  - positive PnL：`50,846,690.00`
  - negative PnL abs：`18,456,032.50`
  - timestamp class：
    - `raw_timestamp_in_candidate_date_not_official`：`140` 笔，PnL `27,462,937.70`
    - `raw_timestamp_in_official_date`：`64` 笔，PnL `6,283,968.50`
    - `missing_stage861_timestamp_bar`：`15` 笔，PnL `-1,356,248.70`

## 视觉观察

- 官方资金曲线覆盖图显示：219 笔初始开仓计划覆盖了主要权益台阶，说明初始开仓盘口路线如果要继续，必须做全量数据覆盖；当前 5 笔 ready 只集中在 `2020` 初段，不能代表全周期。
- 贡献曲线显示：missing tick 样本承载几乎全部初始开仓 PnL，当前 ready PnL 仅 `-5,320`，不能据此判断盘口特征与收益关系。
- 年份/产品族热图显示：计划样本跨 `2020-2026`、`10` 个产品族，贡献不集中于单一年份或单一产品族；这支持全量补数，不支持从少量已下载样本局部归纳。
- tick atlas 显示：5 笔 smoke tick 均有 bid1/ask1/last 序列和有效 top-book 行，但 official open price 与 raw tick mid/last 明显不完全同基准；下一步必须先做价格基准归一或价差/深度类相对特征隔离，不能直接做短滑点规则。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage068_initial_entry_tick_coverage_audit/qmt_roll_stage068_c9_minrisk_initial_entry_tick_coverage_audit_report_stage068_initial_entry_tick_coverage_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage068_initial_entry_tick_coverage_audit/qmt_roll_stage068_c9_minrisk_initial_entry_tick_coverage_audit_summary_stage068_initial_entry_tick_coverage_audit_v1.csv`
- plan：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage068_initial_entry_tick_coverage_audit/qmt_roll_stage068_c9_minrisk_initial_entry_tick_coverage_audit_initial_entry_tick_plan_stage068_initial_entry_tick_coverage_audit_v1.csv`
- features：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage068_initial_entry_tick_coverage_audit/qmt_roll_stage068_c9_minrisk_initial_entry_tick_coverage_audit_initial_entry_microstructure_features_stage068_initial_entry_tick_coverage_audit_v1.csv`
- download status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage068_initial_entry_tick_coverage_audit/qmt_roll_stage068_c9_minrisk_initial_entry_tick_coverage_audit_download_status_stage068_initial_entry_tick_coverage_audit_v1.csv`
- path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage068_initial_entry_tick_coverage_audit/qmt_roll_stage068_c9_minrisk_initial_entry_tick_coverage_audit_official_path_coverage_chart_stage068_initial_entry_tick_coverage_audit_v1.png`
- heatmap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage068_initial_entry_tick_coverage_audit/qmt_roll_stage068_c9_minrisk_initial_entry_tick_coverage_audit_year_family_coverage_heatmap_stage068_initial_entry_tick_coverage_audit_v1.png`
- atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage068_initial_entry_tick_coverage_audit/qmt_roll_stage068_c9_minrisk_initial_entry_tick_coverage_audit_microstructure_atlas_stage068_initial_entry_tick_coverage_audit_v1.png`

## 结论

- 本阶段结论：`stage068_initial_entry_tick_coverage_plan_created_download_required_no_rule`
- 是否进入下一步：是，但只能作为数据工程/覆盖审计继续。
- 下一步：
  - 先按固定 plan 分批或全量下载剩余 `214` 笔 initial-entry tick。
  - 下载后先复验 `anchor_price_exact / first_mid_delta_r`，明确 raw tick 与官方回放价格基准是否需要归一化。
  - 只有在覆盖和价格基准处理清楚后，才允许做 initial-entry microstructure stability audit；仍禁止阈值扫描、产品/年份/方向补丁或 true engine。

## 过拟合反思

- 运行前判断：否。本阶段不是根据历史亏损样本设计规则，而是把 Stage045 已同步事件转成 tick 覆盖计划。
- 运行后判断：否，但如果立刻解释 5 笔 smoke tick 的 Spearman 或方向性盘口形态，就会过拟合。
- 原因：
  - 5 笔 ready 只用于验证下载链路，不足以形成统计或交易判断。
  - 已发现 raw tick 与官方 open price 存在价格基准 mismatch，进一步降低了直接交易化的可信度。

## 继续价值反思

- 运行前判断：有价值。reentry 盘口规则化关闭后，initial entry 是更靠前、更接近“高质量信号用最小风险参与”的可执行检查点。
- 运行后判断：仍有价值，但价值在数据覆盖和 TCA 纪律，不在当前样本出规则。
- 原因：
  - 219 笔初始开仓贡献覆盖主要权益台阶，若能形成全量盘口资产，可以审计 C9 初始成交质量和流动性压力。
  - 价格基准 mismatch 是真实阻塞，越早暴露越能避免后续错误规则。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage068 状态和下一步边界。
- 是否更新 `research/registry.md`：否，非合入/正式候选/重要突破。
- 是否追加根目录 `memory.md/back_log.md`：否，非重要突破，仅本线数据资产推进。
