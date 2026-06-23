# Stage053 外生数据源优先级统一审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 04:17 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读外生源优先级审计；不新增交易规则、不是真实组合引擎、不连接 CTP、不调用订单 API
- 是否重要突破：否，是路线收束与数据工程排序
- 是否触发A/B：否，没有任何外生源达到候选或接正式版标准

## 外部调研与判断

- 参考资料：
  - SHFE 官方 Daily Warrant / Daily Data：https://www.shfe.com.cn/eng/reports/StatisticalData/DailyData/?query_params=dailystock
  - SHFE 官方 Daily Ranking / Daily Data：https://www.shfe.com.cn/eng/reports/StatisticalData/DailyData/?query_params=pm
  - CZCE 官方 Market Data：https://english.czce.com.cn/
  - DCE 官方标准仓单页面：https://www.dce.com.cn/dceg/channel/list/7000065.html
  - CFTC COT 官方说明：https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm
  - CME Daily Volume and Open Interest：https://www.cmegroup.com/market-data/browse-data/exchange-volume.html
  - NBER Hong/Yogo open interest 论文：https://www.nber.org/system/files/working_papers/w16712/w16712.pdf
  - AKShare GitHub：https://github.com/akfamily/akshare
  - AKShare DCE 日行情 issue 例子：https://github.com/akfamily/akshare/issues/7059
- 我的判断：
  - 第一性原则上，会员持仓、仓单/库存、基差/期限结构都比单纯价格衍生标签更接近真实供需和风险承接，理论上更可能穿越周期。
  - 但抓取层不是权威源。AKShare 可以做采集辅助，不能替代交易所官方源和点时化校验；DCE 等接口近期仍有稳定性 issue，必须把数据工程和策略结论分离。
  - 本阶段只允许比较既有冻结审计的覆盖和上限，不允许从事后最亏桶反推规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage053_external_source_priority_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `SOURCE_SPECS`：冻结纳入 Stage025 market breadth、Stage026 term structure、Stage027 supply/inventory、Stage028/029 member rank、Stage052 Stage496 product trend t-stat
  - `posthoc_candidate_like` 固定条件：事后最负桶净亏、样本数、产品数、年份数、最大回撤改善、收益保留、leave-one 年份/产品仍为负
- 修改参数：无正式策略参数修改
- 删除参数：无

## 回测/归因参数

- 数据区间：复用官方 C9/15w closed-lot 与 Stage046 官方资金曲线，约 `2018-01-02` 至 `2026-05-29`
- 账户规模：`150,000`
- 成本口径：沿用官方 C9/15w 曲线，总滑点 `2,730,130`
- 样本过滤：官方 closed lots `399`；每个外生源按自身 ready/missing 字段绑定
- 策略/归因口径：
  - 不做真实交易引擎。
  - 每个源只选一个“事后最负 bucket”作为诊断上限，资金曲线按跳过该 bucket 的 realized PnL cashflow 重算。
  - 该上限只能说明该源有没有值得继续数据工程的解释力，不能作为交易规则。

## 结果

- 官方基准：
  - 期末权益：`39,176,437.60`
  - 总收益：`26017.6251%`
  - 最大回撤：`-45.0827%`
  - Sharpe：`1.6339`
  - 总滑点：`2,730,130`
  - 总交易次数：`787`
  - 胜率：`53.2560%`
- 外生源统一结果：
  - 决策：`stage053_no_posthoc_external_bucket_pass_prioritize_member_rank_data_engineering`
  - posthoc pass count：`0`
  - market breadth：ready `67.6692%`；事后最负桶实际为正 `+849,018.60`，回撤仅改善 `0.4120pp`
  - term structure：ready `67.4185%`；事后最负桶 `mixed_or_flat` 为正 `+18,250.00`，回撤恶化 `-0.0867pp`
  - supply/inventory：ready `77.4436%`；`supply_supportive` 净亏 `-2,356,900.00`，但乐观上限回撤只改善 `1.5337pp`
  - member rank：ready 仅 `17.2932%`；`member_supportive` 净亏 `-2,487,980.00`，但现有样本太少且 missing 净贡献 `+22,263,004.00`
  - Stage496 product trend t-stat：ready `67.4185%`；`aligned_weak_0_2` 净亏 `-755,299.50`，回撤只改善 `0.2302pp`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage053_external_source_priority_audit/qmt_roll_stage053_c9_minrisk_external_source_priority_audit_report_stage053_external_source_priority_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage053_external_source_priority_audit/qmt_roll_stage053_c9_minrisk_external_source_priority_audit_decision_stage053_external_source_priority_audit_v1.json`
- route summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage053_external_source_priority_audit/qmt_roll_stage053_c9_minrisk_external_source_priority_audit_route_summary_stage053_external_source_priority_audit_v1.csv`
- bucket summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage053_external_source_priority_audit/qmt_roll_stage053_c9_minrisk_external_source_priority_audit_bucket_summary_stage053_external_source_priority_audit_v1.csv`
- daily/curve：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage053_external_source_priority_audit/qmt_roll_stage053_c9_minrisk_external_source_priority_audit_posthoc_upper_bound_curves_stage053_external_source_priority_audit_v1.csv`
- quality：
  - `qmt_roll_stage053_c9_minrisk_external_source_priority_audit_posthoc_upper_bound_path_chart_stage053_external_source_priority_audit_v1.png`
  - `qmt_roll_stage053_c9_minrisk_external_source_priority_audit_source_coverage_gap_chart_stage053_external_source_priority_audit_v1.png`
  - `qmt_roll_stage053_c9_minrisk_external_source_priority_audit_source_priority_frontier_stage053_external_source_priority_audit_v1.png`
  - `qmt_roll_stage053_c9_minrisk_external_source_priority_audit_ready_year_heatmap_stage053_external_source_priority_audit_v1.png`
  - `qmt_roll_stage053_c9_minrisk_external_source_priority_audit_best_negative_bucket_fragility_stage053_external_source_priority_audit_v1.png`

## 视觉结论

- 资金曲线：三个最有经济先验的上限曲线基本贴着官方 C9/15w，`2022-06-29` 主回撤谷没有被结构性抬高；局部差异不足以说明可穿越周期的回撤治理。
- 覆盖图：member rank ready 只有 `17.2932%`，2018-2022 基本空白，而 missing 样本贡献大量右尾，不能用当前小样本下策略结论。
- frontier 图：没有任何点进入 `>=5pp` 回撤改善区，最好的 supply/inventory 也只有 `1.5337pp`。
- 年度热图：supply/inventory 和 Stage496 在 2021 后覆盖较好，但 2018/2019 缺口仍明显；member rank 是最大历史缺口。
- fragility 图：member rank 与 supply/inventory 的事后最负桶在 leave-one 后仍可保持负，但回撤修复幅度太小，最多说明值得补数据，不说明可交易。

## 结论

- 本阶段结论：没有外生源达到“收益保留 `>=80%` 且最大回撤实质改善”的候选要求；连事后最宽松上限都不过关。
- 是否进入下一步：进入数据工程下一步，不进入 true engine、不进入 A/B。
- 下一步：
  - 优先补会员持仓官方历史源，尤其 DCE/CZCE/SHFE/GFEX 2018-2022 的 selector、下载、点时化和口径一致性。
  - 第二优先补官方仓单/库存/基差的更细粒度源，不再使用当前粗 supply score 直接交易化。
  - 如果暂不做数据工程，应回到 Stage045 timestamp-ready 分钟 replay 子集，重新预声明一个第一性候选；不能继续从既有亏损 bucket 救参。

## 过拟合反思

- 运行前判断：否。本阶段不是寻找最优参数，而是固定纳入既有冻结外生源，对其事后上限做统一淘汰和排序。
- 运行后判断：否。结论是拒绝交易化，并把最强线索降级为数据工程，不把 `member_supportive`、`supply_supportive` 等历史负桶包装成规则。
- 原因：所有 bucket 都是既有阶段产物，Stage053 没有扫描阈值、产品、方向、年份、月份，也没有修改正式策略。

## 继续价值反思

- 运行前判断：有价值。Stage052 之后需要决定继续做哪类外生源，不能靠直觉在多个半成品源之间来回切。
- 运行后判断：有价值，但价值在数据工程而非策略接入。会员持仓和官方仓单仍符合第一性原则，只是当前覆盖不足或粒度过粗。
- 原因：目标要求不能过拟合且要能穿越周期；这类目标更依赖真实外生状态的完整点时化，而不是在 closed-lot 标签中找亏损子集。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage053 结论和下一步边界。
- 是否更新 `research/registry.md`：否，本阶段不是正式候选、重要突破、路线废弃或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段是本线内部收束和数据工程排序。
