# Stage013 Stage837 C4持仓后全路径压力法证

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-14 18:13 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读归因；基于 Stage832 C4 压力起点拆解持仓簇、产品方向集中、权益分母和分钟K覆盖；不改正式版、不改候选配置、不连接 CTP、不调用下单。
- 是否重要突破：否。它是重要风险形状证据，但还不是可晋级候选。
- 是否触发A/B：否。未形成要接入正式版或与第78/Stage372正式基准组合的候选，只是 Stage819 候选研究线内部法证。

## 外部调研与判断

- 参考资料：
  - CME Position and Risk Management：https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/position-and-risk-management
  - Euronext Clearing Risk Management：https://www.euronext.com/en/clearing/risk-management
  - FINRA Portfolio Margin and Intraday Trading：https://www.finra.org/rules-guidance/guidance/reports/2022-finras-examination-and-risk-monitoring-program/portfolio-margin-intraday-trading
  - Investopedia Futures Risk Management：https://www.investopedia.com/articles/optioninvestor/07/money_management_futures.asp
- 我的判断：外部资料共同指向一个朴素事实：期货组合风险不能只看单笔止损，必须同时看合约手数、保证金、集中度、持仓后盯市和盘中/日终监控。C4 的问题也不是入口 cap 完全失效，而是开仓后持仓簇和权益分母重新生成压力，所以本阶段继续拆 full-path holding pressure，而不是扫止损倍数、OR长度、冷却天数或品种过滤。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage837_stage832_holding_pressure_forensics.py`
- 修改脚本：同上。实现后修正两个质量问题：
  - `BROKER10_CURVE_MULTIPLIER` 从草稿误设的 `1.65` 修正为 `1.10`，使 exact broker10 与 Stage832 actual broker10 口径一致。
  - `pre_anchor_cluster` 只保留锚点当日真实持有的产品方向簇，过滤窗口内出现但锚点已无持仓的噪声行。
- 删除脚本：无。
- 新增参数：
  - `BROKER10_CURVE_MULTIPLIER = 1.10`
  - `BROKER100 = 100.0`
  - `DD50 = -50.0`
  - `HORIZONS = [1, 3, 5, 10, 20]`
  - `TOP_CONTRACTS_PER_ANCHOR = 3`
  - `MAX_ATLAS_ROWS = 12`
- 修改参数：无正式策略参数修改；只修正归因脚本内部 broker10 计算口径。
- 删除参数：无。

## 回测/归因参数

- 数据区间：继承 Stage832 压力起点输出，重点覆盖 `2021-12-22`、`2022-06-13` 至 `2022-07-08` 的 broker100/DD50/max drawdown 锚点。
- 账户规模：继承 Stage819/Stage830 C4 的 30万候选研究口径。
- 成本口径：继承 Stage832 既有曲线、产品保证金、合约保证金与交易成本输出；本阶段不重新生成策略交易。
- 样本过滤：只读 Stage832 已识别的 C4 压力锚点，包含 `first_broker100`、`max_broker10`、`first_dd50`、`max_drawdown`。
- 策略/归因口径：A 为 `stage827_stage819_baseline`，C4 为 `stage830_stage819_c2_broker10_100_cap`。拆解 C4-A broker10 差异为 margin numerator effect 和 equity denominator effect，并统计锚点产品方向簇集中度、方向集中度、10日窗口 PnL 与分钟K覆盖。

## 结果

- 期末权益：不适用；本阶段只读归因，未新增回测曲线。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - decision：`stage837_holding_pressure_cluster_rule_shape_supported`
  - broker 锚点数：`8`
  - broker 锚点 top3 产品方向簇高集中率：`1.0`
  - broker 锚点 short 方向集中率：`0.875`
  - broker 锚点 equity denominator 正贡献比例：`0.5`
  - `2018-01 2022-07-07`：C4 broker10 `115.4012%` vs A `90.6200%`；C4 margin 比 A 少 `540,744.5`，但 equity 比 A 少 `1,854,157.2`，差异主要来自权益分母塌缩，denominator effect `+34.3225pp`。
  - `2019-01 2021-12-22`：C4 broker10 `100.2310%` vs A `71.8461%`；C4 margin 比 A 多 `2,023,728.0`，margin numerator effect `+38.9167pp`，是纯保证金分子/集中度问题。
  - `2019-01 2022-07-07`：C4 broker10 `104.9794%` vs A `87.8039%`；margin numerator effect `+22.2573pp`，denominator effect `-5.0817pp`，主因仍是 C4 更大保证金暴露。
  - `2020-01 2022-07-07`：C4 broker10 `114.4678%` vs A `90.2602%`；margin effect `+3.0584pp`，denominator effect `+21.1493pp`，权益分母是主因。
  - `2021-01 2022-07-07`：C4 broker10 `108.1240%` vs A `81.9304%`；margin effect `+40.1143pp`，denominator effect `-13.9207pp`，保证金分子是主因。
  - 2022-07 broker 压力日 top3 产品方向簇一般为 `hc.SHFE short`、`jm.DCE short`、`rb.SHFE short`，top3 share 约 `78.9%` 至 `81.6%`，short share `100%`。
  - `2019-01 2021-12-22 first_broker100` 是例外方向，top3 全为 long：`jm.DCE long`、`rb.SHFE long`、`MA.CZCE long`，top3 share `100%`。
  - DD50 与 broker100 继续被拆成两个问题：`2022-06` 很多 DD50/max drawdown 锚点 C4 保证金为 `0`，是高水位后的权益路径回撤，不是当日持仓保证金压力。
  - 分钟K覆盖不足：选取的 12 个压力合约行里只有 `rb2205.SHFE` 与 `MA205.CZCE` 在 `2021-12-22` 有分钟K覆盖；关键 `2022-07` 的 `hc2210`、`jm2209`、`rb2210` 基本缺分钟K，不能宣称分钟级出场规则已被证明。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage837_stage832_holding_pressure_forensics_report_stage837_stage832_holding_pressure_forensics_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage837_stage832_holding_pressure_forensics_stress_summary_stage837_stage832_holding_pressure_forensics_v1.csv`
- orders：不适用；本阶段未生成新订单。
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage837_stage832_holding_pressure_forensics_daily_pressure_atlas_stage837_stage832_holding_pressure_forensics_v1.png`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage837_stage832_holding_pressure_forensics_pressure_decomposition_stage837_stage832_holding_pressure_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage837_stage832_holding_pressure_forensics_pre_anchor_cluster_stage837_stage832_holding_pressure_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage837_stage832_holding_pressure_forensics_minute_pressure_features_stage837_stage832_holding_pressure_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage837_stage832_holding_pressure_forensics_decision_stage837_stage832_holding_pressure_forensics_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage837_stage832_holding_pressure_forensics_decomposition_chart_stage837_stage832_holding_pressure_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage837_stage832_holding_pressure_forensics_cluster_chart_stage837_stage832_holding_pressure_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage837_stage832_holding_pressure_forensics_minute_pressure_atlas_stage837_stage832_holding_pressure_forensics_v1.png`

## 结论

- 本阶段结论：C4 的 broker100 压力有稳定的持仓簇集中形状，尤其是 2022-07 黑色/燃油 short 集群，以及 2021-12 的 long 集群；这支持“账户/持仓层集中度压力规则”的研究方向。但它还不是可推广策略：因为 DD50 与 broker100 不是同一问题，且关键 2022-07 分钟K缺失，无法验证分钟级实时止损是否能真正降低压力。
- 是否进入下一步：进入下一步只读/反事实，不进入正式候选。
- 下一步：Stage014 应先做冻结低自由度的 concentration-aware holding pressure counterfactual，只在压力状态下评估“高 broker10 + top3 产品方向簇集中 + 方向集中”是否能解释减风险必要性；如果做真实引擎，也只能作为 C4 内部 C6 压力生存线，不得按产品、年份、方向单独补丁，也不得直接与 Stage372 官方正式版 A/B。

## 过拟合反思

- 运行前判断：否，本阶段不是调参收益曲线，而是用 Stage832 全部压力锚点做结构归因。
- 运行后判断：低到中。top3 集中与方向集中跨多个起点重复出现，且没有按品种/年份调参；但样本仍集中在少数压力日，若把 `hc/jm/rb/fu` 或 `2022-07` 写成专属规则就会过拟合。
- 原因：可继续提炼账户/持仓层规则形状，但必须冻结简单阈值和动作后做完整路径 A/C，不能根据这些锚点反复调阈值。

## 继续价值反思

- 运行前判断：有价值。Stage012 已反证 blanket cooldown，下一层必须看持仓后保证金集中和权益分母。
- 运行后判断：仍有价值，但只值得继续到一个低自由度 counterfactual/engine 试验。若下一步不能同时降低 broker100/DD50 且不破坏 C4 右尾，就停止该生存线方向。
- 原因：Stage837 找到了比“止损是否正确”更接近本质的风险源：持仓集中和分母压力。它能指导下一步，但尚不足以直接成为候选。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage013 结论和下一步。
- 是否更新 `research/registry.md`：否，日常阶段推进不频繁改总索引。
- 是否追加根目录 `memory.md/back_log.md`：否，尚非重要突破、正式候选或路线废弃。
