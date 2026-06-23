# Stage094 数值字段解析 smoke 与 schema 审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-20 13:41 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage093 点时状态 schema 之后的固定数值字段 smoke/schema 审计；不是策略回测
- 是否重要突破：否。只是证明固定字段可解析，不是 alpha、规则或候选版本
- 是否触发A/B：否。无策略候选、无 true engine、无正式接入判断

## 外部调研与判断

- 参考资料：
  - AKShare futures 文档：`https://github.com/akfamily/akshare/blob/main/docs/data/futures/futures.md`
  - AKShare changelog：`https://akshare.akfamily.xyz/changelog.html`
  - CZCE 会员持仓排名页面：`https://www.czce.com.cn/cn/jysj/ccpm/H077003004index_1.htm`
  - CZCE 仓单日报页面：`https://www.czce.com.cn/cn/jysj/cdrb/H077003010index_1.htm`
  - GFEX 仓单日报页面：`https://www.gfex.com.cn/gfex/cdrb/hqsj_tjsj.shtml`
- 我的判断：
  - AKShare/GitHub wrapper 只适合作接口参考；本阶段仍以 Stage091 保存的官方 CZCE/GFEX raw 响应为权威。
  - 固定字段应先做 schema 和单位稳定性审计：CZCE/GFEX warehouse 的产品级仓单/变化，CZCE member_rank 的成交/持买/持卖排名字段。
  - 当前阶段不能解释这些数值是好信号或坏信号；任何阈值、TopN、rolling、flow 权重和收益分桶都会把数据工程污染成过拟合策略。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage094_numeric_parse_smoke_schema_audit.py`
- 修改脚本：无既有策略脚本
- 删除脚本：无
- 新增参数：
  - `NUMERIC_SCHEMA_VERSION=external_numeric_parse_smoke_schema_v1`
  - smoke plan：每个 `source_id/product_root/target_year` 的首尾 present 样本，加全部 `official_absent_before_first_manifest_presence` 样本
  - CZCE warehouse 固定字段：`warehouse_receipt_qty_sum`、`warehouse_change_qty_sum`、`warehouse_valid_forecast_qty_sum`
  - GFEX warehouse 固定字段：`warehouse_last_wbill_qty_sum`、`warehouse_reg_wbill_qty_sum`、`warehouse_logout_wbill_qty_sum`、`warehouse_wbill_qty_sum`、`warehouse_diff_qty_sum`
  - CZCE member_rank 固定字段：`member_rank_volume_sum`、`member_rank_volume_change_sum`、`member_rank_long_oi_sum`、`member_rank_long_oi_change_sum`、`member_rank_short_oi_sum`、`member_rank_short_oi_change_sum`
  - hard gates：`strategy_rule_created=0`、`true_engine_run=0`、`ab_triggered=0`、`order_api_called=0`、`ctp_connected=0`、`strategy_feature_usable=0`
- 修改参数：无策略参数
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage093 `2,590` 条 feature rows 中固定抽样的 `240` 条 smoke rows
- 账户规模：`150,000`
- 成本口径：只读复用官方基线；本阶段不产生交易
- 样本过滤：
  - 按 `source/product/year` 覆盖首尾样本选择，不按盈亏、回撤、右尾、产品表现或年份表现选择
  - `AP 2018` 与 `LC 2023` 的 `14` 条缺席样本保留为官方首次出现前缺席状态，不提取数值
- 策略/归因口径：
  - 本阶段无交易规则、无 true engine
  - CZCE warehouse 优先读取官方产品 `总计` 行；若产品段没有 `总计` 但有官方 `小计` 行，显式记录为 `official_product_subtotal_rows_no_total_row`
  - CZCE member_rank 读取官方 `合计` 行；GFEX warehouse 按 `varietyOrder` 聚合并排除交易所总计行

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`53.2560%`
- 其他关键指标：
  - 决策：`stage094_numeric_parse_smoke_ready_no_rule`
  - smoke_row_count：`240`
  - source_count：`3`
  - product_count：`10`
  - source_year_count：`21`
  - present_smoke_row_count：`226`
  - absent_state_smoke_row_count：`14`
  - field_schema_ready_count：`233`
  - numeric_ready_count：`226`
  - present_numeric_ready_count：`226/226`
  - warehouse_numeric_ready_count：`118`
  - member_rank_numeric_ready_count：`108`
  - parse_error_count：`0`
  - absent_state_handled：`1`
  - strategy_feature_usable：`0`
  - CZCE warehouse `SM` subtotal fallback：`5` 行，均显式标记 `official_product_subtotal_rows_no_total_row`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage094_numeric_parse_smoke_schema_audit/qmt_roll_stage094_c9_minrisk_numeric_parse_smoke_schema_audit_report_stage094_numeric_parse_smoke_schema_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage094_numeric_parse_smoke_schema_audit/qmt_roll_stage094_c9_minrisk_numeric_parse_smoke_schema_audit_summary_stage094_numeric_parse_smoke_schema_audit_v1.csv`
- parse rows：`qmt_roll_stage094_c9_minrisk_numeric_parse_smoke_schema_audit_parse_rows_stage094_numeric_parse_smoke_schema_audit_v1.csv`
- smoke plan：`qmt_roll_stage094_c9_minrisk_numeric_parse_smoke_schema_audit_smoke_plan_stage094_numeric_parse_smoke_schema_audit_v1.csv`
- source-year summary：`qmt_roll_stage094_c9_minrisk_numeric_parse_smoke_schema_audit_source_year_summary_stage094_numeric_parse_smoke_schema_audit_v1.csv`
- field summary：`qmt_roll_stage094_c9_minrisk_numeric_parse_smoke_schema_audit_field_summary_stage094_numeric_parse_smoke_schema_audit_v1.csv`
- 图像：
  - official numeric smoke path chart：`qmt_roll_stage094_c9_minrisk_numeric_parse_smoke_schema_audit_official_numeric_smoke_path_chart_stage094_numeric_parse_smoke_schema_audit_v1.png`
  - readiness heatmap：`qmt_roll_stage094_c9_minrisk_numeric_parse_smoke_schema_audit_readiness_heatmap_stage094_numeric_parse_smoke_schema_audit_v1.png`
  - field availability chart：`qmt_roll_stage094_c9_minrisk_numeric_parse_smoke_schema_audit_field_availability_chart_stage094_numeric_parse_smoke_schema_audit_v1.png`
  - numeric distribution chart：`qmt_roll_stage094_c9_minrisk_numeric_parse_smoke_schema_audit_numeric_distribution_chart_stage094_numeric_parse_smoke_schema_audit_v1.png`

## 视觉观察

- official numeric smoke path chart：官方权益、回撤和 broker10 只作背景；底部年度柱显示 `2018-2026` 的 CZCE member/warehouse present smoke 均有 ready，GFEX 只在 `2023-2025` 出现，符合产品上市和仓单时序。
- readiness heatmap：present-row numeric ready ratio 全部为 `100%`；GFEX 在非适用年份显示空格，不被填补成伪覆盖。
- field availability chart：CZCE member_rank 六个数值字段各有 `108` 个 smoke 值；CZCE warehouse 三个字段有 `108` 个 smoke 值；GFEX warehouse 五个 JSON 字段有 `10` 个 smoke 值。所有字段 `trading_rule_allowed=0`。
- numeric distribution chart：仓单数量、仓单变化、GFEX 仓单量和会员排名字段量级差异很大，说明下一步 full extraction 必须先做单位、标准化和跨源稳定性审计，不能直接把数值大小解释成信号。

## 结论

- 本阶段结论：
  - 固定 smoke plan 下，所有 `226/226` 条 present 样本数值解析就绪，`14` 条 absent-before-first 样本被正确保留为无数值状态。
  - CZCE warehouse 存在 `SM 2019-2021` 无产品总计但有官方小计的格式差异；当前只作为解析 schema 事实记录，full extraction 时必须继续保留 aggregation_source。
  - 当前 artifact 仍不是策略可用特征，因为没有阈值、没有收益分桶、没有 true engine，且 `strategy_feature_usable=0`。
- 是否进入下一步：可以进入 Stage095 全量 feature-row 数值抽取与稳定性审计；仍不能进入策略 true engine、A/B 或正式候选。
- 下一步：
  - 把 Stage094 固定解析器扩展到 Stage093 全部 `2,590` 条 feature rows，输出 point-in-time numeric feature table。
  - 只审计字段缺失、aggregation_source、单位、跨年/跨产品稳定性、right-tail 覆盖和视觉分布。
  - 不做阈值、TopN、rolling、flow 权重、产品/年份补丁、收益分桶或任何策略回测。

## 过拟合反思

- 运行前判断：否。样本选择按 source/product/year 首尾覆盖和官方缺席状态固定，不按最终收益或回撤挑样本。
- 运行后判断：否，但仍需要警惕数值解释阶段的过拟合。
- 原因：本阶段只做表头定位、单位记录、官方总计/小计/合计聚合和可视化，不生成交易条件；`SM` subtotal fallback 是官方 raw 格式差异处理，不是按结果修补。

## 继续价值反思

- 运行前判断：有价值。没有数值解析 smoke，就不能安全推进全量 point-in-time feature table。
- 运行后判断：有价值。三类 source 的固定字段都能解析，且格式差异已被显式记录，下一步可以从数据工程进入全量稳定性审计。
- 原因：这条路线正在把外生 raw 数据变成可审计资产；它比从 closed-lot 或回撤片段反推规则更接近“可穿越周期”的信息源建设。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage094 摘要和后续边界。
- 是否更新 `research/registry.md`：否。不是重要突破、正式候选或跨线合入。
- 是否追加根目录 `memory.md/back_log.md`：否。没有策略候选或正式口径变化。
