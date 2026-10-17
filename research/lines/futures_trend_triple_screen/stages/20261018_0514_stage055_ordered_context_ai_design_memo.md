# Stage055：B 原生时序 context 的一次增量信息评估备忘

- line_id：`futures_trend_triple_screen`。
- 记录时间：2026-10-18 05:14 CST；工作区 `/Users/mac/Desktop/fian`，分支 `codex/ai-training-data-expansion`，读到 HEAD `008575e132ea76032d904cbd407aa6f85566b349`。
- 阶段性质：有限外部调研、机制去重和后续设计；不是候选实现、实验授权或收益结论。是否重要突破：否。
- 决策背景：原 B 的 session70433 / PID21822 仍在执行，尚无完整接受结果；本次未读取 B 中间 PnL、曲线、成交盈亏或部分账户指标。B 的最终结果与审计由原流程完成。
- 本次仅新增本文；脚本、模型、策略参数、行情、已消费来源/协议/收据均未变。训练、金融重放、行情下载、订单、响应 pointer 写入均为 0；没有修改 LINE、registry 或根日志。

## 判断及唯一保留方向

**值得保留一个有条件的问题：B 自身的“逆向准备已持续多久、FI2 已修复到什么程度”能否在旧 19 维之外，帮助排序同一天真实竞争预算的 B 机会。现在只值得先审样本和标签是否可识别，不值得立即重训或再跑一个账户。**

方向是“在 B 事件母体上学习有序准备状态的增量质量”，不是更换 MACD/FI 参数，也不是在原分数上换个软函数。若后续实施，唯一核心配对是：**同一 B 事件样本、同一目标、同一 walk-forward、同一学习器，19 维对 19 维加下述固定 context**。旧 serialized 模型另作参照，不能把重新训练、改变选样或修正目标带来的收益全部归因于 context。

收益更高且 DD 更低只是一种待反证的可能机制：在资源确实不足时，避免把尚未修复的回调与已转为恢复的准备状态混排，可能减少失败入场同时保留趋势右尾。反面同样成立：较久、较深的准备可能正是大行情的起点；新排序会挤走右尾，软排序本身没有免罪权。若不存在真实资源竞争、context 没有额外信息或事件样本不足，本方向没有可交易价值。

## 已读合同、负结果与禁止重复的路线

本次先读 `research/registry.md`、本线 LINE、[035 固定 B 合同](/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/stages/20261018_0333_stage035_b_ts_execution_contract.md)、[024 周 gate 归因](/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/stages/20261018_0156_stage024_terminal_weekly_gate_attribution.md)和 [033 C_TS 负结果](/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/stages/20261018_0325_stage033_c_ts_fixed_negative_result.md)。以下仅复述已经完成的旧结果，没有新增回测：

| 已接受账户 | 期末权益 | 总收益 | 最大回撤 | Sharpe |
| --- | ---: | ---: | ---: | ---: |
| A0 | 2,262,595 | 1,408.396667% | −48.789850% | 1.367364 |
| C0 固定周 gate | 1,190,295 | 693.53% | −43.031732% | 1.185018 |
| C_TS 固定交集 | 660,825 | 340.55% | −32.758963% | 0.991077 |

C0/C_TS 都未同时改善收益与 DD；低回撤不能抵销右尾与收益损失。C_TS 原 fixed-q 合同及其负结果不改，不以本文救 C；B 的 u 已知 T 估量、真实 u 止损 S、最终只缩量风险/保证金钳制、D gap 披露、OI/月资格/通用过滤和原退出路径仍按 035 执行。

另一只读 agent 独立核对四条相关 LINE，我也核对了相应摘要；没有扫描它们的大结果目录：

- [重建二期 Stage015](/Users/mac/Desktop/fian/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/LINE.md:58)：purged meta-label OOS 高分仅在 3/5 年胜低分，高分总 PnL 反而较低。不能以再换一种分类器或旧字段组合解释为新机制。
- [重建优化 Stage058](/Users/mac/Desktop/fian/research/lines/futures_trend_rebuilt_c9_15w_optimization/LINE.md:128)：连续预算没有同时保住全样本右尾与压力段改善。不能把硬 gate 改成连续倍率就当作新方向。
- [全市场 AI Stage009](/Users/mac/Desktop/fian/research/lines/futures_trend_full_market_ai_filter_002risk/LINE.md:141)：尾部 veto 错失 AP605 恢复交易。低排名不等于应该删除，不能再按 topN、品种或坏年份救参。
- [信号质量 AI Stage236](/Users/mac/Desktop/fian/research/lines/futures_trend_signal_quality_ai/LINE.md:43)：路径标签加 purge/embargo 仍没有稳定高低分差异。标签有路径和特征为 PIT，并不等于存在预测力。

因此，仅重组旧 AI rank、OI、账户 DD/loss_streak、分钟形态再软排序，重复风险很高。本文唯一可区别的理由必须是 **B 新事件母体下、原生有序状态提供旧 19 维未表达的信息**；这是待检验的理由，尚未被证明。

## 外部调研：资料支持什么、不支持什么

检索日期为 2026-10-18，仅采用作者材料、论文与官方 GitHub。未下载研究行情或运行外部代码。

1. Elder 本人的书把周线用于战略方向、日线用于回调与入场准备，并以 FI2 描述短期逆向力量。这支持分离方向、回调与执行的机制；不证明固定 B 或加 AI 一定有效。本文不把书中另一套 EMA/Impulse/目标规则移入 B。[作者《Step by Step Trading》，书页 35、45–46](https://s3-us-west-2.amazonaws.com/elderdownload/wp/wp-content/uploads/20180314155306/Step_by_Step_Trading_Elder.pdf)
2. 作者官网确认其工具实现 Triple Screen，含周 MACD 柱方向；QuantConnect 官方实现确认 FI 为价差乘当期量后平滑。它们只支持机制与指标语义，不是中国期货成本后业绩证据，也不意味着本仓库 EMA 起始种子与他库逐值相同。[Elder 官方说明](https://www.elder.com/product-page/elder-disk-2-1-for-ninja-trader-8-v2-1)、[Lean ForceIndex 源码](https://github.com/QuantConnect/Lean/blob/master/Indicators/ForceIndex.cs)
3. TRA 原论文研究股票异质交易模式，说明单一同分布假设可能不足；官方复现表也说明 IC 变好未必使 DD 变好。它不证明 B 存在 concept drift，更不授权迁入复杂路由网络。本阶段只吸收“条件信息须在同样本配对验证”的问题意识。[TRA 原论文](https://arxiv.org/abs/2106.12950)、[Microsoft Qlib 官方复现与结果表](https://github.com/microsoft/qlib/blob/main/examples/benchmarks/TRA/README.md)
4. PBO 论文说明，反复挑选同一历史上的赢家会引入选择偏差，单次历史 holdout 也不能消除研究者已知历史的影响。因此本备忘限制为一组配对，不把重切历史命名成全新 OOS；本阶段没有计算 PBO 或显著性。[Bailey 等原论文，作者网站 PDF](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf)

参考核实：既有合同引用的 [2004 年 5 月 MTA 通讯，第 6 页](https://docs.cmtassociation.org/docs/MTA0405.pdf#page=6)记录了 Elder 于 2003-12-15 的讲座，明确介绍 Triple Screen 的周/日/小时层次、MACD 柱斜率、第二层逆向波动、突破前日高/低的 stop entry，以及 FI 的价差乘量和平滑定义。该讲座记录支持本方向的经典机制依据，不能证明本仓库 alpha 或新 context 有效。本文先前“未找到 Triple Screen/Elder 说明”的判断错误，现据原文更正；不修改已冻结合同或本文其他设计。

## 实际旧模型与 B 的差异：不能把风险说成已证实漂移

本次只静态读相关源文件，没有加载 joblib、执行训练或查询当前 B 结果：

- [runtime](/Users/mac/Desktop/fian/examples/portfolio_backtesting/qmt_roll_ai_selection_pairwise_runtime.py:38)生成单候选字段，再对同日候选构造 pair；19 个输入主要是方向/信号/风险模式相同标志，以及风险、slot、价格/量/OI/横截面和单手保证金相对权益的差分。`same_signal` 比较的是两个字符串是否相同，不是模型直接识别“triple_screen”这个类别。
- [选样器](/Users/mac/Desktop/fian/examples/portfolio_backtesting/build_qmt_roll_ai_candidate_selection_pairwise_samples.py:71)限定旧 `flat_entry` 且同日至少两个候选、至少一项入选并至少一项未入选的竞争日；并非全部日线，也不是全体事件不加选择的母体。v2 在 15 维基础上加 4 维，见 [19 维定义](/Users/mac/Desktop/fian/examples/portfolio_backtesting/build_qmt_roll_ai_candidate_selection_pairwise_samples_v2.py:37)。
- [训练入口](/Users/mac/Desktop/fian/examples/portfolio_backtesting/train_qmt_roll_ai_candidate_selection_pairwise_classifier_v2.py:54)是 StandardScaler 加固定 LogisticRegression，源代码以 2023/2024 切 train/valid/test。此处仅核对设计，未据源码推断当前 serialized 资产的所有训练来源与审计均已完成。
- B 使用 `long_triple_screen/short_triple_screen` 新信号，且 q/保证金按 T 估计；同方向 pair 的 `same_signal`、风险/保证金及竞争组构成可能变化。旧模型在新事件母体的支持与校准未获证明。**这是确定存在的选样机制变化与待测的特征分布/目标适配风险；尚不能由机制变化推导出 P(Y|X) 已变化或旧分数必然无效。**

“重新学习旧 19 维”与“增加 context”是两个不同效果。必须在同一 B 训练母体建立 19 维对照；直接拿新模型胜旧序列化模型，只能说明整体替换有效，不能说明 context 有效。

## 固定 context 与样本/标签先决条件

只预留两个连续变量，不提供候选清单或阈值：

| 字段 | u 时固定定义 | 想表达的增量 |
| --- | --- | --- |
| `setup_age` | 同一 product/contract epoch 内，当前 `setup_day` 到 u 的实际交易日间隔；0 合法；按原状态机的换月、取消、未知和 actual fill 消费边界重置 | 一次逆向准备经历了多长时间；不能把同一 setup 的每日 intent 当独立新机会 |
| `fi_repair_r` | `direction × FI2(u) / (volume(u) × abs(T(u)−S(u)))`；direction 为 ±1，T/S/volume 都取真实 u 已知值；分母非法则缺失并使该研究样本不可用，不回填 D | 在本次风险距离尺度上，逆向力量仍在增强还是已经修复；不设正负 veto 或分桶门槛 |

pair 模型仅增加这两项的左减右差，学习器、正则与权重规则在实施前固定，不搜索额外窗口、层数、交互或产品名单。周许可、FI2 周期、准备/触发/取消规则保持 B 原样。`setup_age` 依 [原状态机](/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/tools/stage027_ordered_state.py:256)的 setup 身份计算；未来须证明字段真在 u 可得，不能只从成功成交回填 setup。两个数只是有机制依据的表述，不是已证实的 alpha。

选样至少包括同一固定 B 环境中、原通用/OI/月资格允许的全部 B intent，记录在 pairwise 排序、slot 与账户预算取舍之前；保留未入选、未触发、取消和成交去向。旧竞争日规则与标签有效性不得用未来是否盈利筛选。重复 intent 按 setup/epoch 归组并保留真实 u/D，不能用相邻日重复样本把置信度放大；不能从当前 B 已成交列表直接造全体训练机会。

旧 [市场标签](/Users/mac/Desktop/fian/examples/portfolio_backtesting/build_qmt_roll_ai_candidate_training_samples.py:158)以 `planned_entry_price` 与 stop 距离构造 5/10/20 日 forward-R；MFE/MAE 的切片从候选日自身开始，尾部还用 `min` 截短。[quality v2](/Users/mac/Desktop/fian/examples/portfolio_backtesting/qmt_roll_ai_candidate_selection_label_v2.py:29)混合这些 forward-R、尾部、MFE/MAE。它们没有表达 B 的以下条件：D 不触发就没有入场、gap 真实成交价与 T 的差别、入场前极值不属于持仓、0.5R 可能先止损、retry 属同母交易、换月/合成成交有真实成本。旧日级代理的 OOS 排序不能当作真实母交易净收益。

**未来目标只接受一个方向：完整 B 规则下该机会的母交易成本后净 R，未触发单独明确记为无成交结果，0.5R/retry/换月按同一母身份归集；分母与可识别价格路径、未触发的监督编码须在训练前单独冻结。** 不在本文随意设新 5/10/20 日截断替代真实退出。先检验能否对未入选机会定义不借未来组合分配、且与原止损/重试/换月一致的价格路径；若不能识别，停止在样本研究，不能用已成交-only、旧日线代理或臆造完整母交易绕过。标签要完全成熟，尾部未结束母交易不可截短后当完整结果；训练资格以标签最终可知时间约束，不能仅沿用 `eval_end < u`。

## 若未来获准，唯一配对与账户作用边界

1. **先样本后模型。** 审计 B 事件母体、两个字段的 u 可得性、旧 19 维支持、重复 setup、实际资源竞争和上述标签可识别性。这个阶段不以 B 最终坏年份/产品挑样本或字段；先决条件失败就停，不训练。
2. **一次配对消融。** M0=在同一 B 样本上学习的 19 维；M1=M0 加上述两维。样本 ID、标签/成熟截止、学习器及全部参数、权重、标准化训练期、时间和产品留出完全相同。旧 serialized 分数是额外参照，不参与调参。固定同日 pair log-loss 与按日期/setup 成组的排序效用差，报告不确定性与逐期稳定性；多对 pair 不算多个独立日期。若留出增量无可靠正证据，结束该方向，不换标签配方、分桶、模型、年份或 FI 窗口补救。
3. **软排序仅提出资源竞争优先级，不提出新拒绝阈值或风险倍率。** 不动原 AI 月池、通用/OI gate、T/S、止损/retry/换月/持仓规则和 035 风险预算。无竞争时应保持原行为。排序会改变预算前缀和整数手数，固定上限并不等于实际杠杆相同；必须报告实际风险/敞口/保证金及 gap，不能把 u 预算称作实际 fill 硬上限。
4. **必须先隔离现有分数耦合。** [原 planner](/Users/mac/Desktop/fian/examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py:4670)让同一 score/rank 参与 slot 顺序、`_apply_selection_pairwise_volume_tilt`、incremental margin 与受保护排名。直接覆盖 `selection_pairwise_score/rank` 会同时改仓位和预算，不能叫纯排序。仅保留旧 score 列也不充分：入选组改变会间接改变 tilt。未来要为 M0/M1 冻结同一可排序机会集与逐项原风险/tilt 需求，另设 priority 身份，并证明两臂除优先级外的 gate、原分数用途和预算函数相同；若做不到这个隔离，不进入账户比较。任何为此新增的接合合同必须另行预注册，本备忘不授权改 035。

历史金融主比较如获准，必须是同一隔离适配下的 M1 对 M0；冻结 B 原账户作行为/总体目标参照。M1 对 M0 的成本后净收益须更高且 DD 幅度更小，Sharpe 不降低，保证金生存不恶化；还需对原 B 和正式对照披露绝对结果，不能靠换低质量 M0 过门。标签层优势只是进入账户验证的必要条件。只降杠杆、少交易、胜率更高、IC 更高或全期一项好看都不通过。若收益/DD 任一主门失败，结束这组 context 结构，不反过来重选字段或利用 B 坏段救参。

## OOS、成本、多周期与停止边界

- 未来训练只用预测日之前已经完全成熟的标签，按时间 expanding walk-forward；同一 setup、母交易及相互重叠结果区间不能跨训练/留出泄漏，按实际结果结束时间 purge，embargo 至少覆盖相应标签依赖。标准化仅拟合训练侧。另做产品组留出，组与切分在看结果前冻结，不挑最佳留出版本。
- 2020—2026 历史已在多条研究线反复使用。时间切分、产品留出和独立起点是历史稳健性检查，不能把它们改称研究者从未见过的未来 OOS。冻结后新增的前向观察另记；没有未来证据不宣称穿越周期或生产资格。
- 先冻结基准同成本，再以实际手续费口径和双倍滑点做压力核验；原接受对照的 commission=0 只是继承口径，不能冒充全部券商成本。真实分钟、gap、同 bar 止损、retry、合成/换月成本均进入最终账户；不把日线价格质量代理直接相加当组合收益。
- 只有主配对和账户门均通过，才进入既定 1 月/6 月独立起点及 1/2/3 年固定多周期，完整列出所有预注册起点和成本情景。多周期不改参数，重叠窗口不算独立证据；弱段、右尾替换损失和杠杆变化需独立复核。若失败不继续换起点救结果。
- 当前 B 完整结果出来前不实施本文。若 B 的机制、数据或执行审计先失败，先处理其实际失败；本文不豁免 035 已有停止规则，也不自动生成“B2”。如果最终 B 的资源竞争/可识别样本不足，这一方向即失去继续依据。

## 本阶段结果及反思

新增/修改/删除策略参数：均无。新增/修改/删除回测结果：均无。本文本阶段的期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数和胜率均为 **N/A（未运行）**，上表为明确标注的历史证据，不能计作本轮收益。

开始时是否在过拟合：否，本次按既有合同查机制与去重，不据 B 途中盈亏选方向；但同一历史已被反复使用，后续数据驱动筛选存在明显选择风险。结束时判断仍为否：仅冻结了一个待否证问题，没有拟合、扫参或声称优越。

是否还有继续价值：**设计去重和样本/标签可识别性审计有价值；立即训练或金融实施的价值尚未成立。** 只有 B 完整审计、真实竞争和独立标签合同共同提供依据，才值得由 root 决定是否另行立项。外部经典机制与机器学习论文都没有替本仓库完成这一证明。

本阶段仅建议保留此条件问题；不更新 LINE/registry/根日志，不注册新实验臂，不改变当前 B 的终态判断和累计试验谱系。
