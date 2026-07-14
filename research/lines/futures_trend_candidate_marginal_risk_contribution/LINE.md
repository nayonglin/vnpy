# 趋势策略候选边际风险贡献研究线

- line_id: `futures_trend_candidate_marginal_risk_contribution`
- 创建时间: `2026-07-12 18:12 CST`
- 当前模式: `day`
- 资产/策略: 商品期货趋势 / 当前 C9 15w 独立研究分支
- 当前状态: Stage001 四锚点 1x 真引擎 canary 已完成并触发9项硬失败；独立结果复核 `P0=0/P1=0/P2=2`、可信度99%；本线关闭，不运行 full/2x/3x，不救参
- 当前基准: `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 独立性: 只写本研究线目录；不改正式实盘、CTP、邮件、launchd、AI 月池或其他研究线。

## 研究目标

- 当前用户目标：每个验证起点保留 A 至少 `70%` 的收益，同时严格降低最大回撤，重点改善 2022 路径和最长水下期。
- 不接受仅靠统一降风险换平滑；C 必须根据候选订单对**当前组合的边际风险贡献**做有条件缩手，分散化候选不受罚。
- 先做一次最小有效 canary；只有冻结 gate 全过，才允许扩展逐半年和成本压力。

## 结构性假设

旧 `futures_trend_signed_covariance_risk_budget` Stage001 实际计算的是绝对组合 inflation，且只取得 `40` 个收益观测，并不是候选的边际风险贡献。新线验证一个不同问题：当某个 `flat_entry` 候选与现有持仓及同日其他候选共同放大组合风险时，只缩小该候选手数；当它独立或提供分散化时保持正式手数。

## 冻结候选语义

- A：当前 C9/15w 正式风险、AI 和执行逻辑。
- B：无；风险 sizing 层没有 standalone alpha，不制造无意义的单腿回测。
- C：A + 候选边际风险贡献缩手，只作用于 `flat_entry`，不改 Close、换月、已有仓、加仓、0.5R stop/retry、AI 池或正式信号。
- 观察窗固定 `63` 个严格日期对齐的交易日，不扫描相邻窗口；每次只使用候选时点 T-1 及以前数据。
- 使用收缩协方差；具体估计器必须在 Stage001 预声明中冻结并有独立数值测试。
- 同一时点/同一交易日的正式 baseline 候选先形成完整提案集合，形成带方向的现金风险暴露向量 `x`，避免逐个处理顺序影响。
- 冻结使用标准可加总风险贡献，而不是 raw leave-one-out 方差差：`sigma_p=sqrt(x'Σx)`，`MRC_i=(Σx)_i/sigma_p`，`RC_i=x_i*MRC_i`。
- 候选自身风险分量为 `IC_i=x_i^2*Σ_ii/sigma_p`，相关风险为 `CC_i=RC_i-IC_i`。当 `RC_i <= IC_i` 时保持正式手数；仅当 `RC_i > IC_i > 0` 时按 `IC_i / RC_i` 缩手。
- 只允许 `0 < final_volume <= baseline_volume`；整数化规则在 Stage001 结果可见前冻结，失败后不改 floor/ceil/min-lot 救参。
- 某日共同有效观测不足63、非有限值或时点证据不闭合时，该日整个MRC batch显式 unavailable并保持A手数；不得静默采用未来数据、缩短窗口、补零或临时替代源。
- 同日批量、日期对齐、方向、合约乘数、价格、手数、保证金顺序和 broker10 必须逐事件留证。

## 预声明验证顺序

1. 外部一手资料/GitHub 调研，并审计当前仓库是否能提供 T-1、63 日、同日批量和真实持仓暴露。
2. 先完成纯函数和负例测试：顺序不变性、单候选/独立/正相关/负相关、缺样本、NaN、未来日期、整数边界。
3. 静态审计必须证明 A 复现、AI 输入一致、无候选放大、日期和 source hash 闭合。
4. 最小 canary 固定为 `2020-01 / 2022-01 / 2022-07 / 2026-01 -> 2026-06-30`、1x 成本；不先跑 full。
5. 每次回测后由独立 agent 全面复核结果、数据、逻辑、置信度、未来函数和 bug。

## 冻结通过门槛

- 四锚点均无破产、会计/持仓/现金/保证金闭合，A 与冻结基准逐锚点一致。
- 四锚点收益保留均 `>=70%`；不得用某一高复利锚点掩盖最新或 2022 起点失败。
- 所有历史锚点最大回撤严格改善；`2022-01` 与 `2022-07` 还必须最长水下期严格缩短。
- `2026-01` 最大回撤不得恶化超过 `1pp`。
- broker10 峰值不得恶化；C 不得在任何局部候选或最终成交上放大 A 手数。
- 只有 canary 全过，才允许逐半年完整面板与 2x/3x 成本压力；任何 gate 失败立即关闭，不修改窗口、比例、估计器或整数规则。

## 反过拟合边界

- 不按 2022 亏损品种、方向、月份或单笔交易做黑名单。
- 不扫描窗口、协方差估计器、阈值、scale 指数、minimum lot、topN、AI rank 或风险小数。
- 不把 Stage137 的赢家/输家标签作为输入。
- 不因 canary 失败添加第二层账户状态、ramp、quality 或产品例外。

## 当前 TODO

- 本线不再新增回测、参数、窗口、估计器、整数规则、品种或例外。
- 保留全部明细作为失败法证；后续任何复用工具前先处理已记录的两个 P2。
- 总体目标若继续，必须另开结构不同的新线并重新做外部调研、预声明、最小 canary 和独立结果审查。

## Stage000 外部调研结论

- Alexander/Fabozzi 的 2026 leave-one-out 风险分解说明，标准风险贡献可以拆成自身方差与对其余组合的协方差，并保持严格可加总；同时明确 raw incremental volatility/leave-one-out 差值不满足严格可加性。因此本线已在任何结果可见前废弃初始 `Var(full)-Var(without i)` 规则，改用标准 `RC_i=x_i(Σx)_i/sigma_p`。
- Roncalli 的 risk budgeting 材料给出 marginal volatility 与 component risk contribution 的标准定义，并说明负相关本身不等于有效对冲；只有相关风险足以抵消自身风险时，仓位才真正降低组合风险。
- Ledoit/Wolf 证明高维有限样本下样本协方差可能病态；收缩到单位阵的凸组合能改善条件数。实现候选冻结为 `sklearn.covariance.LedoitWolf`，不手写估计器，也不扫描 shrinkage。
- `pysystemtrade` 把 position sizing、correlation 和 diversification multiplier 分层，并明确 shrinkage 校准有风险。本线只借鉴分层和证据留存，不复制可加杠杆的 diversification multiplier。
- 我的判断：标准可加总 RC + 只缩手是可继续验证的一般化结构；raw leave-one-out 差值、绝对 portfolio inflation、事后 2022 黑名单和加杠杆均否决。
- Stage001 独立数据审查后，不再使用缺逐日发布版本证据的历史主力连续收益；MRC只使用当日actual持仓/候选合约各自的T-1日线。current-C9 2020锚点真实would-open batch覆盖为 `264/265`，唯一 `lh2109.DCE/2021-04-09` 仅58日，整批no-op。

## Stage001 最终结果与路线关闭

- A/C 四锚点收益保留为 `60.8854% / 87.6814% / 61.2160% / -83.8077%`，三个锚点低于70%。
- 2020 回撤 `-55.3701% -> -57.2294%`，2022-01 `-39.9820% -> -40.6473%`；2022-07 虽改善至 `-53.4343%`，最长水下却由665增至780天。
- 2026 从 `+3.1011%` 变为 `-2.5989%`，回撤恶化 `2.0575pp`，broker10 恶化 `3.3121pp`。
- 真实 MRC 并非空跑：四锚点分别缩手 `126/55/43/9` 个候选、减少 `1301/99/88/17` 手；失败来自缩手改变后续复利和机会序列。
- 独立结果审查复算8臂绩效、40份核心gzip、2,267,438条position、AI eligibility、63日T-1矩阵、394源和23文件；`P0=0/P1=0/P2=2`，可信度99%，确认 decision 的9项失败与 `full_allowed=false` 正确。
- 已记录但不影响本次结果的P2：目录内旧压缩面板未被任何运行路径引用；`reduced_candidate_count/reduced_volume>0` 尚未成为显式 runtime gate，但本次每锚点缩手证据均非空。
- 结论：本线关闭。继续修改63日、LedoitWolf、RC/IC/CC、scale、floor/min1、产品或锚点属于事后救参和过拟合。

### 一手资料/GitHub

- https://arxiv.org/abs/2604.10375
- https://www.thierry-roncalli.com/download/risk-budgeting.pdf
- https://www.sciencedirect.com/science/article/pii/S0047259X03000964
- https://scikit-learn.org/stable/modules/generated/sklearn.covariance.LedoitWolf.html
- https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md
