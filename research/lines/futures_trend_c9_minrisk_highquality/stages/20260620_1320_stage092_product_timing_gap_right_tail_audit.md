# Stage092 产品时序缺口与右尾安全审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-20 13:20 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage091 product hit/miss 缺口分类与右尾安全审计；不是策略回测
- 是否重要突破：否。只是把 raw 覆盖缺口分类清楚，允许下一步设计只读 feature schema
- 是否触发A/B：否。无策略候选、无 true engine、无正式接入判断

## 外部调研与判断

- 参考资料：
  - AKShare futures 文档：`https://github.com/akfamily/akshare/blob/main/docs/data/futures/futures.md`
  - AKShare changelog：`https://akshare.akfamily.xyz/changelog.html`
  - CZCE 会员持仓排名页面：`https://www.czce.com.cn/cn/jysj/ccpm/H077003004index_1.htm`
  - CZCE 仓单日报页面：`https://www.czce.com.cn/cn/jysj/cdrb/H077003010index_1.htm`
  - GFEX 仓单日报页面：`https://www.gfex.com.cn/gfex/cdrb/hqsj_tjsj.shtml`
- 我的判断：
  - Stage091 已经证明 raw 下载与解析不是阻塞；Stage092 的核心是把 product miss 定义成可审计的数据状态，而不是信号。
  - `AP 2018` 与 `LC 2023` 缺口都发生在本 manifest 首次出现对应产品之前，属于时序状态，不是 raw parse failure。
  - gap-linked lot 不是右尾 top10%，但这也不能反推“缺席=坏信号”；最多允许下一步设计明确状态字段。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage092_product_timing_gap_right_tail_audit.py`
- 修改脚本：无既有策略脚本
- 删除脚本：无
- 新增参数：
  - coverage class：`present`、`official_absent_before_first_manifest_presence`、`raw_parse_gap`、`official_absent_after_prior_presence`、`official_absent_no_present_in_manifest`
  - right-tail 判定：closed lots realized PnL rank pct `>=0.90`
- 修改参数：无策略参数
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage091 product-date status，覆盖 Stage090 入场前 `7` 交易日 raw manifest
- 账户规模：`150,000`
- 成本口径：只读复用官方基线；本阶段不产生交易
- 样本过滤：只审计 Stage091 自然产生的 `14` 个 product-date gap；不按收益、回撤或品种表现新增/删除缺口
- 策略/归因口径：
  - 本阶段无交易规则、无 true engine
  - product-date gap 绑定回 Stage090 lot-window links、official closed lots 和官方权益路径
  - right-tail 审计只用于确认缺口是否阻断右尾安全，不生成交易条件

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`53.2560%`
- 其他关键指标：
  - 决策：`stage092_gaps_classified_as_pre_first_presence_schema_design_allowed_no_rule`
  - expanded_product_date_count：`2,028`
  - gap_product_date_count：`14`
  - gap_lot_window_link_count：`14`
  - gap_unique_lot_count：`2`
  - gap_group_count：`2`
  - gap_pre_first_presence_count：`14`
  - gap_raw_parse_count：`0`
  - gap_after_prior_presence_count：`0`
  - right_tail_gap_group_count：`0`
  - gap_linked_realized_pnl_sum：`-981,460.00`，为 unique lot 口径
  - classification_complete：`1`
  - feature_binding_schema_design_allowed：`1`
  - gap groups：
    - `czce_warehouse AP 2018`：`7` 个缺口日期，关联 lot `11 AP805.CZCE long 2018-03-29`，realized PnL `-1,660`，PnL rank pct `0.4912`，非右尾
    - `gfex_warehouse LC 2023`：`7` 个缺口日期，关联 lot `324 lc2401.GFEX short 2023-11-07`，realized PnL `-979,800`，PnL rank pct `0.0050`，非右尾

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage092_product_timing_gap_right_tail_audit/qmt_roll_stage092_c9_minrisk_product_timing_gap_right_tail_audit_report_stage092_product_timing_gap_right_tail_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage092_product_timing_gap_right_tail_audit/qmt_roll_stage092_c9_minrisk_product_timing_gap_right_tail_audit_summary_stage092_product_timing_gap_right_tail_audit_v1.csv`
- orders：无
- daily：无新交易日线，仅复用官方路径
- quality：
  - `qmt_roll_stage092_c9_minrisk_product_timing_gap_right_tail_audit_product_date_status_stage092_product_timing_gap_right_tail_audit_v1.csv`
  - `qmt_roll_stage092_c9_minrisk_product_timing_gap_right_tail_audit_gap_product_dates_stage092_product_timing_gap_right_tail_audit_v1.csv`
  - `qmt_roll_stage092_c9_minrisk_product_timing_gap_right_tail_audit_gap_lot_window_links_stage092_product_timing_gap_right_tail_audit_v1.csv`
  - `qmt_roll_stage092_c9_minrisk_product_timing_gap_right_tail_audit_gap_group_summary_stage092_product_timing_gap_right_tail_audit_v1.csv`
  - `qmt_roll_stage092_c9_minrisk_product_timing_gap_right_tail_audit_gap_lot_summary_stage092_product_timing_gap_right_tail_audit_v1.csv`
  - official gap path chart：`qmt_roll_stage092_c9_minrisk_product_timing_gap_right_tail_audit_official_gap_path_chart_stage092_product_timing_gap_right_tail_audit_v1.png`
  - gap timeline chart：`qmt_roll_stage092_c9_minrisk_product_timing_gap_right_tail_audit_gap_timeline_chart_stage092_product_timing_gap_right_tail_audit_v1.png`
  - gap lot pnl chart：`qmt_roll_stage092_c9_minrisk_product_timing_gap_right_tail_audit_gap_lot_pnl_chart_stage092_product_timing_gap_right_tail_audit_v1.png`
  - classification chart：`qmt_roll_stage092_c9_minrisk_product_timing_gap_right_tail_audit_classification_chart_stage092_product_timing_gap_right_tail_audit_v1.png`

## 视觉观察

- official gap path chart：两个 gap-linked lot 分别在 `2018-03-29` 和 `2023-11-07`，没有覆盖主要右尾爆发点；`LC` 缺口发生在权益高位且 broker10 约 `58.29%`，但该 lot 本身是大亏，不可直接交易化。
- gap timeline chart：`AP` 在 `2018-03` 为红点，但 `2018-09` 后连续出现绿点；`LC` 在 `2023-11` 为红点，`2024-12` 与 `2025-12` 出现绿点。形态符合 first manifest presence 前缺席。
- gap lot pnl chart：两个关联 lot 的 PnL rank pct 均低于右尾 top10 线；`lc2401.GFEX` 的 realized PnL 为 `-979,800`，但这只证明右尾安全不被阻断，不证明仓单缺席可做空/降仓。
- classification chart：`2,014` 个 product-date 为 `present`，`14` 个为 `official_absent_before_first_manifest_presence`，没有 raw parse gap 或 after-prior-presence gap。

## 结论

- 本阶段结论：
  - Stage091 的两个 product-year gap 已全部分类为 `official_absent_before_first_manifest_presence`。
  - 没有 raw parse gap，没有“已出现后又缺失”的异常。
  - 关联 lot 不是右尾 top10%，因此缺口不阻断下一步 schema 设计。
  - 仍不得把产品缺席、仓单缺席、first presence、PnL rank 或 gap-linked loss 写成交易规则。
- 是否进入下一步：可以进入 Stage093 point-in-time feature schema 设计与只读绑定，不进入 true engine、A/B 或正式候选。
- 下一步：
  - 设计固定 feature schema：`source_ready`、`product_present_state`、`days_since_first_manifest_presence`、`raw_parse_ready`、`symbol_hit`、基础仓单/会员排名字段占位。
  - 先只读绑定到 C9 entry 前窗口并做覆盖图，不计算阈值、不跑交易引擎。

## 过拟合反思

- 运行前判断：否。缺口集合由 Stage091 全量覆盖自然产生，不按收益选择。
- 运行后判断：否，但有新的误读风险。
- 原因：本阶段没有新增交易规则或阈值；风险在于看到 `LC` 缺口关联大亏后，把“缺席状态”包装成降仓信号，所以明确禁止。

## 继续价值反思

- 运行前判断：有价值。没有缺口分类，就无法区分真实官方缺席、产品时序和 raw parse failure。
- 运行后判断：有价值。分类完成，feature schema 可以进入只读设计。
- 原因：数据链路从 raw 下载推进到状态定义；下一步能够用固定 schema 绑定，而不是继续在缺口上凭直觉切片。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage092 摘要和后续边界。
- 是否更新 `research/registry.md`：否。不是重要突破、正式候选或跨线合入。
- 是否追加根目录 `memory.md/back_log.md`：否。没有策略候选或正式口径变化。
