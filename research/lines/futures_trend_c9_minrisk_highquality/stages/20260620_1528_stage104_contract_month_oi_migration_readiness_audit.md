# Stage104 合约月份 OI 迁移数据契约审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 15:28 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读合约粒度 OI 面板覆盖/数据契约审计；不是真引擎、不生成交易规则
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - CME Open Interest：`https://www.cmegroup.com/education/courses/introduction-to-futures/open-interest`
  - DCE Daily Data：`https://www.dce.com.cn/dceg/channel/list/471.html`
  - Bourse de Montréal futures roll analysis：`https://www.m-x.ca/f_publications_en/cgb_guide_futures_roll_analysis_en.pdf`
  - Quantpedia continuous futures methodology：`https://quantpedia.com/continuous-futures-contracts-methodology-for-backtesting/`
- 我的判断：open interest 与换月迁移有第一性价值，因为它描述资金承接、流动性迁移和主次合约权力转移；但它是日级、合约级状态，不是分钟触价执行语义。当前必须先确认入场前可见、目标合约可绑定、跨年跨品种覆盖和 raw provenance，再讨论预声明假设。把主力/次主力/份额直接当阈值就是过拟合。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage104_contract_month_oi_migration_readiness_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增输出：
  - `features`
  - `contract_panel_inventory`
  - `product_year_coverage`
  - `rank_summary`
  - `promotion_gate`
  - `official_path_panel_coverage_chart`
  - `product_year_coverage_heatmap`
  - `rank_share_chart`
  - `promotion_gate_chart`
- 新增参数：无策略参数；仅设置数据契约门槛 `target_contract_coverage_ge95pct` 与 `source_date_age_le7_all_orders`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage102 timestamp-ready `219` 笔订单；合约日线来自本地 `examples/portfolio_backtesting/downloaded_futures/tqsdk_daily_2010_2026_04/`。
- 可见性：每笔订单只取 `official_open_date` 之前最近一个可见日的合约 OI 面板。
- 账户规模与成本口径：沿用既有资金路径作为背景；不改变交易、不复跑引擎。
- 策略/归因口径：`panel_feature_rule_allowed=0`、`true_engine_run=0`、`strategy_feature_usable=0`。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：closed-lot win rate `36.0902%`
- 其他关键指标：
  - `decision=stage104_contract_month_oi_migration_panel_partial_ready_no_rule`
  - `timestamp_ready_order_count=219`
  - `product_count=19`
  - `local_contract_daily_file_count=1,017`
  - `local_contract_panel_product_count=19`
  - `target_contract_found_active_count=188`
  - `target_contract_panel_ready_count=186`
  - `target_contract_panel_ready_rate_pct=84.9315%`
  - `target_contract_missing_count=31`
  - `source_age_le7_count=216`
  - `active_contract_ge2_count=218`
  - `right_tail_panel_ready_count=18/18`
  - `bottom_loss_panel_ready_count=14/18`
  - `target_rank1_count=178`
  - `target_rank2_count=9`
  - `target_rank3plus_count=1`
  - `product_year_hard_gap_cell_count=19`
  - `promotion_gate_pass_count=2/7`
  - `official_config_changed=0`、`strategy_rule_created=0`、`true_engine_run=0`、`ab_triggered=0`、`order_api_called=0`、`ctp_connected=0`

## 视觉观察

- official path panel coverage chart：资金/回撤/broker10 仍只是背景路径；panel-ready 点覆盖主要右尾样本，但 2020 与 2026 仍有红色缺口，不能直接进入规则。
- product-year coverage heatmap：多数中段年份覆盖较好，缺口集中在早期/近端目标合约文件缺失；这属于数据覆盖边界，不是品种年份筛选理由。
- rank/share chart：ready 样本中多数目标合约已经是 OI rank1，少量 rank2/rank3plus 也存在；这个分布只能说明当前交易多在主力附近，不能说明 rank1 更好或 rank2 更差。
- promotion gate chart：本地合约日线面板存在、右尾覆盖通过，但目标合约覆盖未达 95%、product-year 有硬缺口、raw hash/source permission manifest 不完整，因此交易规则、true engine、A/B 全部 blocked。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage104_contract_month_oi_migration_readiness_audit/qmt_roll_stage104_c9_minrisk_contract_month_oi_migration_readiness_audit_report_stage104_contract_month_oi_migration_readiness_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage104_contract_month_oi_migration_readiness_audit/qmt_roll_stage104_c9_minrisk_contract_month_oi_migration_readiness_audit_summary_stage104_contract_month_oi_migration_readiness_audit_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage104_contract_month_oi_migration_readiness_audit/qmt_roll_stage104_c9_minrisk_contract_month_oi_migration_readiness_audit_decision_stage104_contract_month_oi_migration_readiness_audit_v1.json`
- features：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage104_contract_month_oi_migration_readiness_audit/qmt_roll_stage104_c9_minrisk_contract_month_oi_migration_readiness_audit_features_stage104_contract_month_oi_migration_readiness_audit_v1.csv`
- charts：
  - `qmt_roll_stage104_c9_minrisk_contract_month_oi_migration_readiness_audit_official_path_panel_coverage_chart_stage104_contract_month_oi_migration_readiness_audit_v1.png`
  - `qmt_roll_stage104_c9_minrisk_contract_month_oi_migration_readiness_audit_product_year_coverage_heatmap_stage104_contract_month_oi_migration_readiness_audit_v1.png`
  - `qmt_roll_stage104_c9_minrisk_contract_month_oi_migration_readiness_audit_rank_share_chart_stage104_contract_month_oi_migration_readiness_audit_v1.png`
  - `qmt_roll_stage104_c9_minrisk_contract_month_oi_migration_readiness_audit_promotion_gate_chart_stage104_contract_month_oi_migration_readiness_audit_v1.png`

## 结论

- 本阶段结论：合约月份 OI 迁移路线从“可能需要采购”变成“本地已有部分合约日线面板，可继续做数据契约修复/只读假设预检”，但当前仍不能写交易规则。
- 原因：目标合约 active 可找到 `188/219`，但严格 panel-ready 只有 `186/219=84.9315%`，低于 `95%` 门槛；缺口集中在本地面板缺少目标合约文件、source age 超限与 raw authority/hash/schema manifest 未按本线固化。
- 下一步：先补齐/固化缺失合约文件与 raw provenance，或只在 `panel_ready=1` 子集做预声明视觉假设审计；不得把 missing、rank、share、product-year 或 source-age 直接做阈值。

## 过拟合反思

- 运行前判断：否。Stage104 是数据契约审计，不按收益调阈值。
- 运行后判断：否。结论是阻止规则化并暴露覆盖缺口；rank/share 只作视觉分布，不作交易条件。
- 原因：如果现在按 rank1、rank2、OI share 或缺失年份筛选，就会把数据结构和历史右尾位置混为 alpha；本阶段明确禁止。

## 继续价值反思

- 运行前判断：有价值。Stage103 关闭了当前微观结构规则化，合约月 OI 是更高层、入场前可见的外生状态。
- 运行后判断：有价值，但价值在数据修复和预声明假设，不在立即接规则。
- 原因：右尾覆盖目前完整，说明这个路线没有第一眼就伤害右尾；但总体覆盖不足和 provenance 缺口决定它还不能进入 true engine。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage104 摘要和边界。
- 是否更新 `research/registry.md`：否，不是正式候选、重要突破或路线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，不是正式候选、重要突破或跨线合并。
