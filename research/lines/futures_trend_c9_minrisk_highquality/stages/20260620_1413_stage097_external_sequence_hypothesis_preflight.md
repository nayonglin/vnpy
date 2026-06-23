# Stage097 外生序列预声明假设 preflight

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 14:13 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读预声明假设筛选；不是真引擎、不生成交易规则
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - CME Volume and Open Interest：`https://www.cmegroup.com/market-data/volume-open-interest.html`
  - CME Open Interest 教育材料：`https://www.cmegroup.com/education/courses/introduction-to-futures/open-interest`
  - CFTC COT 报告说明：`https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm`
  - StoneX warehouse receipt 说明：`https://www.stonex.com/en-us/business/financial-glossary/warehouse-receipt/`
  - 郑商所仓单日报/持仓排名、广期所仓单日报仍作为本线 raw provenance 来源。
- 我的判断：OI/成交量/会员排名适合解释参与度、趋势确认或拥挤状态，仓单适合解释交割供给；但公开资料也支持这些字段必须放在上下文中理解，不能单独作为交易信号。因此 Stage097 只能用符号级、低自由度 preflight 检查右尾冲突，不能从 Stage096 atlas 上抽阈值。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage097_external_sequence_hypothesis_preflight.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - H1：`H1_directional_supply_member_alignment`，入场前 7 日仓单供给方向与会员净持仓方向同时支持交易方向才算 `both_support`。
  - H2：`H2_participation_without_external_alignment`，会员成交量上升但没有 H1 full alignment 时记为 `participation_without_full_alignment`。
  - 只使用首末变化的自然符号：`>0/<0/0/missing`，不设阈值、不设 TopN、不滚动优化。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage096 lot 级入场前 `7` 个交易日外生序列。
- 账户规模：沿用基准路径，仅作背景。
- 成本口径：沿用基准统计，总滑点 `2,730,130`。
- 样本过滤：固定 Stage096 selected union `50` 个视觉 lot，同时保留全体 `188` 个 lot 的 preflight 状态；不按收益筛选生成规则。
- 策略/归因口径：只读 preflight，`preflight_only=1`、`strategy_rule_allowed=0`、`true_engine_allowed=0`。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`53.2560%`
- 其他关键指标：
  - `decision=stage097_hypothesis_preflight_mixed_conflict_no_rule`
  - `hypothesis_count=2`
  - `hypotheses_promoted_to_true_engine=0`
  - `hypotheses_kept_for_predeclared_watch=2`
  - `selected_lot_count=50`
  - `all_lot_count=188`
  - `h1_state_count=4`
  - `h2_state_count=3`
  - `h1_right_tail_both_support_count=6`
  - `h1_right_tail_both_headwind_count=5`
  - `h2_right_tail_participation_without_alignment_count=9`
  - `right_tail_conflict_detected=1`
  - `product_year_concentration_risk=1`
  - `strategy_feature_usable=0`
  - `official_config_changed=0`、`strategy_rule_created=0`、`true_engine_run=0`、`ab_triggered=0`、`order_api_called=0`、`ctp_connected=0`

## 视觉观察

- official path chart：H1 的 `both_support`、`both_headwind`、`mixed_or_neutral` 都落在重要权益台阶上，右尾并没有被某一个“好状态”独占；颜色在 2021-2026 的右尾区间混杂。
- right-tail conflict chart：H1 的 `both_support` 有 `6` 个 right-tail，但 `both_headwind` 也有 `5` 个 right-tail，`mixed_or_neutral` 还有 `7` 个 right-tail；任何把非 support 直接降仓/过滤的规则都会砍掉右尾。
- H2 conflict chart：`participation_without_full_alignment` 有 `9` 个 right-tail，同时 bottom-loss 只有 `4` 个；“成交量上升但没有外生确认”不能作为坏信号。
- cohort state chart：bottom-loss、maxDD context、right-tail 都分布在多个状态里；H2 中 maxDD context 主要落在 `not_participation_without_full_alignment`，与“参与度无确认是坏信号”的直觉相反。
- product-year concentration chart：H1 状态在 `SM 2020/2021/2022`、`AP 2022/2025`、`MA 2022/2023`、`OI 2021/2023/2024/2026` 等产品年份上稀疏分布，单元格样本小，不能据此做产品/年份补丁。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage097_external_sequence_hypothesis_preflight/qmt_roll_stage097_c9_minrisk_external_sequence_hypothesis_preflight_report_stage097_external_sequence_hypothesis_preflight_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage097_external_sequence_hypothesis_preflight/qmt_roll_stage097_c9_minrisk_external_sequence_hypothesis_preflight_summary_stage097_external_sequence_hypothesis_preflight_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage097_external_sequence_hypothesis_preflight/qmt_roll_stage097_c9_minrisk_external_sequence_hypothesis_preflight_decision_stage097_external_sequence_hypothesis_preflight_v1.json`
- lot preflight：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage097_external_sequence_hypothesis_preflight/qmt_roll_stage097_c9_minrisk_external_sequence_hypothesis_preflight_lot_preflight_stage097_external_sequence_hypothesis_preflight_v1.csv`
- hypothesis summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage097_external_sequence_hypothesis_preflight/qmt_roll_stage097_c9_minrisk_external_sequence_hypothesis_preflight_hypothesis_summary_stage097_external_sequence_hypothesis_preflight_v1.csv`
- cohort state summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage097_external_sequence_hypothesis_preflight/qmt_roll_stage097_c9_minrisk_external_sequence_hypothesis_preflight_cohort_state_summary_stage097_external_sequence_hypothesis_preflight_v1.csv`
- product-year summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage097_external_sequence_hypothesis_preflight/qmt_roll_stage097_c9_minrisk_external_sequence_hypothesis_preflight_product_year_summary_stage097_external_sequence_hypothesis_preflight_v1.csv`
- charts：
  - `qmt_roll_stage097_c9_minrisk_external_sequence_hypothesis_preflight_official_path_chart_stage097_external_sequence_hypothesis_preflight_v1.png`
  - `qmt_roll_stage097_c9_minrisk_external_sequence_hypothesis_preflight_cohort_state_chart_stage097_external_sequence_hypothesis_preflight_v1.png`
  - `qmt_roll_stage097_c9_minrisk_external_sequence_hypothesis_preflight_right_tail_conflict_chart_stage097_external_sequence_hypothesis_preflight_v1.png`
  - `qmt_roll_stage097_c9_minrisk_external_sequence_hypothesis_preflight_product_year_concentration_chart_stage097_external_sequence_hypothesis_preflight_v1.png`

## 结论

- 本阶段结论：两个从 Stage096 atlas 提出的低自由度假设都不能 promotion。H1 没有把右尾和坏尾分开；H2 把大量 right-tail 也标成“参与度上升但无外生确认”。当前外生仓单/会员排名 7 日符号序列不能进入 true engine、A/B 或正式候选。
- 是否进入下一步：是，但不沿着 H1/H2 调参。只能保留 forward-watch 标签，或换更细颗粒的真实外生源。
- 下一步：Stage098 若继续外生路线，应优先做“信息粒度是否不足”的只读归因：检查仓单/会员排名按产品总计是否过粗、是否需要会员类别/席位结构、主次合约 OI 迁移、库存/基差/期限结构联动或授权盘口/队列/成交流。不得把 H1/H2 改阈值、改窗口、改产品年份后重试。

## 过拟合反思

- 运行前判断：否。H1/H2 在运行前固定，只用自然符号，不使用收益阈值、TopN、rolling 或参数扫描。
- 运行后判断：否，本阶段没有生成策略规则；但继续围绕 H1/H2 改符号、改窗口、排除产品年份，就是过拟合。
- 原因：右尾冲突是结构性的，不是阈值没调好。Stage097 的职责是及时否决，而不是把图上的混杂关系救成规则。

## 继续价值反思

- 运行前判断：有价值。Stage096 已给出 atlas，Stage097 可以低成本判断是否值得进入真引擎。
- 运行后判断：本分支继续调参没有价值；作为 forward-watch 和数据粒度诊断仍有价值。
- 原因：仓单/会员排名产品总计级别过粗，无法稳定区分高质量信号和坏尾；下一步价值在更细信息源或明确停止，不在 H1/H2 参数化。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage097 摘要和 Stage098 边界。
- 是否更新 `research/registry.md`：否，不是正式候选、重要突破或路线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，不是正式候选、重要突破或跨线合并。
