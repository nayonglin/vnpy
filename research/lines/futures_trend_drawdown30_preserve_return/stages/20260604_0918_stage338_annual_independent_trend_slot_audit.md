# Stage338 年度独立趋势风险槽审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 09:18 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：低单笔风险扩池方向的年度机会 x 独立风险槽交叉审计
- 是否重要突破：否；确认方向有结构价值，但当前不能晋级
- 是否触发A/B：否；没有策略版本进入正式候选、paper 或交易白名单

## 外部调研与判断

- 参考资料：
  - Trend-following, Risk-Parity and the Influence of Correlations：`https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2673124`
  - Trend Following, Risk Parity and Momentum in Commodity Futures：`https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2126813`
  - Increasing Diversification of Commodities Trend-Following Strategies：`https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4871376`
  - Diversifying Trends / CoTrend dependence measure：`https://www.sciencedirect.com/science/article/abs/pii/S245230622100109X`
  - NBER Facts and Fantasies about Commodity Futures：`https://www.nber.org/papers/w10595`
- 我的判断：
  - 文献支持趋势策略跨市场分散，但有效单位不是“品种数量”，而是不同经济来源、不同相关结构、不同尾部行为的风险槽。
  - 单纯降低单笔风险并扩大池子，容易把同一产业链或同一宏观驱动重复买入；真正要审计的是：年度机会是否存在、是否跨家族、是否低相关/可监控、是否有可实盘累计的 PIT source/TCA/selector。
  - 本阶段只做机会结构和门槛审计，不允许用 hindsight 年度赢家生成白名单。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage638_annual_independent_trend_slot_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 年度 oracle topN：`6`
  - 年度 top6 最低家族数：`3`
  - worklist/monitor 年度覆盖检查：年度 top6 中至少 `2` 个来自 P1/P2/watch 才算该年覆盖
  - 当前有效风险槽：`4`
  - 目标有效风险槽：`7`
  - 禁止输出：selector、paper、A/B、交易白名单
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage541/557/563/633 冻结输出，年度范围 `2020-2026`
- 账户规模：不新增账户回测；读取 Stage541 单品种机会账本和 Stage563 低单笔风险宽池结果
- 成本口径：不新增成本重放；引用 Stage563 正常成本宽池 sleeve 结果
- 样本过滤：
  - 只看非核心商品，排除 `CFFEX`
  - 年度机会使用 Stage541 单品种机会图的 `net_pnl/trade_count`
  - 相关性和结构桶使用 Stage633 product map
  - 宽池捕获效果引用 Stage563 decision
- 策略/归因口径：
  - 不重放策略、不改交易规则、不扫参数
  - 不生成 selector/paper/交易白名单、不连接 CTP
  - 本阶段回答“年度机会是否跨独立风险槽、当前工作流能否覆盖”

## 结果

- 期末权益：不适用；本阶段不是新策略回测
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - decision：`annual_opportunity_valid_selector_not_ready_no_promotion`
  - annual years：`7`
  - opportunity years：`7/7`
  - independent-family years：`7/7`
  - worklist/monitor years：`0/7`
  - deployable years：`0/7`
  - deployable products：`0`
  - P1 products：`3`
  - P2 products：`3`
  - watch products：`0`
  - current effective slots：`4`
  - target effective slots：`7`
  - Stage563 all-breadth sleeve PnL：`9,395`
  - Stage563 prev-year-positive sleeve PnL：`-18,245`
  - hard gates：`6/7`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage638_annual_independent_trend_slot_audit_report_stage638_annual_independent_trend_slot_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage638_annual_independent_trend_slot_audit_decision_stage638_annual_independent_trend_slot_audit_v1.json`
- orders：不适用
- daily：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage638_annual_independent_trend_slot_audit_annual_slot_opportunity_stage638_annual_independent_trend_slot_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage638_annual_independent_trend_slot_audit_family_year_opportunity_stage638_annual_independent_trend_slot_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage638_annual_independent_trend_slot_audit_product_ladder_stage638_annual_independent_trend_slot_audit_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage638_annual_independent_trend_slot_audit_gates_stage638_annual_independent_trend_slot_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage638_annual_independent_trend_slot_audit_chart_stage638_annual_independent_trend_slot_audit_v1.png`

## 图表视觉复盘

- 左上图：
  - 非核心商品 oracle top6 在 `2020-2026` 每年均为正，`2020/2021/2022/2026` 的年度机会尤其明显。
  - 橙线显示年度 top6 家族数每年都在 `4-6`，说明机会不是单一品种或单一产业链独占。
  - 紫线显示 worklist/monitor 年度覆盖很弱，最多只是 `1` 个，低于本阶段要求的 `2` 个。
- 右上图：
  - top6 结构桶大量落在 `p0_reference_existing_slot`、`reject_high_core_corr`、`reject_data_or_liquidity`。
  - P1/P2 只在少数年份出现 `1` 个，无法承担“每年抓部分趋势收益”的主通道。
  - 没有任何年度出现 deployable 新槽。
- 左下图：
  - 家族机会热力图显示年度头部在 `energy_oil`、`grains_oilseeds`、`base_metals`、`petrochem` 间切换。
  - 星号位置说明年度第一家族不固定，这支持“每年不同品种/家族有趋势”的直觉。
  - 但这些家族很多属于既有 P0 或高相关拒绝桶，不能自动变成分散风险槽。
- 右下图：
  - `annual_opportunity_exists` 和 `opportunity_not_single_family_only` 为绿，说明方向本身没有被否。
  - `worklist_monitor_year_coverage` 为 `0`，这是核心失败项：当前 P1/P2/watch 工作流覆盖不了年度赢家。
  - `deployable_new_slot_zero`、`paper_and_whitelist_zero` 为绿，是 fail-closed 纪律，不是晋级。

## 结论

- 本阶段结论：
  - 用户提出的“低单笔风险 + 扩大品种池 + 每年抓部分趋势 + 避免高相关”方向，第一性原理上成立。
  - 证据是：非核心年度 oracle top6 `7/7` 年为正，且 `7/7` 年跨至少 `3` 个家族。
  - 但当前不能晋级：年度 top6 大多落在既有 P0、高相关拒绝桶或数据/流动性拒绝桶；现有 P1/P2/watch 在 `0/7` 年达到本阶段最低覆盖要求；deployable 新槽仍为 `0`。
  - Stage563 也已经说明宽池低单笔风险不能可靠捕获机会：全宽池 sleeve 只赚 `9,395`，上一年为正宽池 sleeve 亏 `18,245`。
- 是否进入下一步：继续，但不能继续扫宽池风险小数。
- 下一步：
  - 不应再做“多加几个品种、降低单笔风险”的宽池调参。
  - 应把重点转向事前 selector：PIT source、基本面/舆情事件、相关性实时状态、真实 TCA 和固定预测力审计。
  - 具体优先级：继续补 `lh.DCE` 新自然日 PIT；同时对年度 top6 里反复出现但被拒绝的 `energy_oil/base_metals/grains_oilseeds/petrochem`，只做“可否拆出真正独立经济驱动”的 source/TCA 审计，不直接加白名单。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有调策略参数、没有改变交易规则、没有使用结果生成交易名单。
  - 年度 top6 是 hindsight/oracle 审计，只用于判断机会结构，不作为策略信号。
  - 失败项被保留为失败项，没有为了晋级而放宽 worklist/monitor 覆盖要求。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但方向需要收窄。
- 原因：
  - 继续价值不在宽池调参，而在建立事前选品能力。
  - 年度机会和家族分散性说明这条线值得保留；Stage563 和 Stage638 同时说明“只靠风险分散壳”不够。
  - 下一步必须回答“能否在当时识别哪个家族/品种更可能出趋势”，否则扩池只会增加噪音。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage338 当前状态。
- 是否更新 `research/registry.md`：是，更新当前阶段摘要。
- 是否追加根目录 `memory.md/back_log.md`：否；本阶段不是正式候选、路线废弃、跨线合并或重大突破。
