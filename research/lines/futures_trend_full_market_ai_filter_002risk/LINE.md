# 全市场 AI 过滤 + 0.02 基础风险研究线

- line_id: `futures_trend_full_market_ai_filter_002risk`
- 创建时间: `2026-07-09 17:07 CST`
- 当前模式: `day`
- 资产/策略: 商品期货趋势 / 当前 C9 15w 引擎的独立研究分支
- 当前状态: 新建独立研究线，尚未形成晋级候选
- 基准: 当前实盘默认 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`

## 研究假设

用 point-in-time 的全市场月度品种过滤，替代旧静态/半静态品种池；特征固定包含：

- 该品种在当前策略下截至评估日的累计赚钱能力。
- 近 126 个交易日赚钱能力。
- 近 63 个交易日亏损压力，作为风险惩罚。
- 已有可用基础特征：成交活跃度、近端数据覆盖率、保证金颗粒度。

候选只改变三件事：

- AI 排名候选从旧固定池拓展为当前仓库可交易、可映射、数据覆盖达标的全市场 57 个品种。
- 每月只保留 AI top8，不强制加入固定卫星品种。
- 基础风险比例改为 `0.02`。

## 反过拟合边界

- 不使用评估日之后的单品种收益做当月特征。
- 不按坏窗口加入品种黑名单。
- 不扫 `topN`、窗口天数、权重小数或风险小数；Stage001 固定为 top8、126/63 日窗口、预声明权重、基础风险 `0.02`。
- 若单一起点真实引擎明显失败，先停止并归因，不直接救参。

## A/B/C 预声明

- A: 当前官方 C9/15w 实盘默认，复用已生成 Stage167 曲线。
- B: 全市场 AI 过滤器 standalone 没有独立交易含义，只做 eligibility/feature 审计。
- C: A 的 C9 交易逻辑 + 全市场 PIT AI top8 eligibility + 基础风险 `0.02`。

## 通过标准

- 第一关: 2020-01 到 2026-06-30 单一起点 C 不能明显破坏 A 的收益/回撤/交易质量。
- 第二关: 若第一关有价值，再做 2020-01 起逐半年多周期，终点 2026-06-30。
- 第三关: 独立 agent 审计必须确认结果、数据、逻辑、置信度和潜在 bug 口径清楚。

## 当前 TODO

- 当前 full-market score-only selector、broad-veto、official-pool bottom25 veto、guarded official-tail veto 均已验证并收束，不晋级正式版。
- 不继续扫 topN、窗口、权重、rank 保护层、bottom quantile、月份、品种或风险小数。
- 若继续本大方向，必须换真正外生新信息源或结构不同且能穿越周期的账户/组合层设计；否则只保留 Stage009 归因经验。

## Stage001

- 时间: `2026-07-09 17:17 CST`
- 决策: `stage001_stop_or_attribution_before_more_runs`
- C 期末权益: `522,613.50`，总收益 `248.4090%`，最大回撤 `-29.3247%`，Sharpe `0.9321`。
- 状态: 已跑单起点真实引擎，等待独立 agent review 后再决定是否扩展逐半年多周期。

## Stage001

- 时间: `2026-07-09 17:20 CST`
- 决策: `stage001_stop_or_attribution_before_more_runs`
- C 期末权益: `268,976.10`，总收益 `79.3174%`，最大回撤 `-69.1326%`，Sharpe `0.4442`。
- 独立 review: `2026-07-09 17:26 CST` 完成；未发现 P0，确认 v2_rankfix 接线和统计口径基本成立，但结果明确失败。
- 状态: 不进入逐半年多周期，不扫 topN/窗口/权重/风险小数；如继续，只做只读归因，解释错过官方 C9 核心右尾的原因。

## Stage002

- 时间: `2026-07-09 19:26 CST`
- 决策: `stage002_stop_or_attribution_before_more_runs`
- C 期末权益: `106,927.80`，总收益 `-28.7148%`，最大回撤 `-94.4881%`，Sharpe `0.2625`。
- 独立 review: `2026-07-09 19:55 CST` 完成；未发现 P0，确认 AI eligibility、`risk_ratio=0.02` 和 summary 接线基本成立，但指出 OI restore 让大量入场有效 `risk_multiplier=2.0`，不能解释为所有入场风险严格 `2%`。
- 状态: 不进入逐半年多周期，不扫 veto 分位；下一步若继续，只验证 `0.02` 有效风险上限与 OI restore 叠加问题。

## Stage003

- 时间: `2026-07-09 19:36 CST`
- 决策: `stage003_stop_or_attribution_before_more_runs`
- C 期末权益: `525,988.00`，总收益 `250.6587%`，最大回撤 `-81.9919%`，Sharpe `0.6378`。
- 独立 review: `2026-07-09 20:05 CST` 完成；未发现 P0，确认 OI restore 已关闭且 `risk_multiplier=1.0`，但结果仍明显失败。
- 状态: 不进入逐半年多周期；停止 `full-market broad-veto + 0.02 effective risk` 候选推进，只保留失败归因价值。

## Stage004

- 时间: `2026-07-09 21:28 CST`
- 决策: `stage004_stop_or_attribution_before_more_runs`
- C 期末权益: `568,439.20`，总收益 `278.9595%`，最大回撤 `-66.3656%`，Sharpe `0.7040`。
- 独立 review: `2026-07-09 21:40 CST` 完成；无 P0，确认 active top quartile、PIT、AI 接线、有效风险 `0.02` 和 summary 统计均自洽，但收益保留仅 `7.1782%`。
- 状态: 不进入逐半年多周期；停止 full-market score-only selector 候选推进，避免继续救 topN/分位。

## Stage005

- 时间: `2026-07-09 22:25 CST`
- 决策: `stage005_continue_to_halfyear_if_independent_review_passes`
- C 期末权益: `4,407,585.30`，总收益 `2838.3902%`，最大回撤 `-46.1580%`，Sharpe `1.3541`。
- 收益保留率: `0.7304`，回撤变化 `9.2121` 百分点。
- 状态: 已跑单起点真实引擎，等待独立 agent review 后再决定是否扩展逐半年多周期。

## Stage005

- 时间: `2026-07-09 22:27 CST`
- 决策: `stage005_continue_to_halfyear_if_independent_review_passes`
- C 期末权益: `4,407,585.30`，总收益 `2838.3902%`，最大回撤 `-46.1580%`，Sharpe `1.3541`。
- 收益保留率: `0.7304`，回撤变化 `9.2121` 百分点。
- 独立 review: `2026-07-09 22:40 CST` 完成；未发现未来函数、同日泄漏、AI 未接入、summary 算错、风险参数误改或实盘路径污染，但指出 P0/审计阻塞：C 使用当前磁盘官方 AI 文件，A 基准为冻结 Stage167 曲线，二者 AI 文件版本不完全一致。
- 状态: 不直接进入逐半年多周期；先跑 Stage006 当前官方 AI 无 veto A0 vs 当前官方 AI + full-market bottom25 veto C 的同引擎配对，修复 A/C 口径。

## Stage006

- 时间: `2026-07-09 22:38 CST`
- 决策: `stage006_continue_to_halfyear_if_independent_review_passes`
- A0 期末权益: `5,996,631.00`，总收益 `3897.7540%`，最大回撤 `-55.3701%`，Sharpe `1.3967`。
- C 期末权益: `4,407,585.30`，总收益 `2838.3902%`，最大回撤 `-46.1580%`，Sharpe `1.3541`。
- 收益保留率: `0.7282`，回撤变化 `9.2121` 百分点。
- 状态: 已跑同口径单起点真实引擎，等待独立 agent review 后再决定是否扩展逐半年多周期。

## Stage007

- 时间: `2026-07-09 23:04 CST`
- 决策: `stage007_stop_or_attribution_before_more_runs`
- 样本数: `13`，C 正收益 `12`，收益保留>=50% `11/13`，回撤改善 `12/13`。
- 最小/中位收益保留: `-1.9044` / `0.7450`；C 最差回撤 `-46.1580%`。
- 独立 review: `2026-07-09 23:10 CST` 完成；无 P0，确认 A0/C 同口径、PIT、AI 接线、风险口径和实盘隔离均成立；严格目标失败是正确结论。
- 状态: 不直接晋级，不扫 veto 分位；下一步只允许一个低过拟合 guarded 版本：full-market veto 只作用于 official 低置信层，不否决 official 高 rank 核心品种。

## Stage008

- 时间: `2026-07-09 23:33 CST`
- 决策: `stage008_stop_or_attribution_before_more_runs`
- 规则: 保护 official rank <= `4`，full-market bottom25 veto 只作用于 official 尾部。
- 样本数: `13`，C 正收益 `12`，收益保留>=50% `12/13`，回撤改善 `11/13`。
- 最小/中位收益保留: `-2.4461` / `0.7892`；C 最差回撤 `-47.0256%`。
- 独立 review: `2026-07-09 23:43 CST` 完成；无 P0/P1，确认 A0/C 同 AI 文件、同引擎，C 是 A0 子集，rank<=4 保护生效，PIT/AI 接线/summary/风险口径自洽。
- 状态: 不晋级，不继续扫 `PROTECTED_OFFICIAL_RANK_MAX`、bottom quantile、月份、品种或权重；只保留为防守型 overlay 经验，并转 Stage009 做 2026-01 失败窗口只读归因。

## Stage009

- 时间: `2026-07-09 23:45 CST`
- 决策: `stage009_close_branch_keep_attribution_only`
- 性质: 只读归因 Stage008 的 `2026-01` 失败窗口，不新增参数、不改策略、不碰实盘链路。
- A0 期末权益: `154,651.60`，总收益 `3.1011%`，最大回撤 `-14.2479%`，Sharpe `0.3734`。
- C 期末权益: `138,621.60`，总收益 `-7.5856%`，最大回撤 `-15.6688%`，Sharpe `-0.4790`。
- 核心归因: `2026-01-30` 月池中 `AP.CZCE` official rank `7` 且 full-market rank pct `0.8704`，被 guarded tail bottom25 veto；A0 在 `2026-02-13` 开 `AP605.CZCE` 多头 3 手并于 `2026-03-05` 平仓，产品层 C-A0 机会成本 `-21,300`。
- 抵消项: `MA.CZCE` 产品层 C-A0 `+3,310`，`SM.CZCE` `+1,760`，不足以抵消 AP。
- 独立 review: `2026-07-09 23:50 CST` 完成；无 P0/P1，确认 Stage009 只读、A0/C 与 Stage008 一致、missing entry 归因和产品 PnL diff 闭合。
- 状态: 本分支收束；除非引入真正外生新信息源，不继续围绕 rank/分位救参。
