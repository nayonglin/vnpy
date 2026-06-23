# Stage091 入场前窗口 raw 全量回填与覆盖审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-20 13:13 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage090 冻结 source/date 计划的 full raw download/backfill 与覆盖审计；不是策略回测
- 是否重要突破：否。raw 覆盖工程完成，但仍不是策略候选
- 是否触发A/B：否。无策略候选、无 true engine、无正式接入判断

## 外部调研与判断

- 参考资料：
  - AKShare futures 文档：`https://github.com/akfamily/akshare/blob/main/docs/data/futures/futures.md`
  - AKShare changelog：`https://akshare.akfamily.xyz/changelog.html`
  - CZCE 会员持仓排名页面：`https://www.czce.com.cn/cn/jysj/ccpm/H077003004index_1.htm`
  - CZCE 仓单日报页面：`https://www.czce.com.cn/cn/jysj/cdrb/H077003010index_1.htm`
  - GFEX 仓单日报页面：`https://www.gfex.com.cn/gfex/cdrb/hqsj_tjsj.shtml`
- 我的判断：
  - Stage091 继续以官方 raw 响应为准，不依赖 AKShare wrapper 输出。
  - full raw download 完成只解决 provenance 与覆盖问题，不等于外生特征有效，更不能直接解释回撤。
  - product hit/miss 必须先分类为数据缺口、产品上市/仓单出现时序、或真实空仓单状态；分类前不能进入 feature binding。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage091_preentry_window_raw_full_backfill.py`
- 修改脚本：无既有策略脚本
- 删除脚本：无
- 新增参数：
  - `REQUEST_TIMEOUT=15`
  - `REQUEST_RETRIES=2`
  - `REQUEST_SLEEP_SECONDS=0.12`
  - `CHECKPOINT_EVERY=25`
  - input plan：Stage090 `1,504` 个 source/date planned raw manifest 行
- 修改参数：无策略参数
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage090 入场前 `7` 交易日 source/date plan，覆盖官方路径 `2018-01` 至 `2026-06` 的相关 C9 closed lots
- 账户规模：`150,000`
- 成本口径：只读复用官方基线；本阶段不产生交易
- 样本过滤：完全复用 Stage090 冻结 plan，不按盈亏、回撤、右尾、品种表现或年份表现改样本
- 策略/归因口径：
  - 本阶段无交易规则、无 true engine
  - 所有 source/date 均下载 raw response，记录 URL、payload、sha256、HTTP status、content bytes、schema hash、parse rows、symbol hit/miss
  - product-year miss 只作为下一步覆盖分类输入，不能交易化

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`53.2560%`
- 其他关键指标：
  - 决策：`stage091_full_raw_backfill_all_parsed_product_timing_gaps_no_rule`
  - planned_raw_date_count：`1,504`
  - result_count/hash_count/parsed_count：`1,504/1,504/1,504`
  - needed_symbol_hit_all_count：`1,490/1,504`
  - source_count/product_count/year_count：`3/10/9`
  - source_full_download_done_count：`3/3`
  - source_full_parse_done_count：`3/3`
  - product_year_count：`116`
  - product_year_all_hit_count：`114/116`
  - http_error_count/parse_fail_count/network_error_count：`0/0/0`
  - full_raw_download_done：`1`
  - full_raw_parse_done：`1`
  - source summary：`czce_member_rank 731/731 parsed + 731/731 hit_all`；`czce_warehouse 731/731 parsed + 724/731 hit_all`；`gfex_warehouse 42/42 parsed + 35/42 hit_all`
  - product-year miss：
    - `czce_warehouse AP 2018`：planned `14`、hit `7`、miss `7`；miss 日期 `20180320-20180328`，`20180912-20180920` 已命中
    - `gfex_warehouse LC 2023`：planned `7`、hit `0`、miss `7`；miss 日期 `20231027-20231106`，raw 仅出现 `SI`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage091_preentry_window_raw_full_backfill/qmt_roll_stage091_c9_minrisk_preentry_window_raw_full_backfill_report_stage091_preentry_window_raw_full_backfill_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage091_preentry_window_raw_full_backfill/qmt_roll_stage091_c9_minrisk_preentry_window_raw_full_backfill_summary_stage091_preentry_window_raw_full_backfill_v1.csv`
- orders：无
- daily：无新交易日线，仅复用官方路径
- quality：
  - `qmt_roll_stage091_c9_minrisk_preentry_window_raw_full_backfill_backfill_results_stage091_preentry_window_raw_full_backfill_v1.csv`
  - `qmt_roll_stage091_c9_minrisk_preentry_window_raw_full_backfill_source_summary_stage091_preentry_window_raw_full_backfill_v1.csv`
  - `qmt_roll_stage091_c9_minrisk_preentry_window_raw_full_backfill_source_year_summary_stage091_preentry_window_raw_full_backfill_v1.csv`
  - `qmt_roll_stage091_c9_minrisk_preentry_window_raw_full_backfill_product_year_coverage_stage091_preentry_window_raw_full_backfill_v1.csv`
  - `qmt_roll_stage091_c9_minrisk_preentry_window_raw_full_backfill_schema_summary_stage091_preentry_window_raw_full_backfill_v1.csv`
  - `qmt_roll_stage091_c9_minrisk_preentry_window_raw_full_backfill_failure_rows_stage091_preentry_window_raw_full_backfill_v1.csv`
  - raw responses：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage091_preentry_window_raw_full_backfill/raw/`
  - official path backfill chart：`qmt_roll_stage091_c9_minrisk_preentry_window_raw_full_backfill_official_path_backfill_chart_stage091_preentry_window_raw_full_backfill_v1.png`
  - source-year parse heatmap：`qmt_roll_stage091_c9_minrisk_preentry_window_raw_full_backfill_source_year_parse_heatmap_stage091_preentry_window_raw_full_backfill_v1.png`
  - product-year hit heatmap：`qmt_roll_stage091_c9_minrisk_preentry_window_raw_full_backfill_product_year_hit_heatmap_stage091_preentry_window_raw_full_backfill_v1.png`
  - schema bytes chart：`qmt_roll_stage091_c9_minrisk_preentry_window_raw_full_backfill_schema_bytes_chart_stage091_preentry_window_raw_full_backfill_v1.png`

## 视觉观察

- official path backfill chart：黑点和计划柱完全重合，说明 Stage090 plan 的 full raw parse 覆盖完成；权益、回撤、broker10 只是背景路径，没有被本阶段改变。
- source-year parse heatmap：所有 planned source-year 均为 parsed/planned 全满，CZCE 两类 source 覆盖 `2018-2026`，GFEX 覆盖 `2023-2025`。
- product-year hit heatmap：绝大多数 product-year 为绿色全命中；只有 `czce_warehouse:AP 2018` 黄色 `7/14` 和 `gfex_warehouse:LC 2023` 红色 `0/7`。
- schema bytes chart：三条 source 各自 schema hash 稳定为 `1` 个；CZCE member raw bytes 明显大于 warehouse，GFEX JSON 较小但 `2024-2025` raw bytes 高于 `2023`。

## 结论

- 本阶段结论：
  - Stage090 的 `1,504` 个 planned source/date 已全部 raw 落盘、hash、parse，无 HTTP/parse/network failure。
  - raw provenance 阻塞解除，但 feature binding 阻塞尚未解除，因为 `AP 2018` 和 `LC 2023` 的 product timing gaps 必须先分类。
  - 这两个缺口不允许解释成“跳过/降仓/恢复风险”的信号。它们更像产品上市、仓单出现或报告品种列表时序边界。
- 是否进入下一步：可以进入 Stage092 覆盖缺口分类与右尾安全审计；仍不能进入策略 true engine、A/B 或正式候选。
- 下一步：
  - 对 `czce_warehouse AP 2018` 和 `gfex_warehouse LC 2023` 做 lot-window 绑定，确认关联 lot、entry_date、realized PnL、是否接近右尾关键贡献。
  - 输出缺口分类：`present`、`official_absent_before_product_or_warehouse_start`、`raw_parse_gap`、`source_not_applicable`。
  - 只有分类和右尾安全通过后，才允许设计 point-in-time feature binding schema。

## 过拟合反思

- 运行前判断：否。下载清单由 Stage090 固定，不按收益或回撤结果选择 source/date。
- 运行后判断：否，但要防止把 coverage gap 当作 alpha。
- 原因：本阶段没有产生交易规则，没有参数扫描，没有 true engine；风险点在于 `AP 2018` 与 `LC 2023` miss 容易被误读为应跳过这些产品或年份，所以必须显式禁止。

## 继续价值反思

- 运行前判断：有价值。没有 full raw、hash、parse，就无法建立可复验的外生点时化数据。
- 运行后判断：有价值。raw 全量回填完成，把问题收敛到两个明确的 product timing gaps。
- 原因：相比继续从 closed-lot 或权益曲线切片，当前路线已经形成可审计的数据底座；下一步可以用同一账本做覆盖分类和右尾安全审计。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage091 摘要和后续边界。
- 是否更新 `research/registry.md`：否。不是重要突破、正式候选或跨线合入。
- 是否追加根目录 `memory.md/back_log.md`：否。没有策略候选或正式口径变化。
