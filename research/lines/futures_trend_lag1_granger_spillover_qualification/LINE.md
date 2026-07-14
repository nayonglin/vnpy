# Lag-1 Granger 动量溢出资格线

- line_id: `futures_trend_lag1_granger_spillover_qualification`
- 创建时间: `2026-07-13 00:26 CST`
- 当前模式: `day`
- 资产/策略: 商品期货趋势 / 当前 C9 15w 独立研究分支
- 当前状态: Stage001 已完成并关闭；透明 lag1 Granger 网络在冻结 global BH 门下显著边为0，未形成信号或策略候选
- 当前基准: `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 独立性: 只写本研究线目录；不改正式实盘、CTP、邮件、launchd、AI 月池或其他研究线

## 研究目标

- 验证国内商品之间是否存在跨时间稳定、严格 T-1 可观测的 lag-1 预测信息，使 C9 不只依赖每个品种自己的趋势。
- 只在透明、低自由度的 Granger 网络资格门通过后，才允许讨论把 leader momentum 作为 C9 的独立特征或并行信号。
- 最终目标仍是多锚点收益保留正式 A 至少 `70%`，同时严格降低最大回撤并缩短 2022 水下期；Stage001 不读取这些收益结果。

## 外部调研与判断

- `Follow the Leader: Enhancing Systematic Trend-Following Using Network Momentum`（arXiv:2501.07135）和 `Network Momentum across Asset Classes`（arXiv:2308.11294）都给出跨市场动量溢出的实证先验。
- 2026 年 commodity Granger-causality network 研究说明 Granger 网络是更透明的多商品 interdependence 入口。
- statsmodels 0.14.6 官方文档和 GitHub 源码提供 lag-1 Granger F-test 与 Benjamini-Hochberg 多重检验修正。
- 不直接复制论文完整 NMM：原文对 graph `alpha/beta` 做样本内净 Sharpe 网格搜索，并比较多类 DTW/Levy 模型；仓库没有作者代码和 CVXPY/DTW 依赖，直接移植自由度过高。
- 本线只审计一个明确的低自由度子假设：lag-1 Granger spillover 是否广泛且半窗同号。它失败只关闭这条透明 lag-1 路线，不宣称推翻所有 network momentum 模型。

## Stage001 冻结合同

- 事件全集：Stage131 冻结的 `365` 个 current-C9 唯一入场事件，`2018-01-15 -> 2026-04-30`；不只看亏损、2022 或某些品种。
- 重点完整性子集：2022 全年 `48` 个事件，不使用 `2022-03-09 -> 2022-06-29` 亏损窗口作筛选或调参。
- leader 宇宙：full-market tradable eligibility 中 `eligible=1` 的固定 `57` 个产品；每事件排除 target 自身，上市前或历史不足产品留在不可用分母记录。
- 日收益：从本地 `database.db` 读取实际合约日线。return date `d` 的合约只能由产品在前一有效交易日 `d-1` 的 OI 最大值选择，平局按合约代码固定升序；收益必须用同一实际合约 `close[d]/close[d-1]-1`，禁止主连换月直接相除。
- 历史窗：每个 event-target/leader pair 只取严格 `< entry_date` 的最后 `132` 个共同有效 return dates；不足不补、不缩窗。
- 模型：固定 lag `1`；检验 `target_t = c + target_(t-1) + leader_(t-1)` 相对仅含 target lag 的受限模型，使用 statsmodels `ssr_ftest` p-value。
- 多重检验：对全部 event/leader 原始 p-value 一次性使用 `fdr_bh`、`alpha=0.05`；禁止按事件或年份单独放宽。
- 稳定边：全132日经 global BH 拒绝零假设，且 leader 系数在 full132、early66、late66 三窗均有限、非0、同号；半窗只检查符号，不再次选阈值。
- 资格事件：至少有1条稳定 incoming edge，且至少 `29/56` 个非自身 leader pair 拥有完整132共同日。
- Stage001 不读取事件入场后的收益、逐笔 PnL、账户权益、最大回撤、水下期、胜率或交易成本。

## Stage001 硬门

- Stage131 行数/唯一事件/SHA 与当前冻结源一致；full-market eligible 固定为57产品；数据库前后 SHA 一致。
- 合约日线无重复 contract/date；所有 selection_date 严格早于 return_date；所有 ok return 均同合约 close-to-close、有限，跨合约直接相除为0。
- 全365事件 target 自身历史完整率 `>=90%`；2022 全48事件 target 历史完整率 `>=90%`。
- 全事件中资格事件率 `>=90%`；2022 全年资格事件率 `>=90%`。
- 2018-2026 每个有事件年份的资格事件率均 `>=80%`，避免总样本被少数年份掩盖。
- 任一硬门失败：`CLOSE_LINE_LAG1_GRANGER_NETWORK_INELIGIBLE`，不得构造 feature、回测或 A/B。
- 全部门通过：`ALLOW_STAGE002_NETWORK_SIGNAL_PREDECL_ONLY`；仍然 `ready_for_strategy_ab=false`、`ready_for_live=false`。

## 反过拟合边界

- 不扫描 lag、132/66窗口、FDR方法、alpha、覆盖率、leader数量、产品、方向、年份或边定义。
- 不把 global BH 改成 event-level BH，不把半窗同号改成任一窗通过，不只回测显著边覆盖事件。
- 不把失败后缺少的网络边用 contemporaneous correlation、DTW、图模型或人工产业链映射补齐；这些必须另开线重新预声明。
- Stage001 只回答“透明 lag-1 网络是否有资格”，不根据 2022 表现选择模型。

## Stage001 最终结论

- T-1 selection `96,806` 行、ok returns `96,134`、panel `2,750` 日；重复、未来日期、跨合约直接收益和非有限ok收益均0。
- `365×56=20,440` 个 event/leader tests，完整132日 `14,747`；target历史完整 `358/365`，2022 `48/48`。
- raw `pmin=1.3762259248285614e-05`，global BH `qmin=0.066430622945741`、reject `0`；半窗同号 `7,186`，稳定 incoming edge `0`。
- 资格事件 `0/365`，2022 `0/48`；机械决策 `CLOSE_LINE_LAG1_GRANGER_NETWORK_INELIGIBLE`。
- 首轮 P1 的最高OI前过滤close问题已修复，真实命中0，结果不变；修复后终审 `P0=0/P1=0/P2=1/P3=0`、置信度99%。
- 唯一 P2 是重叠事件下 BH 的形式依赖保证未证明，已降级为预声明机械门解释，不影响闭线。

## 当前 TODO

1. 本线关闭，不构造 network feature，不运行回测、A/B 或 live。
2. 禁止扫描 lag、窗口、FDR、alpha、leader数、产品或年份救参。
3. 未来若另开复杂 network momentum 线，必须事前解决重叠依赖、提供可复验实现，并重新预声明；不得复用本线零边事件作筛选。

## 外部资料

- https://arxiv.org/abs/2501.07135
- https://arxiv.org/abs/2308.11294
- https://www.sciencedirect.com/science/article/pii/S0301420725003629
- https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.grangercausalitytests.html
- https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html
- https://github.com/statsmodels/statsmodels/blob/main/statsmodels/tsa/stattools/_stattools.py
- https://github.com/statsmodels/statsmodels/blob/main/statsmodels/stats/multitest.py
