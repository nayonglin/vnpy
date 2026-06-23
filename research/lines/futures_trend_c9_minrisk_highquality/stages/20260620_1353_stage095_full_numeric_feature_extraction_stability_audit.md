# Stage095 全量数值特征抽取与稳定性审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-20 13:53 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage094 固定解析器扩展到 Stage093 全部 feature rows 的只读数据工程；不是策略回测
- 是否重要突破：否。完成全量点时数值资产，不是 alpha、规则或候选版本
- 是否触发A/B：否。无策略候选、无 true engine、无正式接入判断

## 外部调研与判断

- 参考资料：
  - CZCE 仓单日报官方页面：`https://www.czce.com.cn/cn/jysj/cdrb/H077003010index_1.htm`
  - CZCE 持仓排名官方页面：`https://www.czce.com.cn/cn/jysj/ccpm/H077003004index_1.htm`
  - GFEX 仓单日报官方页面：`https://www.gfex.com.cn/gfex/cdrb/hqsj_tjsj.shtml`
  - AKShare 期货数据文档：`https://akshare.akfamily.xyz/data/futures/futures.html`
- 我的判断：
  - 官方页面字段与 Stage091 raw 中的 `仓单数量/当日增减/有效预报`、`交易量/持买仓量/持卖仓量`、GFEX 仓单 JSON 字段方向一致，Stage095 可以继续使用 Stage094 固定解析器。
  - AKShare 仍只作接口说明参考，不作为权威数值源；权威仍是本地保存的交易所 raw response、sha256 和 schema hash。
  - 全量抽取后仍不能直接解释数值大小是好信号或坏信号；下一步最多做只读稳定性、时序可视化和经济语义预检。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage095_full_numeric_feature_extraction_stability_audit.py`
- 修改脚本：无既有策略脚本
- 删除脚本：无
- 新增参数：
  - `NUMERIC_SCHEMA_VERSION=external_numeric_full_feature_schema_v1`
  - `PARSER_SCHEMA_VERSION=external_numeric_parse_smoke_schema_v1`
  - 输入：Stage093 全部 `2,590` 条 feature rows
  - parse group key：`source_id/exchange/product_root/target_date/raw_file`
  - 固定字段：沿用 Stage094 的 CZCE/GFEX warehouse 与 CZCE member_rank 数值字段
  - hard gates：`strategy_rule_created=0`、`true_engine_run=0`、`ab_triggered=0`、`order_api_called=0`、`ctp_connected=0`、`strategy_feature_usable=0`
- 修改参数：无策略参数
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage093 全部 point-in-time feature rows，共 `2,590` 行；对应 `2,028` 个唯一 parse groups
- 账户规模：`150,000`
- 成本口径：只读复用官方基线；本阶段不产生交易
- 样本过滤：无。全量使用 Stage093 已冻结的全部 feature rows，不按盈亏、回撤、右尾、产品或年份筛选
- 策略/归因口径：
  - 本阶段无交易规则、无 true engine
  - 只做 raw_file 级缓存解析、字段 ready、aggregation_source、field summary、right-tail coverage 和视觉审计
  - PnL rank 只用于覆盖审计，不做收益分桶或阈值

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`53.2560%`
- 其他关键指标：
  - 决策：`stage095_full_numeric_features_ready_no_rule`
  - feature_row_count：`2,590`
  - parse_group_count：`2,028`
  - source_count：`3`
  - product_count：`10`
  - linked_lot_count：`188`
  - present_feature_row_count：`2,576`
  - absent_state_feature_row_count：`14`
  - numeric_ready_feature_row_count：`2,576`
  - present_numeric_ready_feature_row_count：`2,576/2,576`
  - warehouse_numeric_ready_feature_row_count：`1,302`
  - member_rank_numeric_ready_feature_row_count：`1,274`
  - parse_error_group_count：`0`
  - absent_state_handled：`1`
  - lot_all_present_numeric_ready_count：`188/188`
  - right_tail_lot_count：`19`
  - right_tail_all_present_numeric_ready_count：`19/19`
  - strategy_feature_usable：`0`
  - aggregation_source：
    - `official_product_total_row`：CZCE member `1,274` 行，CZCE warehouse `1,211` 行
    - `official_product_subtotal_rows_no_total_row`：CZCE warehouse `56` 行，均为 schema fallback，不是信号
    - `sum_variety_rows_excluding_exchange_total`：GFEX warehouse `35` 行
    - official absent/no numeric：`14` 行

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage095_full_numeric_feature_extraction_stability_audit/qmt_roll_stage095_c9_minrisk_full_numeric_feature_extraction_stability_audit_report_stage095_full_numeric_feature_extraction_stability_audit_v1.md`
- summary：`qmt_roll_stage095_c9_minrisk_full_numeric_feature_extraction_stability_audit_summary_stage095_full_numeric_feature_extraction_stability_audit_v1.csv`
- feature rows：`qmt_roll_stage095_c9_minrisk_full_numeric_feature_extraction_stability_audit_feature_rows_stage095_full_numeric_feature_extraction_stability_audit_v1.csv`
- parse groups：`qmt_roll_stage095_c9_minrisk_full_numeric_feature_extraction_stability_audit_parse_groups_stage095_full_numeric_feature_extraction_stability_audit_v1.csv`
- lot summary：`qmt_roll_stage095_c9_minrisk_full_numeric_feature_extraction_stability_audit_lot_summary_stage095_full_numeric_feature_extraction_stability_audit_v1.csv`
- source-year summary：`qmt_roll_stage095_c9_minrisk_full_numeric_feature_extraction_stability_audit_source_year_summary_stage095_full_numeric_feature_extraction_stability_audit_v1.csv`
- product-year summary：`qmt_roll_stage095_c9_minrisk_full_numeric_feature_extraction_stability_audit_product_year_summary_stage095_full_numeric_feature_extraction_stability_audit_v1.csv`
- field summary：`qmt_roll_stage095_c9_minrisk_full_numeric_feature_extraction_stability_audit_field_summary_stage095_full_numeric_feature_extraction_stability_audit_v1.csv`
- aggregation source summary：`qmt_roll_stage095_c9_minrisk_full_numeric_feature_extraction_stability_audit_aggregation_source_summary_stage095_full_numeric_feature_extraction_stability_audit_v1.csv`
- 图像：
  - official numeric full path chart：`qmt_roll_stage095_c9_minrisk_full_numeric_feature_extraction_stability_audit_official_numeric_full_path_chart_stage095_full_numeric_feature_extraction_stability_audit_v1.png`
  - readiness heatmap：`qmt_roll_stage095_c9_minrisk_full_numeric_feature_extraction_stability_audit_readiness_heatmap_stage095_full_numeric_feature_extraction_stability_audit_v1.png`
  - product-year heatmap：`qmt_roll_stage095_c9_minrisk_full_numeric_feature_extraction_stability_audit_product_year_heatmap_stage095_full_numeric_feature_extraction_stability_audit_v1.png`
  - aggregation source chart：`qmt_roll_stage095_c9_minrisk_full_numeric_feature_extraction_stability_audit_aggregation_source_chart_stage095_full_numeric_feature_extraction_stability_audit_v1.png`
  - right-tail coverage chart：`qmt_roll_stage095_c9_minrisk_full_numeric_feature_extraction_stability_audit_right_tail_coverage_chart_stage095_full_numeric_feature_extraction_stability_audit_v1.png`
  - numeric distribution chart：`qmt_roll_stage095_c9_minrisk_full_numeric_feature_extraction_stability_audit_numeric_distribution_chart_stage095_full_numeric_feature_extraction_stability_audit_v1.png`

## 视觉观察

- official numeric full path chart：官方权益、回撤和 broker10 仍只作背景；年度 ready 柱显示 `2019-2021` feature rows 较多，说明覆盖随 C9 入场分布自然变化，不是单一年份抽样。
- readiness heatmap：CZCE member_rank 与 CZCE warehouse 的 `2018-2026` present rows 全部 `100%` ready；GFEX warehouse 只在 `2023-2025` 出现，非适用年份保持空白。
- product-year heatmap：所有有 present rows 的 source/product/year 都是 `100%` ready；缺口为空，说明 Stage094 固定解析器可全量复用。
- aggregation source chart：主要来源是官方产品总计；`56` 行 CZCE warehouse 小计 fallback 明显但规模小，应在后续审计中保留为 schema 类别，不得被交易化。
- right-tail coverage chart：`188/188` 个 lot 的 present numeric ready ratio 均为 `1.0`，右尾 top10 `19/19` 全覆盖。该图只证明覆盖安全，不证明任何数值和 PnL 的关系。
- numeric distribution chart：仓单量、仓单变化、GFEX JSON 仓单、会员排名字段量级不同；后续若做经济语义，需要先做单位和方向一致性，而不是直接用原始数值阈值。

## 结论

- 本阶段结论：
  - 全量点时数值特征表已生成，present rows `2,576/2,576` ready，parse error `0`。
  - 右尾覆盖安全：`19/19` 个 right-tail lots 均 all-present-numeric-ready。
  - 当前 artifact 仍不是策略可用特征，因为没有阈值、没有收益分桶、没有 true engine，且 `strategy_feature_usable=0`。
- 是否进入下一步：可以进入 Stage096 只读外生数值序列视觉 atlas / 经济语义预检；仍不能进入策略 true engine、A/B 或正式候选。
- 下一步：
  - 以 lot 为单位画入场前 `7` 个交易日的 warehouse/member 数值序列 atlas，优先看 maxDD 段、right-tail 样本、亏损样本的形态是否存在“人眼可见但非阈值化”的普世差异。
  - 只允许做单位、方向、aggregation_source、产品/年份稳定性和右尾保护审计。
  - 不做阈值、TopN、rolling、flow 权重、收益分桶、产品/年份补丁、true engine 或 A/B。

## 过拟合反思

- 运行前判断：否。Stage095 处理 Stage093 全量 rows，不按结果挑样本。
- 运行后判断：否。所有 present rows 全部解析，没有选择性排除亏损或保留右尾。
- 原因：本阶段只证明字段可解析、可点时化、可覆盖右尾；没有从 PnL 反推数值条件。`SM` 小计 fallback 和 AP/LC absent-before-first 都只是官方 raw 格式/时序事实。

## 继续价值反思

- 运行前判断：有价值。没有全量数值表，后续任何外生供需/持仓假设都无法防止泄漏和覆盖偏差。
- 运行后判断：有价值。数据阻塞基本解除，下一步可以开始更接近“默会知识”的视觉序列审计，而不是继续停留在字段存在性。
- 原因：现在有了完整的入场前 `7` 日外生数值序列，可以用视觉方式观察高质量信号前的供需/持仓形态是否有普世结构；这比从 closed-lot 盈亏标签反推规则更稳。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage095 摘要和后续边界。
- 是否更新 `research/registry.md`：否。不是重要突破、正式候选或跨线合入。
- 是否追加根目录 `memory.md/back_log.md`：否。没有策略候选或正式口径变化。
