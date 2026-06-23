# Stage106 合约月份 OI TqSdk backtest 隔离回补 smoke

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-20 15:58 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：数据工程 / raw provenance / 覆盖修复，不写真引擎
- 是否重要突破：数据覆盖突破；不是策略突破
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk 官方 `DataDownloader` 文档：历史数据下载器属于专业版能力，支持 `dur_sec=86400` 日线与 CSV 输出。
  - TqSdk 官方行情/K线文档：`get_kline_serial(..., 86400)` 是日线，单序列最多最后 8000 根 K 线。
  - TqSdk 官方 `TqBacktest` 文档：可按指定起止时间做历史回放。
  - TqSdk GitHub：官方开源包提供历史数据、实时数据、回测、模拟和实盘等能力，但本阶段只用回测行情回放，不连接实盘。
- 我的判断：
  - 直接 `query_quotes(expired=True)` 只能看到 `5/21` 个缺口合约，不足以判断 2020 legacy 数据不可得。
  - 小 probe 证明 `TqBacktest + get_kline_serial(86400)` 可以回放 `DCE.jm2005` 与 `SHFE.ru2605` 的 `open_oi/close_oi`，比直接 DataDownloader 更适合作为本阶段隔离 raw 补数路径。
  - 这一步只解决数据契约，不证明 OI rank/share 有交易 alpha。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage106_contract_month_oi_tqsdk_backtest_backfill_smoke.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `STAGE106_MAX_CONTRACTS`，默认 `0`，表示全量处理 Stage105 repair manifest。
  - `STAGE106_MAX_SECONDS_PER_CONTRACT`，默认 `45`。
  - `STAGE106_FORCE_REFRESH`，默认 `0`。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：按 Stage105 repair manifest 和 Stage104 `source_date` 自动扩展窗口，实际 raw 范围 `2019-12-26` 至 `2026-04-30`。
- 账户规模：沿用官方路径背景，`150,000` 初始账户口径。
- 成本口径：不新增回测，沿用官方背景指标；总滑点 `2,730,130`。
- 样本过滤：Stage105 `21` 个缺失 target contract，Stage105 `33` 条 gap rows。
- 策略/归因口径：只读隔离 raw 回补；不合入主 `tqsdk_daily_2010_2026_04`，不建立交易规则。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - `repair_contract_count=21`
  - `query_quotes_symbol_available_count=5`
  - `query_quotes_symbol_unavailable_count=16`
  - `backtest_downloaded_or_cached_count=21`
  - `raw_provenance_complete_count=21`
  - `missing_target_contract_file_gap_row_count=31`
  - `missing_gap_rows_resolved_by_stage106_raw_count=31`
  - `calendar_holiday_adjacent_reclassifiable_count=2`
  - `potential_panel_ready_after_stage106_raw_count=219/219=100.0000%`
  - `promotion_gate_pass_count=5/8`
  - `primary_daily_root_merged=0`
  - `stage104_reaudit_done_after_merge=0`
  - `strategy_feature_usable=0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage106_contract_month_oi_tqsdk_backtest_backfill_smoke/qmt_roll_stage106_c9_minrisk_contract_month_oi_tqsdk_backtest_backfill_smoke_report_stage106_contract_month_oi_tqsdk_backtest_backfill_smoke_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage106_contract_month_oi_tqsdk_backtest_backfill_smoke/qmt_roll_stage106_c9_minrisk_contract_month_oi_tqsdk_backtest_backfill_smoke_summary_stage106_contract_month_oi_tqsdk_backtest_backfill_smoke_v1.csv`
- raw provenance：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage106_contract_month_oi_tqsdk_backtest_backfill_smoke/qmt_roll_stage106_c9_minrisk_contract_month_oi_tqsdk_backtest_backfill_smoke_raw_provenance_stage106_contract_month_oi_tqsdk_backtest_backfill_smoke_v1.csv`
- gap recheck：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage106_contract_month_oi_tqsdk_backtest_backfill_smoke/qmt_roll_stage106_c9_minrisk_contract_month_oi_tqsdk_backtest_backfill_smoke_gap_recheck_stage106_contract_month_oi_tqsdk_backtest_backfill_smoke_v1.csv`
- raw daily root：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage106_contract_month_oi_tqsdk_backtest_backfill_smoke/raw_daily_backtest/`
- 视觉图：
  - official path：`qmt_roll_stage106_c9_minrisk_contract_month_oi_tqsdk_backtest_backfill_smoke_official_path_backfill_recheck_stage106_contract_month_oi_tqsdk_backtest_backfill_smoke_v1.png`
  - product-year heatmap：`qmt_roll_stage106_c9_minrisk_contract_month_oi_tqsdk_backtest_backfill_smoke_product_year_backfill_heatmap_stage106_contract_month_oi_tqsdk_backtest_backfill_smoke_v1.png`
  - raw rows：`qmt_roll_stage106_c9_minrisk_contract_month_oi_tqsdk_backtest_backfill_smoke_raw_rows_by_contract_stage106_contract_month_oi_tqsdk_backtest_backfill_smoke_v1.png`
  - gate：`qmt_roll_stage106_c9_minrisk_contract_month_oi_tqsdk_backtest_backfill_smoke_promotion_gate_stage106_contract_month_oi_tqsdk_backtest_backfill_smoke_v1.png`

## 结论

- 本阶段结论：`stage106_isolated_tqsdk_backtest_raw_backfill_all_gap_dates_covered_no_merge_no_rule`。Stage105 的 `31` 条 missing target contract gap rows 已全部被隔离 raw 回放覆盖，`21/21` 个 raw 文件具备 `sha256/schema_hash/open_oi/close_oi` provenance；但主日线根未合入、Stage104/105 未复跑，所以仍不可交易化。
- 是否进入下一步：是，进入隔离合入与复跑审计。
- 下一步：构造临时 patched daily root，只把 Stage106 raw 文件按原主数据 schema 映射进去，复跑 Stage104/105，确认 strict panel-ready、product-year hard gap、source-age、right-tail/bottom-loss gate 是否全部通过；仍不得进入 true engine/A/B。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否，但有后续误用风险。
- 原因：本阶段没有按收益、年份、品种或方向选择规则，只按 Stage105 预先生成的缺口合约补齐 raw OI；视觉图显示补齐点集中在 2020 与 2026，是下载批次/端点缺口，不是策略 alpha。风险在于后续如果直接把 OI rank/share 写成过滤或仓位规则，会把数据修复误当成收益规律。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：Stage104/105 的主要阻塞从“缺 target 合约日线 OI”变成“需要隔离合入后复跑覆盖审计”，问题更具体、更可验证；继续做有价值。但下一步仍是数据契约，不是参数搜索。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage106 覆盖突破与后续边界。
- 是否更新 `research/registry.md`：否，本阶段不是正式候选或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不改正式候选，不触发跨线总账。
