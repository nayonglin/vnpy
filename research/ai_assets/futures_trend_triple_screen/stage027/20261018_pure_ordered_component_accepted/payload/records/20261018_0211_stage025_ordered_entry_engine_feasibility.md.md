# Stage025 有序条件入场的真实引擎接合可行性

- line_id：futures_trend_triple_screen。
- 当前模式：只读源码与设计备忘；记录时间2026-10-18 02:11 CST。
- 工作区/分支：`/Users/mac/Desktop/fian`，`codex/ai-training-data-expansion`，读取HEAD `67008605c`。
- 阶段性质：Stage003有序入场草稿的因果接合审查；不是正式实验协议、正式候选或生产资格，不为已接受的C0负结果救参数。
- 是否重要突破：否；是否新跑A/B：否。未编辑策略/引擎/旧工具，未预检、测试、联网、读取大行情或运行金融账户。

## 判断

隔离研究策略子类加隔离执行引擎子类能够实现“上一完成周许可→真实合约日FI2逆向准备→更晚C9信号→次交易日high+tick/low−tick条件成交”。**不能只在原`_stage827_order_context`换成交价和时间，也不能先调用原开仓分支，再在未触发时回滚。**

root提出的最小因果方案可行：u收盘使用完整可见日线、当时已知target与`weekly_cache(u)`及共同C9参数，将预算、保证金额度、手数上限、slots及排序分配到仅D有效的独立intent；D日只依冻结额度和真实fill价格向下裁量，绝不按盘中策略`estimated_equity`、可用资金、state数量或风险倍率重新分配。未触发、取消或日内止损释放的额度当日也不转给其他intent，统一到期释放。这样无需建设全组合分钟估值账本，但必须如实命名为**共同C9风险规则＋冻结前置分配/跳空仅缩量**的新执行约定，不能声称每次触发时原C9账户规则完全不变。

## 外部调研与约束

本次按root要求不联网，沿用Stage003已核资料：[Elder手册](https://6e6fa188-f273-4932-86c0-66af721f16a8.usrfiles.com/ugd/6e6fa1_60651ebd50ca4ea0bd0421f83dce9e74.pdf)、[LEAN ForceIndex](https://github.com/QuantConnect/Lean/blob/master/Indicators/ForceIndex.cs)、[Backtrader多周期](https://www.backtrader.com/docu/data-multitimeframe/data-multitimeframe/)及[高周期确认说明](https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/)。这些说明原始结构、FI公式和确认时间，不能证明本策略能盈利，也不能替本仓库决定预算、失效和分钟内排序。

FI2仍为同一真实合约epoch的`EMA2(Δclose×volume, adjust=False)`，周状态沿已冻结定义；本阶段不扫描周期、阈值、缓冲、持有天数或品种。Stage003的FI初始化/缺失重暖、B/C未知行为等尚须正式协议固定，不能由实现时临时选利好口径。

## 源码接合点与不能直接复用的部分

以下路径均位于`examples/portfolio_backtesting/`，行号为本次实际源码。

| 环节 | 真实hook/行号 | 可复用与必要边界 |
| --- | --- | --- |
| 已完成日线与原信号 | `qmt_roll_portfolio_strategy.py:1290`的`on_bars`、`:1382`构造history、`:9789`的`_generate_signal` | 原on_bars先更新AM，再产生C9信号。研究子类可对本次真实bars做独立FI/准备状态更新，原AM只让super更新一次。仅在`_build_flat_entry_candidate_plan`更新准备会漏掉没有C9信号的日子，因为该函数4099–4105直接返回None。C须严格`setup_date < C9_signal_date < eligible_fill_trade_date`。 |
| EOD native候选与预分配 | `_build_flat_entry_candidate_plan:4098`、`_plan_flat_entry_candidates:4670` | 原AI/方向/相关性/风险快照及整手公式只在u收盘调用。原planner在4691–4758分配并发slots/计划保证金，可供冻结intent预算；不能在D触发时再跑这个planner。为了最小改动，可先取本研究账户native `opened`计划再施加有序资格，并且不把被删额度重分；资格在allocator前或后的具体口径应预声明，不看收益切换。 |
| 避免提前持仓 | `on_bars:1454–1469`、`_open_position:6135–6155`、`_reserve_intrabar_entry:3373`、`_apply_state_target:6241` | 原opened立即reset/state.layers、预留保证金/slot并set_target，尚未成交就有策略层仓位。条件计划必须改存独立intent并阻止这条opened分支；不可先落layer后用“未触发平仓”补救。intent预算封存与实际持仓分开；到期未触发没有position/target/trade/费用。 |
| 条件触发队列 | `Stage827IntradayC2Engine.cross_delayed_orders:365–388` | 原队列先求全部ordinary contexts再按物理时间fill，可延伸为ordinary＋conditional-trigger＋synthetic同一heap。静态市场触发时间可由合格分钟生成，但数量及layer激活只在该事件被pop时提交；真实触发前不得造普通已持仓订单。相同时刻沿冻结serial规则，不能按未来盈利优先。 |
| 成交context | `_stage827_order_context:312–363`、`_fill_order:403–469` | 原context强制canonical首分钟open，不能作为条件entry的价格/时间context。研究分支应提供明确conditional context，ordinary close/正式换月原路径仍沿原context。触发时才创建/激活实际订单并给定冻结裁剪量，然后可复用原真实trade/成本/episode发射路径；不能调用set_target造成次日才成交或重复开仓。 |
| 实际R及母信号同步 | `Stage827._sync_open_trade:185–221`、`_sync_entry_risk_diagnostic:223–263` | 同步要求layer的signal-day与trade.signal_datetime匹配，并以实际fill更新R/实际margin。激活须保留原signal-day身份或专门覆盖conditional匹配，不能把actual-entry-date直接塞入旧字段使其匹配失败。signal/actual-entry/setup日期应分开记录；不要悄悄改变原C9首持仓日计数。 |
| 持仓初始化 | `_open_position:6108–6168` | 提供已冻结sizing_snapshot可避免再次sizing，但本函数仍用传入bar.close/high/low种子化layer，并有`max(1, volume)`。只可用u日冻结bar/stop和明确的实际fill初始化方案；不得传入D最终bar。零量必须在调用前拒绝。初始极值、signal-day年龄与actual-fill metadata要在协议中固定，不可从D全日高低推导。 |
| 0.5R与retry | `qmt_roll_intraday_execution.entry_session:77–122`、`Stage847._stage847_stop_retry_event_after_open_trade:164–337` | entry_session已按真实entry时间取后缀，实际R为`abs(fill−冻结保护止损)`；0.5R/progress及原母量重试可沿用。retry从首次stop后一根分钟开始（847:215–218），不能把条件入场前分钟算入母episode。盘中触发首bar的pre-entry open仍须特殊处理，见下节。 |

## 为何不能盘中直接重算原风险账户

`Stage502.new_bars:112–139`在cross之前已经把D完整日线安装进engine.bars。策略`update_trade:1259`调用`_trade_to_close_pnl:3430–3439`，直接按D最终close预记settled_balance；1271–1274再按同一engine.bars刷新权益与保证金，`_estimate_equity:3411–3421`及`_estimate_margin_usage:3619–3631`均读这些close。当前正式next-open路径的仓位量在前一EOD已决定，但新增盘中条件entry若重用这些字段调量，会把D最终close带进触发时决策。

保护止损也有独立问题：`_calculate_entry_sizing:5983–5993`读取传入bar.close及`_entry_stop_price(...use_day_extreme=True)`；后者9174–9194读取bar.low/high。即使把context价改成触发价，如果传入D最终bar或重跑风险快照，仍会泄漏。

最小前置分配方案不必改变这些原EOD核算公式，但必须把它们与D日条件entry决策隔离：D日的数量函数只接受不可变`intent`、实际可成交价和已知合约规格，不接受strategy或engine.bars。生命周期只在每日close更新；D日新的主力映射、日线和由D观察产生的状态，直到D close才可用于取消未成交准备/生成下一日intent，不能在cross中读取`daily_mapping[D]`或新日线反向取消D早先本可成交的旧target意图。日内交易/止损/retry对原核算的更新保留，到真正EOD才能再用于下一批u=D的预算；冻结后也不在D早盘改读`weekly_cache(D)`来补改u许可。

建议冻结的最小intent内容为：product/contract_epoch/setup_id/native_signal_id/signal日、唯一生效D、方向、周asof、FI准备日、触发价T、保护止损S、native上限q、风险金额R_budget、保证金额度M_budget、slot/排序及已知tick/size/margin约束。不能只存native手数而放任跳空扩大单笔风险。

实际量遵守`q_fill <= q_native`，再取冻结风险额度除以`max(abs(fill−S)×size, 原最小每手风险)`、冻结保证金额度除以`fill×size×margin_ratio`等共同限制的整手下取整；不把更便宜的fill变成向上加量。若量0、价格跨过保护止损或规格不可得，拒绝该intent，不强制1手。具体冻结额度采用native已用额度还是完整可用风险额，也须在实现前单一定义，不扫两套选赢家。

## 触发分钟的因果细节

多头T为已完成u日high＋有效tick，空头为low−有效tick；D只能来自原真实交易日历，夜盘按D归属。分钟达到T后，用现有`stop_fill:136–144`的跳空open/门槛与不利tick取整原则成交；不能以T固定填掉越过T的跳空，也不能套D日open作为午间触发价。

`entry_session`取`>= entry`虽已排除更早分钟，却保留整个触发分钟。当入场发生在分钟内，该bar.open属于入场前，现有`first_stop:147–161`及`stop_fill(use_open=True)`不能原样使用它来判progress/stop或做退出成交。研究override应对该conditional首bar使用实际fill作为事件起点，允许全bar不利极值在入场后发生的保守同bar止损，并对这一次退出禁用pre-entry open；不能乐观忽略首bar，也不能把已经发生的有利极值当入场后progress。真正于bar.open跳空入场的情形才保留原open-first含义。retry仍不得在首次止损同bar声称已回收。

同minute队列必须有显式依赖：母entry先于自己的synthetic stop，同bar不利stop先于无法证明的有利路径，首次stop同bar不允许retry。不同intent同timestamp只按u冻结的排序/稳定serial处理；不得通过pop顺序读取未来进展或回收额度。分钟左标签只能表明事件所在分钟，不能声称已知秒级先后；正式协议应冻结这套保守tie合同，不能仅靠临时push顺序产生意外有利路径。

原Stage847会预生成未来synthetic sequence，并写event最终状态；原finalize（Stage827:273–308）可按未来是否重试而暂留layer。市场事件预生成本身可作为离线事件调度，但**任何未来event最终状态、计数、layer/slot释放结果不得成为D日其他intent的新量或准入依据**。冻结额度整日不回收正好避免这一借道；若以后要在日内释放并重分资金，就必须另做真实时点风险账本/逐事件状态协议，不能声称这仍是本最小方案。

## 最小必要的合成因果测试（本阶段未执行）

1. **前缀不变与账户毒化**：相同u历史及D触发前分钟，任意修改D未来H/L/C、未来是否retry，直至分歧前的intent、预算、量与状态完全相同；D数量函数若访问estimated_equity、可用资金或D最终bar，sentinel立即失败。
2. **没有触发就没有仓位**：一日未到T时，pos_data、layers、target、trade/cost均不变；只有独立intent预算，EOD释放，不能当日转给其他intent。
3. **双向触发、跳空与整手**：多空镜像、夜盘/周末交易日、门槛tick、跳空不利价；量始终不超过native上限，实际R重新从fill与冻结S计算，零量不被`max(1,...)`救活。
4. **触发后才扫描**：更早分钟的stop/progress均无效；分钟内入场遇同bar不利极值时按保守规则处理，pre-entry open不得充当post-entry stop价，首次retry最早下一分钟。
5. **共同队列与固定资源**：两intent触发顺序相反、普通close/换月/0.5R事件穿插及同刻tie；实际trade按时间/固定serial，未触发或早止损的预算不提高另一intent量，未来sequence不能抢占slots。
6. **收盘生命周期与母信号**：u冻结target/weekly(u)后，把D新映射/日线改成不同值，D close前成交仍相同；到D close才按新观察取消未成交准备/变更epoch，不能retroactive取消D早先成交。无旧价接新合约；setup严格早于C9信号，过期C9信号不无限重发，母signal/entry/stop/retry只各消费一次。
7. **记账与共同路径回归**：实际fill才激活layer并正确同步signal-day、实际fill/R和episode；成交成本只计一次；D收盘策略账户/engine daily账对齐。无条件intent时ordinary/换月/已有退出保持原路径，全部scope/method/cache在异常后恢复。

这些是建议的最小验收，不是已通过证据；不写金融测试或用收益寻找实现口径。

## 结果、边界与下一步

- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：N/A；无新回测或新的PnL结论。
- 改动源码/参数/数据/生产：0；金融、网络、订单、撤单、CTP、模型拟合：0；production_qualified=false。
- 结论：最小冻结前置预算方案有条件可行，代价是未触发订单整日占用已分额度、跳空只缩量及不回收日内资金，属于显式可反证的执行约定；设计草稿不能冒称正式候选。
- 下一步若获root认可，只应冻结单一研究协议后做上述小型真实hook合成验证，再独立审查；不自动扩大B/C分支，不立即回放或补下载全上界。
- 过拟合反思：本阶段否，按源码因果约束排除泄漏路径，没有调周/FI/止损参数；已有历史重复研究的选择风险仍在。继续价值：有条件有价值，有序触发与单层周过滤机制不同，但应先证明执行正确，不能把经典名称当收益证据。
- 不改LINE/registry，不追加其他研究线或根总账，由root统一整理。
