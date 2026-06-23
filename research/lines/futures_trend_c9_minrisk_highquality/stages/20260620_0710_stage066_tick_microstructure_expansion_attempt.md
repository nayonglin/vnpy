# Stage066 Tick 微观盘口全量扩展尝试

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 07:10 CST` 初次生成，`07:12 CST` 记录补写
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：点时化 tick/orderbook 数据资产扩展；不是真实组合引擎，不生成交易规则
- 是否重要突破：是，数据资产突破；不是策略收益/回撤突破，也不是正式候选
- 是否触发A/B：否；`strategy_rule_created=false`、`true_engine_run=false`

## 外部调研与判断

- 参考资料：
  - TqSdk 业务对象文档：`Tick` 和 `Quote` 均暴露 `ask_price1/ask_volume1/bid_price1/bid_volume1`、`volume`、`amount`、`open_interest` 等盘口/成交字段。
  - TqSdk `DataDownloader` 文档：`dur_sec=0` 为 tick 数据，历史下载支持 tick 级精度，但属于专业版/授权能力。
  - vn.py GitHub `vnpy/trader/object.py`：`TickData` 含 last trade、orderbook snapshot 和 intraday market statistics，字段包括 bid/ask 价格与挂单量。
- 我的判断：盘口 route 和生产栈字段语义兼容，本地 TqBacktest 也能补齐这批 reentry tick；但数据补齐只是必要条件，不是交易规则。微观结构要进入策略，必须先证明跨年、跨产品、视觉上不会切断 C9 右尾。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage066_tick_microstructure_expansion_attempt.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `STAGE066_MAX_EVENTS`：默认 `0`，表示处理全部 Stage065 缺口。
  - `STAGE066_MAX_SECONDS_PER_EVENT`：默认 `75`，单事件历史 tick 回放超时保护。
  - `STAGE066_TICK_DATA_LENGTH`：默认 `12000`。
  - `STAGE066_ENABLE_TQSDK`：默认 `1`。
  - 固定沿用 Stage065 微观结构 spec：spread、depth1、book imbalance、volume/amount/OI delta、mid/last move。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：复用 Stage058 的 `54` 个 C9 reentry 事件；对 Stage065 缺失的 `35` 个事件补 TqBacktest tick。
- 账户规模：官方正式 C9/15w，`150,000`。
- 成本口径：本阶段不新增成交、不改成本；官方基准沿用既有 true-engine 成本口径。
- 样本过滤：无交易过滤；仅按 tick top-book 是否可用做数据覆盖状态。
- 策略/归因口径：
  - 官方基准：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once` / `Stage847-C9-15w`
  - Stage066：先读取 Stage065 缺口计划，再用本地 `tqsdk` 凭证通过 `TqBacktest + get_tick_serial` 获取重入前后约 `6` 分钟 tick，输出到本线 `stage066` raw tick 目录；凭证只记录 present/length，不写用户名或密码。

## 结果

- 期末权益：官方基准 `39,176,437.60`；本阶段无新 C 版本期末权益。
- 总收益：官方基准 `26017.6251%`；本阶段无新 C 版本总收益。
- 最大回撤：官方基准 `-45.0827%`；本阶段不产生新最大回撤。
- Sharpe：官方基准 `1.6331`。
- 总滑点：官方基准 `2,730,130`。
- 总交易次数：官方基准 `787`。
- 胜率：官方基准日胜率 `53.2560%`，closed-lot 胜率参考 `36.0902%`。
- 其他关键指标：
  - `download_plan_event_count=35`
  - `download_attempt_event_count=35`
  - 下载状态：`extracted=34`，`cached_stage066=1`
  - `stage066_ready_count=35`
  - `microstructure_ready_count=54`
  - `microstructure_ready_pct=100.0000%`
  - `microstructure_missing_count=0`
  - `ready_reentry_lot_pnl=2,697,297.00`
  - `missing_reentry_lot_pnl=0.00`
  - `ready_product_count=16`
  - `ready_year_count=9`
  - `max_abs_spearman_feature_pnl=0.3605`，来自 `open_interest_delta_target`。
  - 单变量 Spearman：`open_interest_delta_target=-0.3605`、`directional_mid_move_r=-0.1807`、`median_spread_r=0.1757`、`median_directional_book_imbalance=0.1148`、`median_depth1_log=0.0293`。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage066_tick_microstructure_expansion_attempt/qmt_roll_stage066_c9_minrisk_tick_microstructure_expansion_attempt_report_stage066_tick_microstructure_expansion_attempt_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage066_tick_microstructure_expansion_attempt/qmt_roll_stage066_c9_minrisk_tick_microstructure_expansion_attempt_summary_stage066_tick_microstructure_expansion_attempt_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage066_tick_microstructure_expansion_attempt/qmt_roll_stage066_c9_minrisk_tick_microstructure_expansion_attempt_decision_stage066_tick_microstructure_expansion_attempt_v1.json`
- download status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage066_tick_microstructure_expansion_attempt/qmt_roll_stage066_c9_minrisk_tick_microstructure_expansion_attempt_download_status_stage066_tick_microstructure_expansion_attempt_v1.csv`
- event features：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage066_tick_microstructure_expansion_attempt/qmt_roll_stage066_c9_minrisk_tick_microstructure_expansion_attempt_event_microstructure_features_stage066_tick_microstructure_expansion_attempt_v1.csv`
- coverage summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage066_tick_microstructure_expansion_attempt/qmt_roll_stage066_c9_minrisk_tick_microstructure_expansion_attempt_coverage_summary_stage066_tick_microstructure_expansion_attempt_v1.csv`
- feature correlations：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage066_tick_microstructure_expansion_attempt/qmt_roll_stage066_c9_minrisk_tick_microstructure_expansion_attempt_feature_correlation_summary_stage066_tick_microstructure_expansion_attempt_v1.csv`
- 官方路径 tick 覆盖资金曲线：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage066_tick_microstructure_expansion_attempt/qmt_roll_stage066_c9_minrisk_tick_microstructure_expansion_attempt_official_path_tick_coverage_chart_stage066_tick_microstructure_expansion_attempt_v1.png`
- 微观结构散点图：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage066_tick_microstructure_expansion_attempt/qmt_roll_stage066_c9_minrisk_tick_microstructure_expansion_attempt_microstructure_scatter_stage066_tick_microstructure_expansion_attempt_v1.png`
- 产品/年份覆盖热力图：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage066_tick_microstructure_expansion_attempt/qmt_roll_stage066_c9_minrisk_tick_microstructure_expansion_attempt_coverage_product_year_heatmap_stage066_tick_microstructure_expansion_attempt_v1.png`
- 下载状态图：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage066_tick_microstructure_expansion_attempt/qmt_roll_stage066_c9_minrisk_tick_microstructure_expansion_attempt_download_status_chart_stage066_tick_microstructure_expansion_attempt_v1.png`
- tick 微观结构 atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage066_tick_microstructure_expansion_attempt/qmt_roll_stage066_c9_minrisk_tick_microstructure_expansion_attempt_microstructure_atlas_stage066_tick_microstructure_expansion_attempt_v1.png`
- raw tick 目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage066_tick_microstructure_expansion_attempt/raw_tick/`

## 结论

- 本阶段结论：`stage066_reentry_tick_microstructure_full_coverage_ready_no_rule_yet`。Stage066 成功把 C9 reentry tick 微观盘口覆盖从 Stage065 的 `19/54` 补到 `54/54`，这是数据资产突破；但没有单变量出现足够稳健的可交易边界，因此不能直接进入 true engine 或 A/B。
- 是否进入下一步：进入，但只进入固定 spec 的稳健性/视觉复验，不进入交易规则。
- 下一步：围绕 `open_interest_delta_target`、spread、depth、imbalance、mid move 做预声明的低自由度全覆盖稳定性审计，重点看年度 leave-one-year、产品族、右尾保护和坏尾识别是否同时成立；若仍无稳定结构，停止 reentry 微观盘口规则化，转向 Stage045 `timestamp_ready=1` initial entry 同口径盘口覆盖审计。

## 过拟合反思

- 运行前判断：否。本阶段目标是按 Stage065 既定下载计划补数据，不根据结果调阈值。
- 运行后判断：否。
- 原因：处理的是全量 `35` 个缺口，不按盈亏、产品、年份、方向选择；没有新增交易规则、没有 true engine、没有 A/B。相关性和散点只用于下一步是否值得做稳定性审计，不能直接交易化。

## 继续价值反思

- 运行前判断：有价值。Stage065 证明盘口路线技术可行但覆盖不足，补齐覆盖是进入任何微观结构判断前的必要条件。
- 运行后判断：仍有价值，但价值边界变清楚。
- 原因：`54/54` 覆盖消除了“样本偏置来自缺数据”的主要阻塞；不过视觉上赢家和亏损样本在 spread、depth、imbalance、mid move 上明显重叠，下一步必须先做稳健性审计。若不能保护 `OI201/lh2301/FG601` 等右尾，同时识别 `jm2209/OI505` 等坏尾，就不能写规则。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage066 数据突破和下一步边界。
- 是否更新 `research/registry.md`：否，本阶段不是跨线合入，且 registry 由合入者统一更新。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是本线数据资产突破，但不是策略收益/回撤突破、正式候选或跨线合入；先保留在本线记录中。
