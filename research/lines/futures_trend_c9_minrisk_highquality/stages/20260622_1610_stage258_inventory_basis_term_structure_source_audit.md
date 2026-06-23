# Stage258 库存/基差/期限结构 source contract 审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-22 16:10 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：外生物理市场数据源合同审计，只回答“还能不能补成可交易源”
- 是否重要突破：否
- 是否触发A/B：否，未形成可接正式版候选

## 外部调研与判断

- 参考资料：
  - SHFE Data 页面列出 Daily Data、Daily Warrant、Weekly Inventory 等官方统计数据：https://www.shfe.com.cn/eng/reports/
  - DCE 标准仓单/仓单登记入口：https://www.dce.com.cn/dceg/channel/list/7000070.html
  - CZCE 仓单日报入口：https://www.czce.com.cn/cn/jysj/cdrb/H077003010index_1.htm
  - GFEX 仓单日报入口：https://www.gfex.com.cn/gfex/cdrb/hqsj_tjsj.shtml
  - GitHub/Quantpedia 上商品期限结构样例主要围绕 roll return / backwardation / contango，属于价格曲线策略参考，不解决国内实盘所需的点时授权、发布时间戳、raw hash 与 source license 问题。
- 我的判断：库存、仓单、基差、期限结构在第一性原理上确实是更接近供需和便利收益的外生信息，但它要能交易化必须同时满足“官方/授权来源、点时发布时间、可复验 raw/hash、产品/合约映射、spot/basis 授权、完整曲线滞后日历”。本地已有缓存只能做背景和归因，不能直接做开仓质量规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage258_inventory_basis_term_structure_source_audit.py`
- 修改脚本：无其他脚本
- 删除脚本：无
- 新增参数：`LOOKBACK_DAYS=7`，用于入场日前最多 7 个自然日查找最近一条 basis/warehouse 缓存；`REQUIRED_FIELDS=17` 项物理市场数据合同字段
- 修改参数：无
- 删除参数：无
- 新增回测/归因结果：新增 Stage258 source-contract 审计摘要、entry coverage、field contract、gate 和 5 张视觉图
- 修改回测/归因结果：无
- 删除回测/归因结果：无

## 回测/归因参数

- 数据区间：官方 A 臂资金曲线 `2018-01-02` 至 `2026-06-15`；basis/warehouse 本地缓存 `2020-01-02` 至 `2026-04-17`
- 账户规模：沿用 Stage251 官方 A 臂 15w 口径，只作背景，不重跑策略
- 成本口径：沿用官方 A 臂成本结果，不创建新交易
- 样本过滤：Stage239 已冻结的 `219` 个 entry decision
- 策略/归因口径：只读审计，不创建策略规则、不运行 true engine、不触发 A/B、不改变 official config、不连接 CTP/SimNow、不调用 order API

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`53.2560%`
- 其他关键指标：
  - decision：`stage258_inventory_basis_term_structure_contract_incomplete_no_rule`
  - basis cache：`24,482` 行、`18` 个产品，entry 命中 `203/219=92.6941%`，缺 `16/219`
  - warehouse cache：`13,084` 行、`17` 个产品，entry 命中 `97/219=44.2922%`，缺 `122/219`
  - basis + warehouse cache 同时命中：`88/219=40.1826%`，缺 `131/219`
  - Stage095 官方仓单数值 entry 命中：`103/219=47.0320%`，缺 `116/219`
  - cache joint + official warehouse 同时命中：`76/219=34.7032%`
  - 完整库存+基差+期限结构交易源合同 ready：`0/219=0.0000%`，缺 `219/219`
  - required fields：`17` 项，rule-ready `10` 项，blocking missing `7` 项：`exchange_inventory/deferred_future_price/curve_slope/source_timestamp/publication_lag_calendar/source_license/unit`
  - promotion gate：`5/12`
  - Stage087 旧结论仍有效：basis ready lot `73.9348%` 但缺 big winner `3` 个；warehouse ready lot `33.8346%` 但缺 big winner `11` 个；直接规则已因右尾冲突关闭
  - strategy_rule_created：`0`
  - true_engine_run：`0`
  - ab_triggered：`0`
  - order_api_called：`0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage258_inventory_basis_term_structure_source_audit/qmt_roll_stage258_c9_minrisk_inventory_basis_term_structure_source_audit_report_stage258_inventory_basis_term_structure_source_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage258_inventory_basis_term_structure_source_audit/qmt_roll_stage258_c9_minrisk_inventory_basis_term_structure_source_audit_summary_stage258_inventory_basis_term_structure_source_audit_v1.csv`
- orders：无
- daily：无
- quality：
  - `qmt_roll_stage258_c9_minrisk_inventory_basis_term_structure_source_audit_entry_coverage_stage258_inventory_basis_term_structure_source_audit_v1.csv`
  - `qmt_roll_stage258_c9_minrisk_inventory_basis_term_structure_source_audit_field_contract_stage258_inventory_basis_term_structure_source_audit_v1.csv`
  - `qmt_roll_stage258_c9_minrisk_inventory_basis_term_structure_source_audit_promotion_gate_stage258_inventory_basis_term_structure_source_audit_v1.csv`
  - `qmt_roll_stage258_c9_minrisk_inventory_basis_term_structure_source_audit_official_path_physical_contract_coverage_stage258_inventory_basis_term_structure_source_audit_v1.png`
  - `qmt_roll_stage258_c9_minrisk_inventory_basis_term_structure_source_audit_field_readiness_heatmap_stage258_inventory_basis_term_structure_source_audit_v1.png`
  - `qmt_roll_stage258_c9_minrisk_inventory_basis_term_structure_source_audit_asset_inventory_chart_stage258_inventory_basis_term_structure_source_audit_v1.png`
  - `qmt_roll_stage258_c9_minrisk_inventory_basis_term_structure_source_audit_entry_exchange_year_coverage_heatmap_stage258_inventory_basis_term_structure_source_audit_v1.png`
  - `qmt_roll_stage258_c9_minrisk_inventory_basis_term_structure_source_audit_promotion_gate_chart_stage258_inventory_basis_term_structure_source_audit_v1.png`

## 视觉结论

- official path 图：红叉覆盖全部 `219` 个 entry；蓝圈/橙框只说明有 basis+warehouse 缓存或局部官方仓单数值，并不代表完整交易源 ready。
- field heatmap：`spot_price/near_future_price/basis/warehouse_receipt` 等缓存字段局部可用，但 `source_timestamp/publication_lag_calendar/source_license` 全红，`curve_slope` 只能来自已关闭的旧归因源。
- exchange-year heatmap：CZCE/GFEX 局部缓存较好，DCE/SHFE 官方仓单数值链明显缺；所有交易所、所有年份 full contract rule-ready 都是 `0`。
- asset inventory 图：本地 basis/warehouse 数据量不小，但多数没有 raw hash、发布时间戳和 license；这就是“缓存覆盖”和“可交易源覆盖”的差异。
- gate 图：只通过“公开源存在、本地缓存存在、局部解析存在、joint 非零”这类资产存在性 gate；关键交易化 gate 全部失败。

## 结论

- 本阶段结论：库存/基差/期限结构路线不是没有数据，而是没有完整可交易 source contract。当前还差 `219/219` 个 entry 的完整规则级覆盖；核心缺口是授权/发布时间/滞后日历/raw hash/完整曲线/全交易所官方仓单，而不是再扫阈值或补几天缓存。
- 是否进入下一步：进入下一条 source contract 审计或授权数据接入准备；不进入策略规则、true engine、A/B、正式候选。
- 下一步：若坚持这条物理市场路线，先取得或补齐授权 spot/basis + 官方仓单全交易所 raw/hash + 发布时点/滞后日历 + 期限结构曲线合同；否则转向 Stage099 其他未闭环外生源，或研究不改变正式持仓路径的部署层资金治理。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有基于收益挑阈值、年份、交易所、方向或品种，也没有生成交易规则；它只检查信息源能否在入场前、可授权、可复验地存在。拒绝把 `203/219` basis 缓存命中、`97/219` warehouse 缓存命中或 `88/219` joint 命中解释成 alpha，反而是在降低过拟合风险。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值但不应继续补同类缓存。
- 原因：价值在于把“为什么一直覆盖、还差多少”讲清楚：分钟覆盖已补完，当前物理市场路线的缓存覆盖局部存在，但规则级覆盖仍缺 `219/219`。继续补无授权缓存的边际价值低；只有补 source contract 或换更高信息层级才有继续价值。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage258 摘要。
- 是否更新 `research/registry.md`：否，本阶段不是跨线合并、正式候选或重要突破。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段是本线日常 source-contract 收敛记录。
