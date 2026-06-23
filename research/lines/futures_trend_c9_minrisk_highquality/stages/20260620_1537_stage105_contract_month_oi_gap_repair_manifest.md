# Stage105 合约月份 OI 缺口修复 manifest

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 15:37 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读数据缺口修复 manifest；不是真引擎、不生成交易规则
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk Kline 对象字段：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.objs.html`
  - TqSdk 介绍：`https://tqsdk-python.readthedocs.io/en/latest/intro.html`
  - CME contract trading codes：`https://www.cmegroup.com/education/courses/introduction-to-futures/understanding-contract-trading-codes`
  - CME daily volume and open interest：`https://www.cmegroup.com/market-data/browse-data/exchange-volume.html`
- 我的判断：TqSdk 日线字段能承载 `open_oi/close_oi`，但合约代码格式、年份位数和本地下载批次覆盖会造成数据缺口。缺口修复应该先回到具体合约文件与 raw schema，而不是把 `missing`、`rank` 或年份缺口解释为交易信号。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage105_contract_month_oi_gap_repair_manifest.py`
- 修改脚本：无
- 删除脚本：无
- 新增输出：
  - `gap_rows`
  - `repair_manifest`
  - `action_summary`
  - `product_year_gap_matrix`
  - `source_age_audit`
  - `promotion_gate`
  - `official_path_gap_chart`
  - `product_year_gap_heatmap`
  - `repair_action_chart`
  - `source_age_chart`
- 新增参数：无策略参数；只使用 Stage104 已冻结的 non-ready 行做文件级审计。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage104 `219` 笔 timestamp-ready 订单与 Stage045 官方资金路径。
- 本地搜索范围：`examples/portfolio_backtesting/downloaded_futures/**/*.csv`。
- 审计口径：精确合约文件是否存在、schema 是否含 OI、自然日 source-age 是否只是交易日历空档、缺失合约需要的补数 manifest。
- 策略/归因口径：`strategy_feature_usable=0`、`true_engine_run=0`、`ab_triggered=0`。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：closed-lot win rate `36.0902%`
- 其他关键指标：
  - `decision=stage105_gap_repair_manifest_built_external_backfill_required_no_rule`
  - `stage104_target_panel_ready_count=186`
  - `timestamp_ready_order_count=219`
  - `stage104_gap_row_count=33`
  - `missing_target_contract_file_gap_row_count=31`
  - `stale_source_calendar_gap_row_count=2`
  - `calendar_holiday_adjacent_reclassifiable_count=2`
  - `exact_alternate_local_file_found_row_count=0`
  - `unique_missing_contract_count=21`
  - `legacy_2020_missing_gap_row_count=22`
  - `near_endpoint_2026_missing_gap_row_count=9`
  - `effective_panel_ready_after_calendar_reclass_count=188/219`
  - `effective_panel_ready_after_calendar_reclass_rate_pct=85.8447%`
  - `right_tail_gap_row_count=0`
  - `bottom_loss_gap_row_count=4`
  - `promotion_gate_pass_count=2/6`
  - `official_config_changed=0`、`strategy_rule_created=0`、`true_engine_run=0`、`ab_triggered=0`、`order_api_called=0`、`ctp_connected=0`

## 视觉观察

- official path gap chart：缺口主要贴在 2020 初期与 2026 近端，两个自然日 stale 点可解释为交易日历相邻；缺口点不形成可交易状态。
- product-year gap heatmap：缺口集中在 `2020` 多品种与 `2026` 近端少数合约，说明当前阻断是下载批次覆盖，不是策略结构。
- repair action chart：最大动作是 `backfill_legacy_target_contract_daily_oi`，其次是 `download_or_refresh_near_endpoint_target_contract_daily_oi`；本地 alternate exact 文件未找到。
- source-age chart：`CF201` 与 `AP205` 自然日超过 7 天，但产品交易日之间没有中间日期，更适合作为交易日历相邻修正，不应当被当作市场信号。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage105_contract_month_oi_gap_repair_manifest/qmt_roll_stage105_c9_minrisk_contract_month_oi_gap_repair_manifest_report_stage105_contract_month_oi_gap_repair_manifest_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage105_contract_month_oi_gap_repair_manifest/qmt_roll_stage105_c9_minrisk_contract_month_oi_gap_repair_manifest_summary_stage105_contract_month_oi_gap_repair_manifest_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage105_contract_month_oi_gap_repair_manifest/qmt_roll_stage105_c9_minrisk_contract_month_oi_gap_repair_manifest_decision_stage105_contract_month_oi_gap_repair_manifest_v1.json`
- gap rows：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage105_contract_month_oi_gap_repair_manifest/qmt_roll_stage105_c9_minrisk_contract_month_oi_gap_repair_manifest_gap_rows_stage105_contract_month_oi_gap_repair_manifest_v1.csv`
- repair manifest：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage105_contract_month_oi_gap_repair_manifest/qmt_roll_stage105_c9_minrisk_contract_month_oi_gap_repair_manifest_repair_manifest_stage105_contract_month_oi_gap_repair_manifest_v1.csv`
- charts：
  - `qmt_roll_stage105_c9_minrisk_contract_month_oi_gap_repair_manifest_official_path_gap_chart_stage105_contract_month_oi_gap_repair_manifest_v1.png`
  - `qmt_roll_stage105_c9_minrisk_contract_month_oi_gap_repair_manifest_product_year_gap_heatmap_stage105_contract_month_oi_gap_repair_manifest_v1.png`
  - `qmt_roll_stage105_c9_minrisk_contract_month_oi_gap_repair_manifest_repair_action_chart_stage105_contract_month_oi_gap_repair_manifest_v1.png`
  - `qmt_roll_stage105_c9_minrisk_contract_month_oi_gap_repair_manifest_source_age_chart_stage105_contract_month_oi_gap_repair_manifest_v1.png`

## 结论

- 本阶段结论：Stage104 的 `2` 个 stale source 可以改用交易日历相邻 gate 解释，但 `31` 个目标合约文件缺失在本地所有下载批次中都没有精确替代文件；必须外部补数或刷新 TqSDK 日线根目录。
- 原因：本地 exact alternate file 命中为 `0`，effective ready 即使加入交易日历相邻修正也只有 `188/219=85.8447%`，仍低于 `95%` 规则研究门槛。
- 下一步：按 repair manifest 补 `2020` legacy target contract daily OI 与 `2026` near-endpoint target contract daily OI，落盘 raw path/hash/schema/source permission 后重跑 Stage104/105；补齐前不做 rank/share 规则。

## 过拟合反思

- 运行前判断：否。Stage105 是文件级缺口修复审计，不按收益设计条件。
- 运行后判断：否。缺口分类没有被用于开仓/降仓/退出，且明确把 `missing` 与 product-year 集中度排除为交易信号。
- 原因：如果用 2020 或 2026 缺口对应的亏损去写规则，就是用数据缺失包装 alpha；本阶段只生成补数清单。

## 继续价值反思

- 运行前判断：有价值。Stage104 已证明合约月 OI 有部分覆盖且右尾覆盖完整，值得把数据契约补清。
- 运行后判断：有价值，但下一步价值在补数，不在策略研究。
- 原因：两个 stale row 已被交易日历解释，说明 Stage104 gate 可精炼；但 `31` 个目标合约文件缺失仍是硬阻断。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage105 摘要和边界。
- 是否更新 `research/registry.md`：否，不是正式候选、重要突破或路线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，不是正式候选、重要突破或跨线合并。
