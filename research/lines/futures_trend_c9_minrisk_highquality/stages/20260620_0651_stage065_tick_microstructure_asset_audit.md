# Stage065 Tick 微观盘口数据资产审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 06:51 CST` 初次生成，`06:54 CST` 记录补写
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：点时化 tick/orderbook 数据资产审计；不是真实组合引擎，不生成交易规则
- 是否重要突破：否；证明路线技术可行但覆盖不足，不能形成候选
- 是否触发A/B：否；`strategy_rule_created=false`、`true_engine_run=false`

## 外部调研与判断

- 参考资料：
  - TqSdk 业务对象文档：`Quote/Tick` 暴露 `ask_price1/ask_volume1/bid_price1/bid_volume1` 等盘口字段。
  - TqSdk `DataDownloader` 文档：历史下载支持 `dur_sec=0` 的 tick 精度与任意 K 线周期，但属于专业版能力，需要权限与本地可得性验证。
  - vn.py GitHub `vnpy/trader/object.py`：`TickData` 数据结构含 bid/ask 盘口字段，生产栈技术上能承接点时化微观结构字段。
- 我的判断：盘口/价差/队列/成交流比继续切 no-follow、opening-range、breakeven、reentry candle 更接近“新增信息源”；但历史深度数据通常受权限和覆盖约束。当前只可先做覆盖审计，不能从局部样本直接提炼阈值。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage065_tick_microstructure_asset_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：固定 tick 微观结构审计 spec：
  - `median_spread_r`
  - `p90_spread_r`
  - `median_depth1_log`
  - `median_book_imbalance`
  - `median_directional_book_imbalance`
  - `volume_delta_target`
  - `amount_delta_target`
  - `open_interest_delta_target`
  - `directional_mid_move_r`
  - `directional_last_move_r`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：复用 Stage058 的 `54` 个 C9 reentry 事件；复用 Stage057 已落盘 raw tick 文件；复用 Stage046 官方资金曲线作为路径背景。
- 账户规模：官方正式 C9/15w，`150,000`。
- 成本口径：本阶段不新增成交、不改成本；官方基准沿用既有 true-engine 成本口径。
- 样本过滤：无交易过滤；仅按是否存在本地 tick 文件与有效 top-book 字段分为 `microstructure_ready/missing`。
- 策略/归因口径：
  - 官方基准：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once` / `Stage847-C9-15w`
  - 盘口审计：只读取重入当刻附近 tick bid/ask/last/volume/amount/open_interest，不使用最终盈亏生成交易规则。

## 结果

- 期末权益：官方基准 `39,176,437.60`；本阶段无新 C 版本期末权益。
- 总收益：官方基准 `26017.6251%`；本阶段无新 C 版本总收益。
- 最大回撤：官方基准 `-45.0827%`；本阶段不产生新最大回撤。
- Sharpe：官方基准 `1.6331`。
- 总滑点：官方基准 `2,730,130`。
- 总交易次数：官方基准 `787`。
- 胜率：官方基准日胜率 `53.2560%`，closed-lot 胜率参考 `36.0902%`。
- 其他关键指标：
  - `input_reentry_event_count=54`
  - `tick_file_exists_count=19`
  - `microstructure_ready_count=19`
  - `microstructure_ready_pct=35.1852%`
  - `microstructure_missing_count=35`
  - `ready_reentry_lot_pnl=975,455.00`
  - `missing_reentry_lot_pnl=1,721,842.00`
  - `ready_product_count=11`
  - `ready_year_count=5`
  - `download_plan_missing_event_count=35`
  - `max_abs_spearman_feature_pnl=0.4914`，来自 `open_interest_delta_target`，但样本只有 `19` 个，不可交易化。
  - `median_depth1_log` 对 reentry PnL 的 Spearman 为 `0.4362`；`directional_mid_move_r` 为 `-0.3763`；这些只作为覆盖后复验候选字段，不是规则。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage065_tick_microstructure_asset_audit/qmt_roll_stage065_c9_minrisk_tick_microstructure_asset_audit_report_stage065_tick_microstructure_asset_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage065_tick_microstructure_asset_audit/qmt_roll_stage065_c9_minrisk_tick_microstructure_asset_audit_summary_stage065_tick_microstructure_asset_audit_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage065_tick_microstructure_asset_audit/qmt_roll_stage065_c9_minrisk_tick_microstructure_asset_audit_decision_stage065_tick_microstructure_asset_audit_v1.json`
- event features：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage065_tick_microstructure_asset_audit/qmt_roll_stage065_c9_minrisk_tick_microstructure_asset_audit_event_microstructure_features_stage065_tick_microstructure_asset_audit_v1.csv`
- coverage summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage065_tick_microstructure_asset_audit/qmt_roll_stage065_c9_minrisk_tick_microstructure_asset_audit_coverage_summary_stage065_tick_microstructure_asset_audit_v1.csv`
- feature correlations：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage065_tick_microstructure_asset_audit/qmt_roll_stage065_c9_minrisk_tick_microstructure_asset_audit_feature_correlation_summary_stage065_tick_microstructure_asset_audit_v1.csv`
- download plan：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage065_tick_microstructure_asset_audit/qmt_roll_stage065_c9_minrisk_tick_microstructure_asset_audit_tick_expansion_download_plan_stage065_tick_microstructure_asset_audit_v1.csv`
- 官方路径 tick 覆盖资金曲线：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage065_tick_microstructure_asset_audit/qmt_roll_stage065_c9_minrisk_tick_microstructure_asset_audit_official_path_tick_coverage_chart_stage065_tick_microstructure_asset_audit_v1.png`
- 微观结构散点图：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage065_tick_microstructure_asset_audit/qmt_roll_stage065_c9_minrisk_tick_microstructure_asset_audit_microstructure_scatter_stage065_tick_microstructure_asset_audit_v1.png`
- 产品/年份覆盖热力图：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage065_tick_microstructure_asset_audit/qmt_roll_stage065_c9_minrisk_tick_microstructure_asset_audit_coverage_product_year_heatmap_stage065_tick_microstructure_asset_audit_v1.png`
- tick 微观结构 atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage065_tick_microstructure_asset_audit/qmt_roll_stage065_c9_minrisk_tick_microstructure_asset_audit_microstructure_atlas_stage065_tick_microstructure_asset_audit_v1.png`

## 结论

- 本阶段结论：`stage065_tick_microstructure_partial_data_asset_no_rule`。Stage057 既有 tick 文件证明点时化盘口路径技术上可落盘，且 atlas 能看到 bid1/ask1/last、depth、imbalance、OI 变化；但当前 ready 只有 `19/54`，且主要来自此前需要 tick fallback 的样本，覆盖偏置明显，不能由此生成 spread、depth、imbalance 或 OI 阈值。
- 是否进入下一步：进入，但只进入数据扩展，不进入 true engine 或 A/B。
- 下一步：按同一固定 spec 扩展 tick microstructure collection 到全部 `54` 个 C9 reentry 事件；完成后再扩到 Stage045 `timestamp_ready=1` 的 initial entry 事件。扩展完成前禁止把 `open_interest_delta_target`、spread、depth、book imbalance、mid move 等字段交易化。

## 过拟合反思

- 运行前判断：否。本阶段从 Stage064 明确的“新增点时化信息源”方向出发，先审计本地数据可得性，不调交易参数。
- 运行后判断：否。
- 原因：没有新增交易规则、没有 true engine、没有按盈亏筛品种/年份/方向、没有用 `19` 个 ready 样本提阈值；相反，结论明确拒绝从当前偏样本推规则。

## 继续价值反思

- 运行前判断：有价值。旧分钟价格路径候选已大量碰撞失败，盘口/队列/成交流是少数仍可能提供独立信息的方向。
- 运行后判断：仍有价值，但价值只在数据工程和固定 spec 复验。
- 原因：本地 tick 文件已经能生成点时化 top-book atlas，说明路线不是空想；但 `35/54` 缺口和 FG601 等单点右尾主导风险说明当前样本不足以决策。继续价值来自补齐覆盖，而不是从 `19` 个事件上拟合规则。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage065 结论和“盘口 route 只能数据先行”的边界。
- 是否更新 `research/registry.md`：否，本阶段不是跨线合入，且 registry 由合入者统一更新。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段无新候选回测、无正式候选、无重要突破。
