# Stage090 入场前窗口 raw manifest 设计与小探针

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-20 12:22 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：官方/公开外生 raw 数据入场前窗口 manifest 设计与小探针；不是策略回测
- 是否重要突破：否。只是把 Stage089 的年度锚点推进到 C9 entry_date 前窗口计划
- 是否触发A/B：否。无策略候选、无 true engine、无正式接入判断

## 外部调研与判断

- 参考资料：
  - AKShare futures 文档：`https://github.com/akfamily/akshare/blob/main/docs/data/futures/futures.md`
  - AKShare changelog：`https://akshare.akfamily.xyz/changelog.html`
  - CZCE 会员持仓排名页面：`https://www.czce.com.cn/cn/jysj/ccpm/H077003004index_1.htm`
  - CZCE 仓单日报页面：`https://www.czce.com.cn/cn/jysj/cdrb/H077003010index_1.htm`
  - GFEX 仓单日报页面：`https://www.gfex.com.cn/gfex/cdrb/hqsj_tjsj.shtml`
- 我的判断：
  - AKShare changelog 显示 CZCE wrapper 口径有过更名与调整，因此 Stage090 继续以 raw URL、payload、sha256、schema hash 和 parse result 为准，不把 wrapper rows 当权威证据。
  - CZCE/GFEX 官方公开端点可用于 raw provenance 工程，但当前仍只是点时化覆盖准备，不能直接转成交易条件。
  - Stage089 的 GFEX `LC/SI 2023` 年度锚点 miss 说明下一步应该围绕 C9 入场前窗口，而不是用单个年度锚点代表全年。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage090_preentry_window_raw_manifest_design.py`
- 修改脚本：无既有策略脚本
- 删除脚本：无
- 新增参数：
  - `LOOKBACK_TRADING_DAYS=7`
  - source：`czce_member_rank`、`czce_warehouse`、`gfex_warehouse`
  - manifest 粒度：按 C9 相关 closed lot 的 `entry_date` 前 `7` 个官方交易日生成 source/date/raw 计划
  - probe 选择：每个 source-year 取一个 linked lot 数最多的代表日期；GFEX `LC/SI 2023` 入场前窗口额外全探针
- 修改参数：无策略参数
- 删除参数：无

## 回测/归因参数

- 数据区间：官方路径 `2018-01` 至 `2026-06`；raw manifest 覆盖 C9 相关 closed lot 的 entry_date 前 `7` 个交易日
- 账户规模：`150,000`
- 成本口径：只读复用官方基线；本阶段不产生交易
- 样本过滤：只按交易所/source 可用性与 C9 entry_date 前固定窗口筛选；不按盈亏、回撤阶段、产品表现或年份表现抽样
- 策略/归因口径：
  - 本阶段无交易规则、无 true engine
  - planned manifest 不等于 full raw download
  - raw response 只在 probe 行落盘并记录 hash
  - product hit/miss 只用于数据覆盖归因，不能作为过滤、降仓或恢复风险条件

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`53.2560%`
- 其他关键指标：
  - 决策：`stage090_preentry_window_manifest_built_probe_all_parsed_no_rule`
  - relevant_lot_count：`188`
  - lot_window_link_count：`2,590`
  - planned_raw_date_count：`1,504`
  - planned_source_count：`3`
  - planned_product_count：`10`
  - planned_year_count：`9`
  - probe_count：`34`
  - probe_parsed_count：`34/34`
  - probe_hash_count：`34/34`
  - probe_needed_symbol_hit_all_count：`27/34`
  - preentry_manifest_ready_source_count：`3/3`
  - full_raw_download_done：`0`
  - source plan：`czce_member_rank=731`、`czce_warehouse=731`、`gfex_warehouse=42`
  - source probe parsed：`czce_member_rank=9/9`、`czce_warehouse=9/9`、`gfex_warehouse=16/16`
  - GFEX `LC 2023` 入场前窗口 probe `7` 行均解析成功但 product hit 为 `0`，样本 raw 只出现 `SI`；这是上市/仓单出现/活跃日期边界，不是坏信号。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage090_preentry_window_raw_manifest_design/qmt_roll_stage090_c9_minrisk_preentry_window_raw_manifest_design_report_stage090_preentry_window_raw_manifest_design_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage090_preentry_window_raw_manifest_design/qmt_roll_stage090_c9_minrisk_preentry_window_raw_manifest_design_summary_stage090_preentry_window_raw_manifest_design_v1.csv`
- orders：无
- daily：无新交易日线，仅复用官方路径
- quality：
  - `qmt_roll_stage090_c9_minrisk_preentry_window_raw_manifest_design_planned_raw_manifest_stage090_preentry_window_raw_manifest_design_v1.csv`
  - `qmt_roll_stage090_c9_minrisk_preentry_window_raw_manifest_design_lot_window_links_stage090_preentry_window_raw_manifest_design_v1.csv`
  - `qmt_roll_stage090_c9_minrisk_preentry_window_raw_manifest_design_probe_results_stage090_preentry_window_raw_manifest_design_v1.csv`
  - `qmt_roll_stage090_c9_minrisk_preentry_window_raw_manifest_design_source_summary_stage090_preentry_window_raw_manifest_design_v1.csv`
  - `qmt_roll_stage090_c9_minrisk_preentry_window_raw_manifest_design_product_summary_stage090_preentry_window_raw_manifest_design_v1.csv`
  - raw probe responses：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage090_preentry_window_raw_manifest_design/raw/`
  - official path manifest chart：`qmt_roll_stage090_c9_minrisk_preentry_window_raw_manifest_design_official_path_manifest_chart_stage090_preentry_window_raw_manifest_design_v1.png`
  - planned source-year heatmap：`qmt_roll_stage090_c9_minrisk_preentry_window_raw_manifest_design_planned_source_year_heatmap_stage090_preentry_window_raw_manifest_design_v1.png`
  - probe status heatmap：`qmt_roll_stage090_c9_minrisk_preentry_window_raw_manifest_design_probe_status_heatmap_stage090_preentry_window_raw_manifest_design_v1.png`
  - probe product hit heatmap：`qmt_roll_stage090_c9_minrisk_preentry_window_raw_manifest_design_probe_product_hit_heatmap_stage090_preentry_window_raw_manifest_design_v1.png`

## 视觉观察

- official path manifest chart：权益、回撤、broker10 路径不变；计划 raw 日期分布没有只贴着单一右尾台阶。CZCE 两类 source 横跨 `2018-2026`，GFEX 仅在 `2023-2025` 出现，符合品种上市后的事实边界。
- planned source-year heatmap：CZCE 会员/仓单每年均有计划行，`2021` 最多为 `135`，`2026` 暂为 `43`；GFEX 仓单只在 `2023/2024/2025` 各 `14` 行。
- probe status heatmap：所有 probe 均 parsed，CZCE 每 source-year 各 `1` 个代表日期，GFEX `2023` 因 `LC/SI` focus 有 `14` 个 probe。
- probe product hit heatmap：CZCE probe 产品命中全绿；GFEX `SI` 命中，GFEX `LC 2023` 为红格。该红格是覆盖边界，不能解释为应跳过 LC 或降低风险。

## 结论

- 本阶段结论：
  - 已生成 C9 入场前 `7` 交易日的 raw manifest 计划，覆盖 `1,504` 个 source/date 计划行与 `2,590` 条 lot-window link。
  - 小探针 `34/34` 可落盘、hash、parse，三条 source 均可继续进入 full raw download/backfill。
  - 但 full raw download 尚未执行，`full_raw_download_done=0`；AP 等产品在本轮代表探针中未抽中不代表 miss。
  - GFEX `LC 2023` 的 preentry miss 说明 full manifest 需要显式处理产品上市/仓单出现/活跃日期，不允许把 miss 状态策略化。
- 是否进入下一步：可以进入 Stage091 full raw download/backfill 设计或分批执行；仍不能进入策略 true engine、A/B 或正式候选。
- 下一步：
  - 对 `1,504` 个 planned raw 日期做分批下载，记录 rate-limit、HTTP status、content bytes、sha256、schema hash、parse rows、symbol hit/miss 和失败原因。
  - 下载完成后做 point-in-time feature binding 前置审计：先查覆盖是否跨年、跨品种、跨右尾安全，再决定是否存在固定 spec 的只读外生特征。

## 过拟合反思

- 运行前判断：否。本阶段只做数据 manifest 设计和固定探针，不按收益、亏损、回撤段或右尾表现选择规则。
- 运行后判断：否，但存在“覆盖状态误读”为信号的风险。
- 原因：没有新增交易规则、没有参数扫描、没有 true engine；风险主要在于把 `LC 2023` miss、source ready 或 product hit 当作可交易标签，所以明确禁止。

## 继续价值反思

- 运行前判断：有价值。当前目标需要真正入场前可见、非最终盈亏标签、可复验的新信息源；raw/provenance 是必要前置。
- 运行后判断：有价值。Stage090 把下一步从“是否能取样”推进到“按 `1,504` 个明确 source/date 做 full raw backfill”。
- 原因：三条 source 小探针全部解析，且 GFEX `LC 2023` 暴露了必须处理的真实产品时序边界；这比继续从 closed-lot 或权益曲线切片更接近可穿越周期的数据底座。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage090 摘要和后续边界。
- 是否更新 `research/registry.md`：否。不是重要突破、正式候选或跨线合入。
- 是否追加根目录 `memory.md/back_log.md`：否。没有策略候选或正式口径变化。
