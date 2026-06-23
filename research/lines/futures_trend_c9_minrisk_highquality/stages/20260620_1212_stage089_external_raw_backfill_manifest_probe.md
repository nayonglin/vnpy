# Stage089 外生 raw 小规模回填 manifest 探针

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-20 12:12 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：官方/公开 raw 数据小规模回填 manifest 探针；不是策略回测
- 是否重要突破：否。只是确认三条 source 可进入全量 manifest 设计
- 是否触发A/B：否。无策略候选、无 true engine、无正式接入判断

## 外部调研与判断

- 参考资料：
  - AKShare futures 文档：`https://github.com/akfamily/akshare/blob/main/docs/data/futures/futures.md`
  - AKShare changelog：`https://akshare.akfamily.xyz/changelog.html`
  - CZCE 会员持仓排名页面：`https://www.czce.com.cn/cn/jysj/ccpm/H077003004index_1.htm`
  - CZCE 仓单日报页面：`https://www.czce.com.cn/cn/jysj/cdrb/H077003010index_1.htm`
  - GFEX 仓单日报页面：`https://www.gfex.com.cn/gfex/cdrb/hqsj_tjsj.shtml`
- 我的判断：
  - Stage088 只证明三条 source 的三日样本可行；Stage089 必须扩大为固定年度锚点，检查 raw path、query params、sha256、schema hash、parse rows 和 C9 产品映射。
  - 不能用年度锚点覆盖结果形成交易规则；这只决定是否值得做全量日历回填。
  - product-year hit 只用于发现数据工程缺口，不能作为过滤、降仓、恢复风险或正式候选条件。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage089_external_raw_backfill_manifest_probe.py`
- 修改脚本：无既有策略脚本
- 删除脚本：无
- 新增参数：
  - source：`czce_member_rank`、`czce_warehouse`、`gfex_warehouse`
  - 年度锚点：从官方权益曲线每年取 `06-03` 之后首个交易日，覆盖 `2018-2026`
  - manifest 字段：`raw_file`、`url`、`payload_json`、`sha256`、`schema_hash`、`row_count`、`symbol_count`、`sample_symbols`
  - active product-year hit：只统计 C9 实际有交易的产品年份
- 修改参数：无策略参数
- 删除参数：无

## 回测/归因参数

- 数据区间：官方路径 `2018-01` 至 `2026-06`；raw manifest 年度锚点 `20180604/20190603/20200603/20210603/20220606/20230605/20240603/20250603/20260603`
- 账户规模：`150,000`
- 成本口径：只读复用官方基线；本阶段不产生交易
- 样本过滤：不按盈亏、年份表现或品种结果抽样；只按固定年度锚点和 Stage088 允许 source 取样
- 策略/归因口径：
  - 本阶段无交易规则、无 true engine
  - raw response 必须落盘并记录 sha256
  - CZCE 表头日期先做 schema hash 归一，避免把标题日期误判成 schema 漂移
  - active product-year miss 只作为全量回填需求，不作为 alpha 标签

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`53.2560%`
- 其他关键指标：
  - 决策：`stage089_small_raw_manifest_all_three_sources_pass_but_not_full_history_no_rule`
  - source_count：`3`
  - anchor_date_count：`9`
  - manifest_row_count：`27`
  - manifest_parsed_count：`27`
  - manifest_hash_count：`27`
  - small_manifest_pass_source_count：`3/3`
  - full_history_ready_source_count：`0`
  - product_year_requirement_count：`162`
  - product_year_symbol_hit_count：`134`
  - active_product_year_requirement_count：`113`
  - active_product_year_symbol_hit_count：`111`
  - active miss：`gfex_warehouse LC 2023`、`gfex_warehouse SI 2023`
  - miss 归因：C9 的 `lc2401.GFEX` 入场在 `2023-11-07`，`si2310.GFEX` 入场在 `2023-08-24`，而年度锚点是 `2023-06-05`，因此是年度锚点早于品种活跃/仓单出现的边界，不是坏信号。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage089_external_raw_backfill_manifest_probe/qmt_roll_stage089_c9_minrisk_external_raw_backfill_manifest_probe_report_stage089_external_raw_backfill_manifest_probe_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage089_external_raw_backfill_manifest_probe/qmt_roll_stage089_c9_minrisk_external_raw_backfill_manifest_probe_summary_stage089_external_raw_backfill_manifest_probe_v1.csv`
- orders：无
- daily：无新交易日线，仅复用官方路径
- quality：
  - `qmt_roll_stage089_c9_minrisk_external_raw_backfill_manifest_probe_manifest_stage089_external_raw_backfill_manifest_probe_v1.csv`
  - `qmt_roll_stage089_c9_minrisk_external_raw_backfill_manifest_probe_source_summary_stage089_external_raw_backfill_manifest_probe_v1.csv`
  - `qmt_roll_stage089_c9_minrisk_external_raw_backfill_manifest_probe_product_year_requirement_stage089_external_raw_backfill_manifest_probe_v1.csv`
  - `qmt_roll_stage089_c9_minrisk_external_raw_backfill_manifest_probe_schema_summary_stage089_external_raw_backfill_manifest_probe_v1.csv`
  - raw responses：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage089_external_raw_backfill_manifest_probe/raw/`
  - official manifest chart：`qmt_roll_stage089_c9_minrisk_external_raw_backfill_manifest_probe_official_manifest_chart_stage089_external_raw_backfill_manifest_probe_v1.png`
  - source-year matrix：`qmt_roll_stage089_c9_minrisk_external_raw_backfill_manifest_probe_source_year_matrix_chart_stage089_external_raw_backfill_manifest_probe_v1.png`
  - product-year hit chart：`qmt_roll_stage089_c9_minrisk_external_raw_backfill_manifest_probe_product_year_hit_chart_stage089_external_raw_backfill_manifest_probe_v1.png`
  - schema/raw bytes chart：`qmt_roll_stage089_c9_minrisk_external_raw_backfill_manifest_probe_schema_raw_bytes_chart_stage089_external_raw_backfill_manifest_probe_v1.png`

## 视觉观察

- official manifest chart：权益、回撤、broker10 路径不变；年度锚点 parsed count 三条 source 全绿。这说明 source 可做全量 manifest 工程，不说明回撤已改善。
- source-year matrix：`2018-2026` 三条 source 全部 parse-ready；这是 Stage089 的主要工程价值。
- product-year hit chart：无 C9 交易的年份显示灰色，active product-year 只有 GFEX `LC/SI` 的 `2023` 年红色；这两个 miss 发生在年度锚点早于 2023 下半年入场的场景。
- schema/raw bytes chart：CZCE 会员/仓单 raw size 随年份变化明显但 schema hash 归一后稳定；GFEX `2024` 后 raw size 显著变大，早年小响应并不等于有产品覆盖。

## 结论

- 本阶段结论：
  - 三条 source 均通过小规模 raw manifest 探针，可进入全量回填 manifest 设计。
  - 这不是 full-history ready，`full_history_ready_source_count=0`。
  - 不能把年度锚点命中、source_id、active miss 或 schema hash 当交易条件。
  - GFEX 2023 miss 说明下一步必须按真实交易日/产品上市后日期回填，而不是用年度锚点代表全年。
- 是否进入下一步：可以进入 Stage090 全量 manifest 设计；仍不能进入策略 true engine、A/B 或正式候选。
- 下一步：
  - Stage090 设计全量 manifest：对 `czce_member_rank/czce_warehouse/gfex_warehouse` 按官方交易日历或 C9 entry_date 前窗口生成待回填日期，记录 raw path、url、payload、sha256、schema hash、parse rows、symbol hit、失败原因和 rate limit。
  - 只在全量 manifest 覆盖、点时化、右尾缺口安全通过后，才允许做固定 spec 只读外生特征绑定。

## 过拟合反思

- 运行前判断：否。本阶段只做固定年度锚点数据工程，不按收益、亏损桶、产品表现或回撤阶段抽样。
- 运行后判断：否，但要防止“锚点可得性过拟合”。年度锚点全绿不能代表全年每个交易日都可取，也不能代表品种上市后每个关键 entry_date 可覆盖。
- 原因：没有产生策略规则，也没有使用最终盈亏选择阈值；风险在于把可得性误读为 alpha。

## 继续价值反思

- 运行前判断：有价值。目标需要入场前可见、非最终盈亏标签的新信息源；raw/provenance 是必要前置。
- 运行后判断：有价值，且下一步更明确。CZCE 会员、CZCE 仓单、GFEX 仓单可以进入全量 manifest；DCE/GFEX 会员仍不碰。
- 原因：27/27 raw 可落盘、hash、parse，active product-year hit `111/113`，剩余 2 个 miss 解释为年度锚点边界。继续价值在于全量点时化覆盖，而不是策略调参。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage089 摘要和后续边界。
- 是否更新 `research/registry.md`：否。不是重要突破、正式候选或跨线合入。
- 是否追加根目录 `memory.md/back_log.md`：否。没有策略候选或正式口径变化。
