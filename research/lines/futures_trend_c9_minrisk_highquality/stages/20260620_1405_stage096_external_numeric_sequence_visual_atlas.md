# Stage096 外生数值序列视觉 atlas 与经济语义预检

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 14:05 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读数据工程 + 视觉归因预检；不是真引擎、不生成交易规则
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - 郑商所仓单日报：`https://www.czce.com.cn/cn/jysj/cdrb/H077003010index_1.htm`
  - 郑商所持仓排名：`https://www.czce.com.cn/cn/jysj/ccpm/H077003004index_1.htm`
  - 广期所仓单日报：`https://www.gfex.com.cn/gfex/cdrb/hqsj_tjsj.shtml`
  - AKShare futures 文档：`https://akshare.akfamily.xyz/data/futures/futures.html`
  - CME open interest/volume 教育材料：`https://www.cmegroup.com/cn-t/education/courses/introduction-to-futures/open-interest.html`
- 我的判断：仓单数量/变化/有效预报更接近交割供给与库存压力，会员成交量/持买/持卖/净持仓更接近参与度与拥挤状态；这些字段有经济语义，但只能作为入场前外生状态的视觉假设来源，不能直接把数值大小、变化方向、产品/年份、缺席状态或 aggregation_source 写成策略规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage096_external_numeric_sequence_visual_atlas.py`
- 修改脚本：同一脚本内修复 `DataFrame.get(..., 0)` 标量兜底问题，并把重复计数字段改名为 `linked_feature_row_count`，避免输出 `_x/_y` 混乱。
- 删除脚本：无
- 新增参数：
  - `BOTTOM_LOSS_VISUAL_COUNT=12`
  - `MAXDD_CONTEXT_DD_PCT=-40.0`
  - `LOTS_PER_ATLAS_PAGE=4`
  - 固定展示入场前 `7` 个交易日的外生序列，沿用 Stage090-095 的 point-in-time 窗口。
- 修改参数：无策略参数修改；仅脚本字段命名修正。
- 删除参数：无

## 回测/归因参数

- 数据区间：官方闭合 lot 覆盖 `2018-2026`，外生 raw 来源为 Stage091-095 已点时化的 `czce_member_rank/czce_warehouse/gfex_warehouse`。
- 账户规模：沿用当前 C9/15w 基准路径，仅作为背景路径。
- 成本口径：沿用基准统计，总滑点 `2,730,130`。
- 样本过滤：不做收益阈值和交易过滤；固定视觉 cohort 为 right-tail `19`、bottom-loss `12`、maxDD context `10`、fallback-or-absent `10`，并取 union `50` 个 lot。
- 策略/归因口径：只读外生数值序列 atlas，`strategy_rule_allowed=0`、`true_engine_allowed=0`、`strategy_feature_usable=0`。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`53.2560%`
- 其他关键指标：
  - `decision=stage096_visual_atlas_ready_no_rule`
  - `feature_row_count=2,590`
  - `sequence_row_count=11,592`
  - `lot_count=188`
  - `selected_lot_count=50`
  - `atlas_page_count=13`
  - `right_tail_visual_lot_count=19`
  - `bottom_loss_visual_lot_count=12`
  - `maxdd_context_visual_lot_count=10`
  - `fallback_or_absent_visual_lot_count=10`
  - maxDD context：`2022-05-30` 到 `2023-03-09`，trough `2022-06-29`，`-45.0827%`
  - broker10 peak：`111.7365%`
  - `official_config_changed=0`、`strategy_rule_created=0`、`true_engine_run=0`、`ab_triggered=0`、`order_api_called=0`、`ctp_connected=0`

## 视觉观察

- official context chart：`50` 个视觉样本覆盖早期 fallback、2022-2023 maxDD 段、右尾台阶和近端样本；right-tail 主要落在权益扩张台阶附近，maxDD context 全部是自然回撤段中的亏损 lot，样本分布符合预期但不是交易 bucket。
- cohort sequence chart：bottom-loss 和 right-tail 都出现 member volume 入场前抬升，不能用“成交量放大”区分好坏；maxDD context 的 member volume 中位 delta 大幅为负且跳动，member net OI 入场前转正，但 atlas 中由 MA/SA/FG/AP 等少数形态驱动，不能直接交易化。
- atlas page 001：bottom-loss 内部形态高度异质，`OI205/SM205/AP210/SM209` 的仓单、成交量、净持仓方向不同；单看仓单增加、成交量增加或净持仓转弱，都有反例。
- atlas page 006：`lc2401.GFEX` fallback-or-absent 全部 `n/a`，证明 absent-state 是官方时序边界，不是可交易信号；maxDD 段 `MA209` 两笔重复 lot 形态几乎一致，提示后续不得让重复合约/同日样本支配假设。
- atlas page 010/013：right-tail 中既有仓单上升的 `CF205`，也有仓单平稳或下降的 `OI605/OI609`；member net OI 既可改善也可恶化，说明右尾保护对任何单一方向阈值都有强冲突。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage096_external_numeric_sequence_visual_atlas/qmt_roll_stage096_c9_minrisk_external_numeric_sequence_visual_atlas_report_stage096_external_numeric_sequence_visual_atlas_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage096_external_numeric_sequence_visual_atlas/qmt_roll_stage096_c9_minrisk_external_numeric_sequence_visual_atlas_summary_stage096_external_numeric_sequence_visual_atlas_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage096_external_numeric_sequence_visual_atlas/qmt_roll_stage096_c9_minrisk_external_numeric_sequence_visual_atlas_decision_stage096_external_numeric_sequence_visual_atlas_v1.json`
- sequence rows：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage096_external_numeric_sequence_visual_atlas/qmt_roll_stage096_c9_minrisk_external_numeric_sequence_visual_atlas_sequence_rows_stage096_external_numeric_sequence_visual_atlas_v1.csv`
- selected lots：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage096_external_numeric_sequence_visual_atlas/qmt_roll_stage096_c9_minrisk_external_numeric_sequence_visual_atlas_selected_lots_stage096_external_numeric_sequence_visual_atlas_v1.csv`
- atlas manifest：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage096_external_numeric_sequence_visual_atlas/qmt_roll_stage096_c9_minrisk_external_numeric_sequence_visual_atlas_atlas_manifest_stage096_external_numeric_sequence_visual_atlas_v1.csv`
- charts：
  - `qmt_roll_stage096_c9_minrisk_external_numeric_sequence_visual_atlas_official_context_chart_stage096_external_numeric_sequence_visual_atlas_v1.png`
  - `qmt_roll_stage096_c9_minrisk_external_numeric_sequence_visual_atlas_cohort_sequence_chart_stage096_external_numeric_sequence_visual_atlas_v1.png`
  - `qmt_roll_stage096_c9_minrisk_external_numeric_sequence_visual_atlas_selection_coverage_chart_stage096_external_numeric_sequence_visual_atlas_v1.png`
  - `qmt_roll_stage096_c9_minrisk_external_numeric_sequence_visual_atlas_atlas_page_001-013_stage096_external_numeric_sequence_visual_atlas_v1.png`

## 结论

- 本阶段结论：Stage096 成功把 Stage095 的全量数值字段转成 lot 级入场前序列 atlas，供人工视觉归因使用；外生数据资产可继续被研究，但当前视觉证据没有形成普世、跨产品、保护右尾的交易规则。
- 是否进入下一步：是，但只能进入预声明假设筛选，不进入 true engine/A/B。
- 下一步：Stage097 只允许写 `1-2` 个第一性经济假设的 preflight spec，并先检查 right-tail conflict、重复合约/同日样本影响、产品/年份集中度和 fallback/absent 排除规则；不得做阈值、TopN、rolling、flow 权重、收益分桶、产品/年份补丁、true engine、A/B 或正式候选。

## 过拟合反思

- 运行前判断：否。Stage096 的 cohort 在运行前固定，用于视觉覆盖 right-tail、bottom-loss、maxDD 和 fallback/absent，不按某个阈值优化收益。
- 运行后判断：否，本阶段没有生成规则、没有筛参数、没有真引擎；但若从当前图上直接抽“成交量增加/仓单减少/净持仓转正”阈值，就会立刻变成过拟合。
- 原因：图像显示右尾和亏损样本共享若干外生形态，且同一 cohort 内部差异很大。正确做法是先预声明经济假设和排除冲突，再决定是否值得做下一步。

## 继续价值反思

- 运行前判断：有价值。Stage095 已证明外生数值可点时化，Stage096 可以把字段从表格变成可人工判断的序列形态。
- 运行后判断：有价值但边界收窄。atlas 已经暴露出可解释性和右尾冲突，下一步最多做一次严格的 preflight spec；如果没有通过，就应停止这条外生序列规则化路线，保留为 forward watch/风险解释资产。
- 原因：这一步提供的是“看见结构”的能力，不是“规则成立”的证据。继续价值来自更严格地否决或保留少数第一性假设，而不是继续切片。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage096 摘要和 Stage097 边界。
- 是否更新 `research/registry.md`：否，不是正式候选、重要突破或路线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，不是正式候选、重要突破或跨线合并。
