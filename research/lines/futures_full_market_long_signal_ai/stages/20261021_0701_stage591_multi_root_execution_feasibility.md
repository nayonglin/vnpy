# Stage591：同epoch赢家新批次的最小账本与时序适配可行性

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-21 07:01 CST。
- 模式：有限只读/设计，不写引擎、不actual、不读真实大输入；非重要突破或已获现金资格。
- 已先读registry，再读579唯一机制阶段及042/070/131相关小段源码；完整98产品/95family保持，正式C9独立。
- 本轮fit/cash/SQL/native cache/行情下载/旧A重放均0；累计547 fit/282 completed cash＋1旧partial不变。

## 裁决

**CONDITIONAL_GO_U_FEASIBILITY_ONLY。** 当前数据结构可以用小而隔离的适配支持多个同family、同actual epoch的root，无需重写CashLedger或通用撮合引擎。前提是只开放579那一种重复有效信号的剩余额度请求，正确分开D开盘与日内止损，并以同epoch/同账户/同D的共享容量处理所有批次。**目前只值得root的592 u可行性probe，不授权引擎实现、fit或cash。** 若原额度与共享容量下没有实质新增手数，停止，不释放旧F0或放大风险救它。

## 一、账本已经支持多root，限制在选择和执行层

| 已核源码 | 已有行为 | 最小适配判断 |
|---|---|---|
| `stage042_cross_session_experiment.py:207–242` CashLedger | positions按root_id而非family键；enter只拒绝重复root/nonpositive qty；exit按root减量；totals逐root累加权益、保证金、F0 | 不改账本；同family可以多个root，独立entry_fill/entry_reference/initial_qty/fees/SL0/boundary/expiry/anchor |
| `stage131_contract_choice_kernel.py:101–120` prepare | 先收集occupied families、原选择函数直接拒绝；随后统一批量预算 | 不能全局删除occupied。只将原winner分类为fresh、严格合格的same-epoch add、仍拒绝三种；u每family最多一个请求 |
| `stage070_policy_kernel.py:53–84` reserve/execution_quantity | 单请求原家族目标、全批共同缩放、向下取整；D按该单allocated_risk/margin/fee与qty_cap只减量 | 仅隔离复制目标金额计算，将add实数目标上限换为家族剩余额度；共同缩放和D自有额度算法复用，不重分释放资金 |
| `stage131_contract_choice_kernel.py:59–87` CapacityLedger | audit已按(epoch,k)累计所有BUY/SELL gross，不以root重置 | 多root累计结构已具备；但audit发生在fill之后，只标unknown，不会阻止新add重复拿完整额度，必须另有add-only事前容量扣减 |
| `stage131_contract_choice_kernel.py:122–172` D循环 | 旧仓force/reduce/含D.low的stop先于pending；之后新仓再查D.low、收盘设下一boundary | 仅复制/隔离这一函数并切为四阶段；不得monkeypatch原131或挪用旧stop结果去筛开盘add |

新批次仍用本次原signal的独立event_id，现有`account_id + event_id`已可形成唯一root_id，不在旧root上改qty/平均成本。原same-epoch重复信号出自不同u，不能复用旧root ID。所有批次各自保留0.25N初损及原20low更新，不把最近一批stop、N、anchor或成本覆盖全家族。报告需区分root批次数和家族持仓周期，不能把更高批次数/胜率当成更多独立机会。

## 二、u资格、利润口径与F0

沿579：只有原u决策已选中、与已有持仓**同一actual epoch**的family winner可提add；其他月份仍拒绝，不改选次优或靠次日旧仓退出改成fresh。普通/F的原family优先级不变。正常状态下同一family只有同epoch的一组批次；若发现混epoch、basis不完整或其它不支持状态，应拒绝/unknown，不在此增加跨月策略。

u已有剩余持仓的净浮盈仅作资格判断：对每个root用原u不利SELL quote，计算

`q_remaining*M*(sell_fill_u − entry_fill) − entry_fees*(q_remaining/initial_qty) − q_remaining*sell_fee_u`，

同epoch批次求和严格>0。BUY/SELL滑点已经进入fill，不再把slippage另扣一次；这不是再次从账本扣费。已平数量的实现利润/退出费不加进剩余持仓浮盈。原entry_fees仍留在root供最终闭合净PnL，不因这个资格计算修改它。u stale、缺价/成本基础、待force/deferred/reduce、生命周期/K不合格不能当作“盈利真”；unknown状态保留。

家族剩余F0额度为 `max(0,0.0025*E_u − Σ_family remaining_qty*original_entry_risk_per_lot)`；组合剩余沿原0.02*E_u，保证金沿原25%/1.1 buffer。E已含浮盈，不把利润再加一遍；旧F0不会因盈利、当前stop位置或新增批次重设而释放。每批均从原u预算共同缩放，不能每个root新拿0.25%E。已发生的原仓部分退出自然减少剩余qty，不是由“stop更近”人为授信。

## 三、D必须按信息可知顺序分为四阶段

原131第142行用`price_exit_reference(D.open,D.low,old_boundary,None)`，并在第144行把family写入closed_today；第150行据此取消pending。原u禁止occupied，所以这没有处理过本题新add；直接删occupied后沿用会以未来D.low取消本应在Dopen发生的加仓。

建议的隔离时序如下，不引入任何盘中加仓触发：

1. **Dopen已知义务。** 对进入该日的旧root快照，只处理missing/deferred/force、原u已冻结减仓与`D.open<=old_boundary`跳空stop。缺价保持unknown。对同family已发生开盘强退/跳空stop/减仓的add可按预先冻结的保守取消规则取消；即使旧仓退出使家族变空，也不把add重解释成fresh，不将释放资金补给任何订单。
2. **冻结开盘请求。** 执行原u生成的fresh/add请求，使用原Dopen报价、不利滑点/tick、原生命周期/20low/初损/own-allocation规则；add只跳过那个有明确同epoch资格的occupied veto。禁止读取D.low/high/close、重新评估当日盈利或根据退出补钱；D只减量/取消，不能加量。若同family已有root在开盘已消失或状态不再支持，保持取消原因，不能回退到旧选择。
3. **日内stop。** 此时才读取D.low，对所有仍存旧root和刚买入的新root按各自原boundary处理。旧仓当天稍后stop不能撤回已经发生的新批BUY；新批可同日stop，不能因为这会亏而取消其开盘成交。不使用D.high排序或幻想盘中再次加仓。
4. **Dclose及下一日边界。** 统一标记存活root的D.close，然后按原next_boundary/anchor_request/K逻辑更新各自下一日状态，再按C自身权益/持仓准备后继u。不得在阶段2提前用D.close计算总权益或预算。

开盘force与风险reduce原有优先级可保留；gap与reduce同在开盘时，若后继协议决定维持旧force→reduce→gap顺序即可，关键是都不能夹入D.low。无需重建完整高低价路径，因为本题只有一次Dopen买入和之后的单向long stop，没有盘中加仓触发。

普通fresh在u没有该family持仓，且同u每family一个请求，所以D日先前别family的日内stop并不构成其合法取消条件。将这些stop延至阶段3不会赋予fresh新family机会；新机制对其它fresh数量的挤出只应来自u共同预算多了add请求。add关闭/没有add时，经济行为应与原fresh一致，原A源码和四条已验A路径完全复用，不重放A。重排fill日志可能改变跨family显示顺序及浮点累加末位，不能承诺原CSV逐字节相同；后继只需必要合成例证明现金恒等式与原规则一致，不为此跑四A或全历史引擎。

## 四、同epoch 1% gross容量要共享，不能每批发一张许可证

令原 `capacity_limits(V_u,lot)` 的第一项为同epoch、同D gross上限G；旧同epoch剩余批次总数量为S。原fresh的entry_cap近似G/2，预留新买q及当日可能退出q。add时旧批也可能在同日退出，所以新增q应至少受收益前冻结的保守限制：

`q_capacity_add_u = floor_lot(max(0,G−S)/2, lot)`，且保持原u其它风险/保证金/成交量约束。

这是为同日全部旧批SELL S +新批BUY q +新批SELL q预留，不预测哪一笔会触stop。fresh S=0时精确退化为原G/2取整规则。纯代数例：G=100、S=80，则add最多10手；若仍给新批50手，当天旧仓及新仓退出的gross可达180，明显重复授信。例子不是市场事件或回测。

执行上可继续用既有`capacity_gross[(epoch,D)]`记录已成交gross，并在add开盘前同时预留所有存活旧root的可能SELL及新q的可能SELL：`gross_filled_before + remaining_old_sell_reserve + 2*q <= G`。开盘旧仓退出的成交量已在gross里，不能又把它当作容量“释放”；后续每次SELL增加gross并减少同额预留，不再产生新BUY额度。一个账户/epoch/D所有root共享，不能root_id级重置。D允许减量，不能因为旧仓开盘卖了就提高u冻结qcap。

若原旧仓自身已S>G或容量参考缺失，add应为0/unknown，原风险退出仍照做，不为守容量强截止损数量。既有CapacityLedger是事后未知审计，原路径的未知必须保留；多批次若出现共享容量超额，应至少保持账户unknown，并明确该epoch/day关联批次的资格，而不能只凭每root单独小于G说合格。该新add约束不要求改变原A强平或既有fresh容量语义。

## 五、本轮真实网上/GitHub调研及判断

本轮真实浏览[原Turtle发布页](https://tradingblox.com/originalturtles/originalturtlerules.htm)，页面将加单位、对应止损以及组合/相关性限制列为共同规则。只核发布页，不重试579已记录超限的17MB PDF，不冒称读过其PDF正文。它支持“加仓须与风险会计一起说明”，没有证明本线加仓有效。

实读[vn.py维护者TurtleSignalStrategy](https://github.com/vnpy/vnpy_ctastrategy/blob/main/vnpy_ctastrategy/strategies/turtle_signal_strategy.py)：多仓状态仍发BUY，on_trade更新一条long_stop。它是聚合pos与共享stop的公开示例，**不是本题保留独立旧root/旧F0的可直接复制实现**；不移植其0.5ATR、4unit、2ATR stop或额外参数。

实读[维护者backtesting源码](https://github.com/vnpy/vnpy_ctastrategy/blob/main/vnpy_ctastrategy/backtesting.py)：new_bar先撮合已有limit/stop，再on_bar、更新close；bar撮合使用high/low与open给价。这强调事件顺序与bar成交假设需要明示，不能把其一般撮合顺序当作本线开盘add可预知D.low的依据。本轮不clone、安装、运行或搬入通用vn.py引擎。

## 最小下一步、NO_GO边界及反思

当前只支持root先做592：在原A的u状态测原同epoch重复信号、净盈利/unknown、家族/组合/保证金剩额、共享容量与至少一手可行性，报告时间/家族支持，不当成C实际成交或利润。C之后多root自身权益和机会会变化，不能把原A probe事件PnL相加冒充策略。

若probe没有实质可执行空间，直接NO_GO精确机制，不改family rate、释放旧F0、加速止损、取消S容量预留或扫unit阈值。若有意义，root再冻隔离预算/时序/容量与最多4C、独立review；本stage不提前授权现金。范围可以控制在一份隔离131适配加少量纯预算/资格函数及现有ledger/report复用；若实现却演变为跨月净额、多级盘中触发或重写撮合框架，则超出这份conditional GO，停止。

- 新增/修改/删除策略参数与回测结果均0；期末权益、总收益、最大回撤、Sharpe、滑点、交易数、胜率均N/A。
- 开始/结束新增按收益过拟合：否；长期同史自适应择题风险是且高。此次用代码因果顺序和可用额度限制机制，不据新收益选参数。
- 继续价值：592有限u空间核查有条件价值；未测空间先建引擎或跑cash没有价值。代码结构本身不是盈利优势，完整目标未完成。
- 只写本591唯一stage与小decision；不改LINE/registry、根总账、旧代码/数据、正式/生产/任务/Git。
- `goal_complete=false`、`production_qualified=false`、`increased_betting_qualified=false`。

决定：`outputs/stage591_multi_root_execution_feasibility/decision.json`。
