# Stage256 CFTC COT 跨市场持仓背景审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-22 15:50 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读外生持仓背景审计；固定旧线 COT 映射和周频滞后公式，在当前 C9/15w 的 `219` 个点时 entry 上复核
- 是否重要突破：否；COT 在当前线也被证伪为交易化质量因子
- 是否触发A/B：否；没有形成正式候选

## 外部调研与判断

- 参考资料：
  - CFTC, Commitments of Traders: https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm
  - CME Group, Commitment of Traders: https://www.cmegroup.com/tools-information/quikstrike/commitment-of-traders.html
  - Data.gov, Commitment of Traders dataset: https://catalog.data.gov/dataset/commitment-of-traders-cot
  - GitHub, `NDelventhal/cot_reports`: https://github.com/NDelventhal/cot_reports
  - Inderscience/ResearchGate, The Commitment of Traders report as a trading signal: https://www.researchgate.net/publication/368643811_The_Commitment_of_Traders_report_as_a_trading_signal_Short-term_price_reversals_and_market_efficiency_in_the_US-futures_market
- 我的判断：COT 是官方周频持仓透明度数据，适合做拥挤/持仓背景，不适合做分钟入场精确触发。对中国商品期货尤其要先过两道硬门：国内品种映射必须足够可靠，周二持仓到周五发布的时滞必须点时化。若覆盖低、supportive 状态不降低坏账或跨 split 不稳，就不能进入 true engine。

## 开始前反思

- 是否在过拟合：否。本阶段沿用旧线 Stage313 已冻结的映射、`156` 周 zscore、最低 `52` 周启用、报告日后第 `4` 天 `08:00` 中国时间可见、最大信号年龄 `45` 天，不根据当前结果调窗口、映射或阈值。
- 是否还有价值继续：有。Stage255 确认真实订单流缺失后，必须把已有外生源逐一排除或确认。COT 是仓库里 readiness 较高的官方外生源，值得在当前 C9/15w 标签体系下做一次闭环审计。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage256_cftc_cot_cross_market_context_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `START_YEAR=2020`
  - `END_YEAR=2026`
  - `ROLLING_WEEKS=156`
  - `MIN_ROLLING_WEEKS=52`
  - `MAX_SIGNAL_AGE_DAYS=45`
  - COT 状态固定为 `cot_headwind <= -0.25`、`cot_neutral`、`cot_supportive >= 0.25`
  - 映射沿用旧线 Stage313：`CF/OI/lh/lc/au/cu/fu/hc/rb` 对应 CFTC Cotton/Soybean Oil/Lean Hogs/Lithium Hydroxide/Gold/Copper/Fuel Oil/HRC Steel
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：官方 C9/15w 基准沿用 Stage251，`2018-01-01 -> 2026-06-15`
- 账户规模：`150000`
- 成本口径：官方基准成本口径，不新增成本压力回测
- COT 数据源：本地缓存 `examples/portfolio_backtesting/backtest_outputs/external_cftc_cot_cache/fut_disagg_txt_2020.zip` 至 `fut_disagg_txt_2026.zip`
- 样本过滤：Stage239 的 `219` 个点时 entry 标签，按 `decision_ts` 匹配此前 `45` 天内最近的已发布 COT 信号，并用 Stage251 closed lots 补 realized PnL
- 策略/归因口径：
  - 只读审计 COT 外生持仓背景
  - 不创建策略规则、不运行 true engine、不触发 A/B、不改变 official config、不连接 CTP/SimNow、不调用 order API

## 结果

- 官方期末权益：`39,176,437.60`
- 官方总收益：`26017.6251%`
- 官方最大回撤：`-45.0827%`
- 官方 Sharpe：`1.6331`
- 官方总滑点：`2,730,130`
- 官方总交易次数：`787`
- 官方胜率：`53.2560%`
- entry 样本数：`219`
- COT 命中样本：`73/219 = 33.3333%`
- supportive 样本：`17`
- supportive risk_bad_rate：`0.352941`
- non-support risk_bad_rate：`0.232143`
- supportive 相对 non-support 坏账改善：`-0.120798`，即坏账更高
- supportive right-tail 捕获：`2/18 = 11.1111%`
- supportive bottom-loss 捕获：`1/18 = 5.5556%`
- supportive PnL：`-485,590`
- split stability：`0/7`
- promotion gate：`3/9`，只通过 direct mapping share、bottom-loss 捕获和技术隔离；失败覆盖率、supportive 样本量、坏账改善、右尾保留、PnL 正负混杂、split 稳定性
- 决策：`stage256_cftc_cot_context_low_coverage_tail_conflict_no_rule`

## 视觉分析

- official path COT coverage：COT 命中点集中在少数映射品种，缺失/未映射覆盖大部分 C9 entry；官方资金路径并没有出现 COT supportive 能系统性标记高质量台阶的视觉证据。
- state rate chart：`cot_supportive` 的坏账率最高，且累计 PnL 为负；`cot_neutral` 反而贡献最多，说明 COT 方向一致性不是质量排序。
- coverage heatmap：覆盖只落在 `CF/OI/lh/lc/au/cu/fu/hc/rb` 等少数跨市场可映射产品，`jm/MA/SM/AP/sp/FG/SA/ru` 等 C9 重要样本完全无 COT 直接背景，覆盖缺口不是单一年份问题。
- split stability heatmap：`2023`、SHFE、long 等切片 supportive 风险更高且 PnL 更差；没有任何有效 split 同时满足低风险、保右尾、低 bottom-loss 和保 PnL。
- promotion gate chart：红项集中在覆盖不足、supportive 样本不足、坏账不降、右尾不保、split 不稳；这不是参数能救的问题，而是跨市场周频背景与国内分钟 entry 的信息层级不匹配。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage256_cftc_cot_cross_market_context_audit/qmt_roll_stage256_c9_minrisk_cftc_cot_cross_market_context_audit_report_stage256_cftc_cot_cross_market_context_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage256_cftc_cot_cross_market_context_audit/qmt_roll_stage256_c9_minrisk_cftc_cot_cross_market_context_audit_summary_stage256_cftc_cot_cross_market_context_audit_v1.csv`
- joined：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage256_cftc_cot_cross_market_context_audit/qmt_roll_stage256_c9_minrisk_cftc_cot_cross_market_context_audit_joined_entry_audit_stage256_cftc_cot_cross_market_context_audit_v1.csv`
- state summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage256_cftc_cot_cross_market_context_audit/qmt_roll_stage256_c9_minrisk_cftc_cot_cross_market_context_audit_state_summary_stage256_cftc_cot_cross_market_context_audit_v1.csv`
- coverage：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage256_cftc_cot_cross_market_context_audit/qmt_roll_stage256_c9_minrisk_cftc_cot_cross_market_context_audit_coverage_stage256_cftc_cot_cross_market_context_audit_v1.csv`
- split stability：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage256_cftc_cot_cross_market_context_audit/qmt_roll_stage256_c9_minrisk_cftc_cot_cross_market_context_audit_split_stability_stage256_cftc_cot_cross_market_context_audit_v1.csv`
- visuals：`official_path_cot_coverage`、`state_rate_chart`、`coverage_heatmap`、`split_stability_heatmap`、`promotion_gate_chart`

## 结束后反思

- 是否在过拟合：否。COT 失败后直接拒绝，没有继续改映射、改窗口、改阈值、改 COT 分组或挑产品/年份救结果。
- 是否还有价值继续：有，但 COT 这条作为交易化规则没有继续价值。它只能保留为外盘温度计/研究背景，不进入 true engine、A/B 或正式候选。后续若继续外生路线，应回到 Stage099 的更细粒度信息源：会员类别/席位结构、合约月份 OI 迁移、库存/基差/期限结构联动、授权盘口/队列/成交流；若没有新增数据，就不能靠 COT 或现有分钟特征完成目标。

## 后续 TODO

- 不再围绕 COT 的 `156/52` 周窗口、`45` 天匹配、`-0.25/0.25` 状态、品种映射、年份、方向或交易所做参数救援。
- 若继续外生数据工程，优先做 `contract_month_oi_migration` 或 `member_category_seat_structure` 的点时化 source inventory，而不是产品总计级 COT/仓单/会员数值阈值。
- 未取得更细、点时化、覆盖完整且右尾保护通过的信息源前，不进入 true engine、A/B 或正式候选。
