# Stage034：B_TS 最小接合只读设计复核

- line_id：`futures_trend_triple_screen`；核对时间：2026-10-18T03:21+08:00。
- 范围：只读源码、已接受 actual settings / 模型摘要与既有设计；本文件为唯一新增资产。没有改策略、引擎、runner、测试、LINE、registry、正式物料或失败输出；没有跑金融、preflight、模型加载/训练或联网。
- 已先读 `research/registry.md`：当前索引未列出这条已存在研究线；按 root 明确分工继续使用本线，不另建重复线、不改用户脏 registry。
- Stage031 已由 root 观察 terminal exit0；Stage033 独立经济审计仍在进行。本文件不读取或据其收益挑选规则，不宣告 C 或 B 的经济结论。B 已在 Stage027/028 收益前预声明，当前核对不是救 C 的周/FI 参数。

## 调研与判断

复用已核的 [CMT Elder 讲座](https://docs.cmtassociation.org/docs/MTA0405.pdf)、[LEAN ForceIndex 源码](https://github.com/QuantConnect/Lean/blob/master/Indicators/ForceIndex.cs)和 [Backtrader 执行文档](https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/)。本次不重复泛搜；以仓库真实 producer / consumer 路径为接合证据。多周期许可、逆向准备及以后突破是可反证结构，经典出处不能提供盈利保证。工程判断是：B 可按最小研究子类接入，但必须先排除旧标签和候选池语义残留；不能把能接通模型或原生 gate 称为 B 的 alpha 已获资格。

## 可行性结论与最小差异

| 核对项 | 源码事实与最小接合要求 |
| --- | --- |
| 同一 context 与时序 | 原 `on_bars` 先建立 `day_contexts`，再算环境快照、调用 `_plan_flat_entry_candidates`，随后逐产品再次读取 `context.signal_data`（qmt strategy 1306—1468）。B 必须在原 planner 之前，对实际 flat context 复制原 `signal_data` 并替换其 `signal/risk_mode`，赋回同一个 context。只改临时 plan 不会改变后续产品循环；只把 C 的后置观察 arm 改 B 也不会产生缺少 native plan 的独立机会。 |
| 每日状态恰好一次 | `OrderedSetupMachine('B_TS')` 可在 setup_day 当日产生下一真实交易日 intent，不要求 C9 信号，且 unknown 不 fallback（Stage027 179—281）。每产品 u 收盘先观察一次并缓存 decision；原 planner 返回后只关联其选中 q/S，不能第二次 `on_close`。已持仓产品仍观察 hard block 清准备，但其 context 信号不能替换。无映射、合法日线或 AM 可用 context 时要区分：可观察的真实市场 bar 可更新准备；没有可执行 context / entry day 许可时不得发金融 intent。 |
| 无 B intent 的 flat context | 必须把送入原 planner / 原产品循环的金融 `signal` 清为 `''`。unknown、周中性、AI 不允许、无合法 bar、未准备或终点无下一日均不能保留原 native 标签开普通单。`baseline_fallback` 对 B 必须恒 false。指标 unknown 与分钟缺失不得混同。 |
| 通用入场过滤 | 实际 A/031 设置启用 `ma5_extreme_filter_enabled`、`short_ma5_slope_filter_enabled`、`wick_chop_filter_enabled`。这些只在 `_generate_signal` 末尾通过 `_passes_entry_filters(signal, history)` 过滤原标签；替换标签后不再自动执行。root 本轮明确选择：对新的 B 标签显式调用该真实双参数方法，拒绝时 machine 仍已完成当天观察，但不得送 planner 金融信号。它只依 long/short 前缀，不要求 case 标签；不新增 native MA 交叉、排列或 MACD 信号要求。保留这一层是显式共同过滤合同，不能默默绕过，也不能按回测好坏决定去留。 |
| 新空头标签 | `_is_native_openable_candidate` 对 long 只查 `long_entry_enabled`；不存在对应 `_can_open_long_signal`。short 还查 `_can_open_short_signal`，基类只允许 `short_case1a`（4091、8364）。只在 B 子类显式允许 `short_triple_screen`；不改正式 whitelist，不把 B 伪装 `short_case1a`，不泛放所有 short 标签。 |
| OI 风险模式 | 原 `_generate_signal` 只有 `signal` 非空时才计算 generic OI mode。B 不得继承“无旧信号所以 regular”或其他旧信号状态。对新 B 信号按 u 的原 history 依序调用 `_volume_open_interest_risk_mode(history)`、`_open_interest_risk_mode(history)`，均空才 `regular`；沿原阈值和 risk ratio，不扫描或引入 ma_cross/breakout 风险档。OI-price-confirm restore 独立按 history/direction/entry_context 工作，不要求 case 标签，继续原值。 |
| 初始保护 S | 真实 MRO 为 847→830→827→804；804 启用 long tighter stop，long 的 u-close 初始 S=`max(low(u),close(u)*(1-stop_loss_pct))`，不是裸 qmt 的旧 fallback。short 继承 qmt `_entry_stop_price`：day extreme 路径 `min(high(u), min(close(u)*(1+pct), recent3_high_max))`。两者均不看 case 标签。S 始终从真实 u bar/history 计算。初版“沿旧 close 估价 q、不按 trigger 定量”的待冻结建议已被 root 后续选择取代：B 在 u 用已知 trigger 估风险/保证金并冻结 q；见末尾追加。C/031 原合同不改。 |
| 共同账户 cap / allocator | 830 `_calculate_entry_sizing` 只按 `entry_context`、u 的权益/已预留 margin 和参数裁量，没有 case 标签条件。原 planner 的同日候选评分、slot、volume tilt、incremental margin gate 与产品循环原预留位置继续使用（4670—4830）。B 的候选池与风险模式变了，q 只能称“B 自己的原 allocator 选中 q”，不能声称等于 A/C q。选中后改为 conditional_pending，冻 q/S/排序；D 未触发或止损不重分配给其他 intent。u 的 broker10 cap 不是实际 fill 的保证金/R 硬上限，沿 028/031 披露和实际审计。 |
| 持仓与真实执行 | 既有持仓的 native context 信号/指标/历史不改；reverse 当前为 false。母 entry 之后保持原 0.5R/retry/止损/加仓/换月管理。B 新标签只用于初始信号身份；实际 `_open_position` 接受其字符串，layer/状态保存新标签但止损按方向/价格/数量工作。复用 0242 的入场当日 lifetime OHLC 与真实分钟 gate，AM/history/env 仍是真实完整日线；普通/已有仓/roll 不套新初始视图。 |

环境快照在 planner 之前已完成。当前 `enable_weighted_env_gate/enable_portfolio_env_gate` 未在 accepted settings 覆盖，基类默认均 False；不得为了 B 打开。如果未来启用，B 信号注入晚于旧快照会使其仍基于 native 候选池，此处必须另定合同，不能事后把该快照称为 B 的环境选择。

`signal_data` 的 RSI、MA、bullish/bearish 等完整收盘技术字段必须复制保留，供原持仓路径使用。独立 B 不继承 `_generate_signal` 的 native 交叉/排列/MACD 触发资格。原 `breakout` 目前只用于诊断，不是 B trigger；不得把它重命名为“三重滤网突破已发生”。B 真突破只在下一真实 D 的分钟队列 pop 时成为 fill。

## 模型及旧精确标签域

冻结 pairwise classifier 的实际 summary `model_metadata.feature_columns` 为 **19 个数值特征**：V1 为 15 个，V2 新增 4 个。旧“20 features”是历史笔误，本次更正，不改旧 receipt。原 accepted pipeline 是 scaler + logistic classifier；没有 OHE 新类别维度，但仍有 `feature_pair_same_signal`、`feature_pair_same_risk_mode` 数值项。B 同方向候选统一新标签，会改变 same_signal 的分布，且新的入场样本域不等同原 case 样本。继续原模型字节、参数与评分算法、不重训；必须将其表述为既有模型在新 B 域的外推，而非“无 OHE 所以训练资格等价”。

两处旧 catastrophe-veto helper 只匹配 `short_case1a/short_case2`（qmt strategy 4445；pairwise runtime 144）。B 新标签默认不会匹配；accepted veto 开关本身为 False，hard filter 默认 False，不能为 B 自动泛化名单或开关。`_entry_structure_recovery_fields` 的 whitelist 为 `long_case1a,short_case1a`，B 新标签不匹配；accepted `enable_streak_entry_structure_risk_recovery=False`，recovery sleeve 也 False，本次不扩 whitelist、不启用或补偿风险倍数。若后来要适配这些 case-specific 层，须独立收益前合同，不能根据 B/C 差异找回收益。

模型输入仍须输出新 `signal`、真实方向、generic OI risk_mode、分数/rank、unknown 原因和实际过滤原因。不能拿旧标签过闸再在导出时改成 B 标签；否则真实训练域、short 权限、same_signal 和审计身份都会失真。

## 收益前必要反例（尚未执行）

1. 无任何 C9 native signal，但 B 周许可/FI 准备合法且 generic filters 通过：同一个 flat context 进入原 planner，产生独立 B candidate；不能因旧 signal 为空失去它。
2. 原 native long/short 合法但 B 周/FI unknown：无普通单、无 target、无 fallback；machine 当日只观察一次。
3. B 新 short 被原 whitelist 拒绝、仅 B 子类精确开放后才可进入候选；任意 `short_other` 仍不能意外开放。
4. B intent 合法但 active generic MA5/wick filter 拒绝：当天观察存在，金融 signal 清空；不反复 `on_close`、不消费 setup。改变该日更后数据不能改变既有 decision。
5. 原 signal 为空但 history 满足原 OI surge：B sizing 使用该 generic risk_mode；不能遗留 regular，不能沿用原 case 专属 mode。S 实测沿 804 long / qmt short，冻结 q 不受 D 最终 OHLC 或账户毒化影响。
6. 原持仓/旧合约仓与 flat context 并存：只替换 flat；held machine 清准备，held 技术字段/止损/roll 不变。D close 不得追溯取消 D 早前已填的 B intent。
7. 条件已分配的 slot/q 未触发：无 order/layer/费用，也不把它的预算重新给第二候选；actual gap 风险允许高于 u 预测并如实输出，不能声称过了 fill-time cap。
8. D 早段 low80、11:00 以111入场、之后 low108：holding 视图 low108；AM/history/env 保留80。缺合格完整分钟必须阻塞同一 engine，不能 unknown 或日线近似触发。
9. 同方向 B 两候选的 same_signal=1，旧 case 不同可能为0：数值推断可执行不等于分数校准有效；catastrophe/recovery 新标签不匹配必须在 provenance 可见。
10. export-only 从 B 自己 sealed snapshot 重导出，保留实际 TradeData / synthetic 母 OPEN 身份，不启动 engine。不能把 B 存成 C_TS 或加载 C 的自有 checkpoint。

以上是待新最小 hook fixture 验证的反例清单，不是已通过测试。现有 028 factory 仅接受 C_TS、031 runner/owned checkpoint/manifest 也固定 C_TS；B 必须有独立真实 arm/output/收据及相应受控入口，不能把 CLI 标签改成 B 而内部仍称 C。028 engine 的分钟队列/冻结量/真实 fill 机制没有 native case 条件，可作为共同执行部件复用；其 price_source 名称标识执行机制，不可冒充 B alpha 已被验证。两项现有 anchor 仍只授各自一 key anchor 权利；B 新增完整 session 需求必须走同一 engine 的 Stage021 精确资格，不能借 anchor 扩大 full 权利。

## 决策边界与记录

结论：机械接合可行；独立 B 信号、精确 short 权限、generic filters/OI 复用、同 context 与单次状态更新是必要最小差异。必须等 root 冻结最终合同，才可实施和运行；本文件没有授权或启动下一金融 attempt。旧 C 周/FI 参数及其历史结果保持原记录。

- 重要突破：否；本次为只读设计复核。正式参数新增/修改/删除均0；研究 B 标签/子类行为尚未实现。
- 新增/修改/删除回测结果：均无。期末权益、总收益、最大回撤、Sharpe、总滑点、成交次数、胜率：全部 N/A。
- 开始过拟合判断：否；B 是收益前预声明，未选新周/FI 参数。结束判断：否；本次只识别接合漏项，未按经济结果筛规则；既有多轮历史选择偏差仍在。
- 开始/结束继续价值：是；独立 B 尚无完整真实账户证据，且原生 planner 可以接新域；继续的价值在一次干净、可证伪的闭环，不在无限增加过滤层。下一步先冻结本文反例与新域披露，再做必要最小接合验证；任何更高净收益且更低回撤结论仍待真实金融与独立审计。


## 追加：B 收益前采用 u 已知 trigger 估价的精确接合点

追加时间：2026-10-18T03:24+08:00。root 已报告 C 的独立审计事实：100 个条件 fill 的 actual R 均高于旧 u-close 预测，最大约50倍；C 的 same-q 是既定实验口径，不能重写、重跑救参。B 的首个金融风险合同尚未冻结，root 现选择在 u 用已知 trigger T 估价，保护止损 S 仍只来自原 u bar/history。本节取代上文初版的 B close-q 建议；不从50倍反推阈值、gap额度或品种筛选。

真实接口缺口：现有 qmt `_calculate_entry_sizing`（5792）及830同名 wrapper（94）的签名均没有 `entry_estimate`。因此不存在“多传一个现成参数”即可完成的 hook；也不能把整根 `bar.close_price` 改成 T 后调用 super，否则会污染804的 S、诊断及 signal-day 身份。只在最外层 super 返回后缩 q 同样太晚：cluster/heat/env、830 gate、模型的 margin/equity 特征已沿旧估价计算，不能称原 cap 链条保持一致。

最小可信插入位置是 **830 的 super 链条以下、qmt sizing 的价差/保证金算术以前**。建议新研究策略增加一个明确的 pricing 基类，作为与原847链共享 qmt 基类的第二继承分支，让其 `_calculate_entry_sizing` 排在772之后、原 qmt 方法之前；这样830 wrapper仍包住新 sizing，804 `_entry_stop_price` 仍优先生效。只复制这一受SHA约束的方法，原算法/门序不变，显式增加 `entry_estimate` 标量读取，替换三处估价：fixed-size分支的局部 price（5864）、risk-budget分支的 risk_per_contract（5985）及 margin_per_contract（5992）。这是源码可定位的最小结构改动，尚未实施或验证实际 MRO；后续必须用最小反例确认830的 super确实进入新方法、stop调用仍进入804。若不允许这一研究专属方法拷贝/显式新入口，当前API就是实际阻塞，不能宣称纯wrapper已完成。

接合合同建议：先在B单次收盘观察/通用过滤后，把 `(u,contract,direction)→T` 注册给 sizing；新B flat-entry缺该T须拒绝，不回退close。bar/history/signal_data及 `_entry_stop_price(direction,原bar,原history,True)` 全部不变。仅取 `rho_T=max(abs(T-S)*size,原min_risk)`、`margin_T=T*size*原margin_ratio`；原 risk_amount、`int(...//rho_T)`、保证金/单笔资本整数上限、cluster→heat→env→830 wrapper→原batch rank/tilt/incremental gate顺序与原产品循环预留位置继续使用这些一致字段。原 `_reserve_intrabar_entry`（3373）直接消费 sizing.margin_per_contract，因此可自然预留T估值；不要重复预留或在D再分配。held、add、reverse、roll与非B信号仍用原路径。实际 accepted fixed_size=0；不凭本次设计扩大固定手数模式的资格。

必须分清“保持原评分/账户顺序”与“保证close版逐项rank数值不变”：模型含margin/equity数值特征，估价变为T后输入与rank可自然变化；不能继续以close喂模型、却声称所有风险字段已按T。另原 volume tilt（4454，实际round在4635附近）位于830 cap之后，可上调q；保持原算法顺序本身 **不证明最终q是原风险预算或830 cap的硬上限**。root后续B风险合同须明确这层含义，若要求最终硬预算，必须在收益前另冻结最终约束位置；本复核不擅自关tilt、补cap或调倍率。最终 allocator q/T/S/排序与预测风险/保证金一并冻结；D实际gap仍可能比T差，实际R/保证金必须另列，不能声称T估价消除了gap风险。

必要而未运行的最小反例：u.close100、low99、high110、T111时，long S仍为max(99,98)=99，rho按12*size而非1*size；反向short对称检查。改变T须改变风险/保证金估价但不能改变S、signal、history或bar；D未来H/L/C/账户毒化不能改u冻结量；两B候选的incremental margin预留须使用T并保留原排序处理。固定成本、FI/周参数及旧 C/031 字节不动。

本追加只读，未写代码/测试、未新增金融结果。过拟合判断：本次不以50倍数值定参数，只修正u已知执行门槛与预算价格域的一致性；既有研究选择偏差不因此消失。继续价值：是，但下一步先由root冻结B风险合同并消除上述最终预算语义歧义，而非用接合文档替代金融证据。
