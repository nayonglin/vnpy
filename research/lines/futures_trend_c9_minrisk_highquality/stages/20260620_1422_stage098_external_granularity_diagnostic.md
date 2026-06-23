# Stage098 外生数据粒度诊断

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 14:22 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读数据粒度诊断；不是真引擎、不生成交易规则
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - 郑商所持仓排名：`https://www.czce.com.cn/cn/jysj/ccpm/H077003004index_1.htm`
  - CFTC COT explanatory notes：`https://www.cftc.gov/MarketReports/CommitmentsofTraders/ExplanatoryNotes/index.htm`
  - CFTC COT reports：`https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm`
  - AKShare 期货数据文档：`https://akshare.akfamily.xyz/data/futures/futures.html`
  - SHFE 成交持仓公布标准：`https://www.shfe.com.cn/reports/tradedata/dailyandweeklydata/dailyranking/decl/`
- 我的判断：交易所会员排名和 COT 类报告都属于聚合持仓/成交结构信息，真正可解释的部分往往依赖类别、席位、合约月份、交易者角色或报告门槛。当前本线只有产品总计级仓单与会员排名，缺少席位类别、主次合约迁移、跨月 spread、基差/库存联动和盘口/成交流，因此不应继续从同一聚合口径里救规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage098_external_granularity_diagnostic.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `SIGN_METRICS = warehouse_qty / warehouse_change / member_volume / member_net_oi`
  - `SIGN_DAYS = -7..-1`
  - 四类粒度 gate：`right_tail_conflict`、`product_year_sparsity`、`same_contract_entry_collision`、`member_detail_gap`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage096/097 的入场前 `7` 个交易日外生序列与 lot preflight 状态。
- 账户规模：沿用基准路径，仅作背景路径。
- 成本口径：沿用基准统计，总滑点 `2,730,130`。
- 样本过滤：固定 Stage097 selected lot `50` 与 all lot `188`，不根据收益做新过滤。
- 策略/归因口径：只读数据粒度诊断，`preflight_only=1`、`strategy_rule_allowed=0`、`true_engine_allowed=0`。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`53.2560%`
- 其他关键指标：
  - `decision=stage098_product_total_granularity_insufficient_no_rule`
  - `selected_lot_count=50`
  - `all_lot_count=188`
  - `selected_product_year_cell_count=28`
  - `selected_product_year_singleton_cell_count=14`
  - `selected_product_year_singleton_cell_ratio=0.5000`
  - `selected_product_year_h_state_tail_conflict_group_count=2`
  - `selected_same_contract_entry_pnl_conflict_group_count=1`
  - `member_detail_missing_product_count=2`
  - `source_family_gap_product_count=2`
  - `granularity_gate_count=4`
  - `granularity_gate_failed_count=4`
  - `hypotheses_promoted_to_true_engine=0`
  - `strategy_feature_usable=0`
  - `official_config_changed=0`、`strategy_rule_created=0`、`true_engine_run=0`、`ab_triggered=0`、`order_api_called=0`、`ctp_connected=0`

## 视觉观察

- official path chart：右尾台阶上同时存在 `same_contract_entry_conflict`、`product_year_state_tail_conflict`、`product_year_singleton` 与 `coarse_state_only`；这说明粒度问题覆盖关键权益阶段，不是只发生在边缘样本。
- collision chart：selected 样本在 H-state 层面 `6` 个多 lot group 同时也是 `6` 个 PnL 符号冲突和 `6` 个 tail conflict；即使压到 product-year H-state 仍有 `2` 个 tail conflict；同合约同日同方向仍有 `1` 个 PnL/tail 冲突。
- product-year density chart：`28` 个 selected product-year cell 中 `14` 个是 singleton，最大 cell 也只有 `4` 个 lot。大量单元格只有 `1-2` 个样本，任何 product/year 解释都没有足够 OOS 承载。
- granularity gate chart：四个 gate 全部 `rule_allowed=0`；最大问题是 product-year 稀疏，其次是右尾冲突、同合约入场冲突和会员明细缺口。
- 典型强冲突：`OI405.CZCE long 2024-03-15` 同一合约/方向/日期有 `-222,500` bottom-loss 与 `665,000` right-tail；同一产品总计外生状态无法区分层级/执行差异。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage098_external_granularity_diagnostic/qmt_roll_stage098_c9_minrisk_external_granularity_diagnostic_report_stage098_external_granularity_diagnostic_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage098_external_granularity_diagnostic/qmt_roll_stage098_c9_minrisk_external_granularity_diagnostic_summary_stage098_external_granularity_diagnostic_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage098_external_granularity_diagnostic/qmt_roll_stage098_c9_minrisk_external_granularity_diagnostic_decision_stage098_external_granularity_diagnostic_v1.json`
- lot diagnostic：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage098_external_granularity_diagnostic/qmt_roll_stage098_c9_minrisk_external_granularity_diagnostic_lot_diagnostic_stage098_external_granularity_diagnostic_v1.csv`
- collision summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage098_external_granularity_diagnostic/qmt_roll_stage098_c9_minrisk_external_granularity_diagnostic_collision_summary_stage098_external_granularity_diagnostic_v1.csv`
- collision groups：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage098_external_granularity_diagnostic/qmt_roll_stage098_c9_minrisk_external_granularity_diagnostic_collision_groups_stage098_external_granularity_diagnostic_v1.csv`
- product-year summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage098_external_granularity_diagnostic/qmt_roll_stage098_c9_minrisk_external_granularity_diagnostic_product_year_summary_stage098_external_granularity_diagnostic_v1.csv`
- source gap summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage098_external_granularity_diagnostic/qmt_roll_stage098_c9_minrisk_external_granularity_diagnostic_source_gap_summary_stage098_external_granularity_diagnostic_v1.csv`
- granularity gate：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage098_external_granularity_diagnostic/qmt_roll_stage098_c9_minrisk_external_granularity_diagnostic_granularity_gate_stage098_external_granularity_diagnostic_v1.csv`
- charts：
  - `qmt_roll_stage098_c9_minrisk_external_granularity_diagnostic_official_path_chart_stage098_external_granularity_diagnostic_v1.png`
  - `qmt_roll_stage098_c9_minrisk_external_granularity_diagnostic_collision_chart_stage098_external_granularity_diagnostic_v1.png`
  - `qmt_roll_stage098_c9_minrisk_external_granularity_diagnostic_product_year_density_chart_stage098_external_granularity_diagnostic_v1.png`
  - `qmt_roll_stage098_c9_minrisk_external_granularity_diagnostic_granularity_gate_chart_stage098_external_granularity_diagnostic_v1.png`

## 结论

- 本阶段结论：当前产品总计级仓单/会员排名信息粒度不足以支持降低回撤且保住右尾的交易规则。Stage096-098 的外生路线应停止直接规则化，保留为数据资产与 forward-watch 标签。
- 是否进入下一步：可以继续，但不能沿 H1/H2 或产品年份切片救参。
- 下一步：Stage099 若继续，应做“更细信息源可行性 manifest”：只列数据需求、point-in-time 约束和获取路径，例如会员类别/席位结构、合约月份 OI 迁移、库存/基差/期限结构联动、授权盘口/队列/成交流；在拿到更细数据之前，不进入 true engine、A/B 或正式候选。若暂不做新数据工程，则应回到 Stage045 timestamp-ready replay 子集，另提不同构的分钟级第一性候选。

## 过拟合反思

- 运行前判断：否。Stage098 不是为了优化收益，而是诊断 Stage097 失败是否来自信息粒度不足。
- 运行后判断：否，本阶段没有筛阈值、没有参数扫描、没有真引擎；但如果继续用当前 product-year 冲突单元格排除品种或年份，就是明显过拟合。
- 原因：`14/28` 个 product-year cell 是 singleton，同合约同日还能同时出现 right-tail 和 bottom-loss；这些现象说明不是阈值没调好，而是信息粒度无法分辨。

## 继续价值反思

- 运行前判断：有价值。Stage097 已否决两个假设，Stage098 可以判断是否值得继续挖当前外生数据。
- 运行后判断：当前聚合口径继续规则化没有价值；作为数据资产和下一步更细数据需求清单有价值。
- 原因：四个 gate 全部失败，继续从产品总计数据里找规则会走向样本切片；真正的继续价值只在更细点时化信息源或回到分钟 replay 另起第一性候选。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage098 摘要和 Stage099 边界。
- 是否更新 `research/registry.md`：否，不是正式候选、重要突破或路线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，不是正式候选、重要突破或跨线合并。
