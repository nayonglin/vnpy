# Stage254 顺势价差 + OI 收缩状态审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-22 15:29 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读审计；复核 Stage253 暴露的 `aligned_price_oi_contract` 是否可进入 true engine
- 是否重要突破：否，反直觉状态有解释价值但交易化阻断
- 是否触发A/B：否；未形成正式候选

## 外部调研与判断

- 参考资料：
  - NBER/Hong & Yogo, What Does Futures Market Interest Tell Us about the Macroeconomy and Asset Prices: https://www.nber.org/papers/w16712
  - CME Group, Understanding Open Interest: https://www.cmegroup.com/education/courses/introduction-to-futures/open-interest
  - GitHub, `chrism2671/PyTrendFollow`: https://github.com/chrism2671/PyTrendFollow
  - GitHub, `pst-group/pysystemtrade`: https://github.com/pst-group/pysystemtrade
  - Investopedia, Intro to Open Interest in the Futures Market: https://www.investopedia.com/trading/intro-to-open-interest-in-futures-market/
- 我的判断：价格顺势时 OI 收缩可能对应空头/多头平仓挤压、被迫止损或流动性释放，确实可能承载趋势右尾；但 OI 收缩不能告诉我们“谁在退场”，也不能保证后续不反转。只有在 bottom-loss、split 稳定性和反例图谱都过关时，才允许考虑 true engine。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage254_aligned_price_oi_contract_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `CANDIDATE_GROUP=aligned_price_oi_contract`
  - promotion gate：样本数 `>=30`、坏账率相对 rest 降低 `>=5pp`、右尾捕获 `>=50%`、bottom-loss 捕获 `<=25%`、early right-tail 捕获 `>=50%`、无 PnL 正负混杂、split pass share `>=60%`、技术隔离通过
  - counterexample atlas：最多 6 个 right-tail 与 6 个 bottom-loss 候选样本，绘制入场前最多 121 根 closed 1m bar 的 direction-aligned price log 与 OI pct
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：官方 C9/15w 基准沿用 Stage251，`2018-01-01 -> 2026-06-15`
- 账户规模：`150000`
- 成本口径：官方基准成本口径，不新增成本压力回测
- 样本过滤：Stage253 的 `219` 行 price+OI 四象限结果；候选只取 `aligned_price_oi_contract`
- 策略/归因口径：
  - 只读审计 Stage253 暴露的反直觉状态
  - 不创建策略规则、不运行 true engine、不触发 A/B、不改变 official config、不连接 CTP/SimNow、不调用 order API

## 结果

- 官方期末权益：`39,176,437.60`
- 官方总收益：`26017.6251%`
- 官方最大回撤：`-45.0827%`
- 官方 Sharpe：`1.6331`
- 官方总滑点：`2,730,130`
- 官方总交易次数：`787`
- 官方胜率：`53.2560%`
- timestamp-ready 订单数：`219`
- 候选订单数：`74`
- 候选 PnL：`23,972,483.70`
- 候选单笔 PnL 最小/最大：`-594,792` / `8,970,000`
- 候选 risk_bad_rate：`0.148649`
- rest risk_bad_rate：`0.206897`
- 相对 rest 坏账率降低：`0.058248`
- 候选 right-tail 捕获：`10/18 = 55.5556%`
- 候选 bottom-loss 捕获：`6/18 = 33.3333%`
- 候选 early right-tail 捕获：`6/9 = 66.6667%`
- split stability：`3/11 = 27.2727%`
- promotion gate：`5/8`，通过样本量、坏账率降低、右尾捕获、early right-tail 捕获、技术隔离；失败 bottom-loss 捕获、PnL 正负混杂、split 稳定性
- 决策：`stage254_aligned_price_oi_contract_tail_contaminated_no_true_engine_no_rule`

## 视觉分析

- official path contract chart：候选点覆盖多个权益台阶和后半段右尾，但并未避开主要回撤上下文。
- contribution chart：候选累计 PnL 明显强于 rest，尤其 `2023-2025` 贡献突出；这说明状态有解释价值，但不是风险过滤充分条件。
- contrast rate chart：候选右尾率显著高于 rest，risk_bad 低于 rest；但 bottom-loss rate 与 rest 接近，无法满足“最小风险搏最大收益”的低污染要求。
- split heatmap：只有 `2023`、`2025`、CZCE 通过；`2022` 候选 risk_bad 更高、right-tail 更低且 bottom-loss 更高，SHFE 候选 PnL 和 bottom-loss 均反向，short 方向右尾保留反向。
- counterexample atlas：right-tail 和 bottom-loss 都能出现“价格顺势、OI 收缩”的相似路径；若继续用 OI 收缩幅度、末端形态或品种做切分，会变成事后补丁。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage254_aligned_price_oi_contract_audit/qmt_roll_stage254_c9_minrisk_aligned_price_oi_contract_audit_report_stage254_aligned_price_oi_contract_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage254_aligned_price_oi_contract_audit/qmt_roll_stage254_c9_minrisk_aligned_price_oi_contract_audit_summary_stage254_aligned_price_oi_contract_audit_v1.csv`
- rows：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage254_aligned_price_oi_contract_audit/qmt_roll_stage254_c9_minrisk_aligned_price_oi_contract_audit_contract_rows_stage254_aligned_price_oi_contract_audit_v1.csv`
- contrast：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage254_aligned_price_oi_contract_audit/qmt_roll_stage254_c9_minrisk_aligned_price_oi_contract_audit_contract_vs_rest_stage254_aligned_price_oi_contract_audit_v1.csv`
- split stability：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage254_aligned_price_oi_contract_audit/qmt_roll_stage254_c9_minrisk_aligned_price_oi_contract_audit_split_stability_stage254_aligned_price_oi_contract_audit_v1.csv`
- promotion gate：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage254_aligned_price_oi_contract_audit/qmt_roll_stage254_c9_minrisk_aligned_price_oi_contract_audit_promotion_gate_stage254_aligned_price_oi_contract_audit_v1.csv`
- visuals：
  - `qmt_roll_stage254_c9_minrisk_aligned_price_oi_contract_audit_official_path_contract_chart_stage254_aligned_price_oi_contract_audit_v1.png`
  - `qmt_roll_stage254_c9_minrisk_aligned_price_oi_contract_audit_contract_contribution_chart_stage254_aligned_price_oi_contract_audit_v1.png`
  - `qmt_roll_stage254_c9_minrisk_aligned_price_oi_contract_audit_contract_contrast_rate_chart_stage254_aligned_price_oi_contract_audit_v1.png`
  - `qmt_roll_stage254_c9_minrisk_aligned_price_oi_contract_audit_split_stability_heatmap_stage254_aligned_price_oi_contract_audit_v1.png`
  - `qmt_roll_stage254_c9_minrisk_aligned_price_oi_contract_audit_promotion_gate_chart_stage254_aligned_price_oi_contract_audit_v1.png`
  - `qmt_roll_stage254_c9_minrisk_aligned_price_oi_contract_audit_counterexample_atlas_stage254_aligned_price_oi_contract_audit_v1.png`

## 结论

- 本阶段结论：`aligned_price_oi_contract` 有解释价值和右尾承载力，但 bottom-loss 污染、PnL 混杂和 split 不稳足以阻断交易化。
- 是否进入下一步：不进入 true engine、不进入正式候选、不触发 A/B。
- 下一步：停止在 OI 四象限内继续扫阈值或切片；若继续当前大目标，应换到更高信息层级，如真实盘口/订单流可行动事件、会员持仓结构的点时覆盖修复，或明确转为非交易规则的 forward-watch 风险解释。

## 过拟合反思

- 运行前判断：有过拟合风险。
- 运行后判断：本阶段本身可控，继续救参会过拟合。
- 原因：`aligned_price_oi_contract` 是 Stage253 结果中暴露出来的状态，虽然属于预声明四象限，但已经不是原始先验。Stage254 只做固定状态审计，没有扫 OI 阈值、lookback、年份、交易所、方向或产品；结果失败后再细分就是历史补丁。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：OI 四象限路线无继续交易化价值；OI 可保留为解释/forward-watch 标签。
- 原因：它确实解释了部分右尾，但不能把右尾和 bottom-loss 普世切开。继续做策略化会牺牲“穿越周期”的约束；更值得继续的是寻找更直接的订单流/持仓结构/执行事件信息。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage254 路线阻断摘要。
- 是否更新 `research/registry.md`：否，本线不新增/合并/废弃研究线。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是正式候选或重要合入。
