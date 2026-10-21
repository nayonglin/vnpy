# Stage590：原A路径重复赢家信号的一手上界——允许先筛可行性，有条件全零可免现金

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-21 07:04 CST。
- 当前模式：独立收益前逻辑/输入设计审查，非actual、非回测结果、非重要突破。
- 范围：579唯一机制的原家族/组合额度内、同actual epoch净盈利重复信号；四对照是157 OWN的2020/2023冷启动×base/stress，不是旧baseline。全六所98历史产品/95family目标及原52/AI不变，与正式C9隔离。
- 先读registry（588关闭BDI，547fit/282completed cash＋1旧partial）；只定向读579、070/131/157小源码、042转引的成本/账本纯函数和157 manifest身份/role。没有读signals/positions/daily/native等数据表。
- 本阶段fit/cash/SQL/行情GET/大cache读取全部0；只写唯一590stage及decision，不改LINE/registry、正式/生产、Git或其它agent文件。

## 裁决

**`GO_BOUNDED_A_PATH_UPPER_BOUND_PROBE`。** 先做0fit/0cash的原A路径可行性上界有价值；目前不能因为579有机制解释就直接花四本C现金。

**“四A全部合格新增候选上界不足一手且无关键unknown，所以C不可能首次分歧”有条件成立。必要补充已经root接受：新增候选的整数上界不足lot，必须在共同batch缩放、预留与任何账户状态写入之前无副作用剔除；普通A原请求集合、顺序、参数与无新增时的旧执行语义保持不动。** 否则全零只能证明没有直接新增持仓，不能证明没有挤出原A订单。上界>0则只表示“未被这个便宜检验排除”，不是C真实机会数、可成交数量或盈利保证。

## 网上/GitHub有限刷新与判断

本次实读[原Turtle规则发布页](https://www.tradingblox.com/originalturtles/originalturtlerules.htm)，页面把加仓、止损、头寸规模及组合约束作为完整系统；未再下载此前超大PDF，也不引用未读PDF数值。实读[vn.py维护方TurtleSignalStrategy](https://github.com/vnpy/vnpy_ctastrategy/blob/main/vnpy_ctastrategy/strategies/turtle_signal_strategy.py)：已有多仓时仍会发买单，而成交会更新stop，说明公开实现存在“多批次+旧仓状态变化”的联动。这里不复制其单位数、ATR间距或stop，也不把公开代码当成本线盈利证据。

判断：本次上界的有效性来自冻结本仓库的额度与确定性状态转移，不来自Turtle收益故事。579所反对的浮盈全额再投、移动旧stop释放F0、放大风险率依旧NO_GO；也不重开075—082对全体原订单的一手预过滤。本次新增的batch-neutral剔除仅针对本来不能新增一手的重复候选，普通A请求不得受其影响。

## 必须保留的净利润与账本口径

在u完成时，原持仓家族恰有原规则选出的同actual epoch重复候选；按原u资格、原family priority、原K/生命周期，不切次优epoch。force_next、减仓、stale/缺报价等状态不应偷渡成“盈利真”；按冻结规则保留拒绝/unknown。没有持仓年龄、几R利润、unit数量或距离阈值。

设同epoch剩余批次j的数量为`q_j`、原BUY实际fill为`B_j`、乘数`M_j`；u的原不利SELL填价为`S_u`、每手SELL fee为`f_sell,u`、原BUY每手fee为`f_buy,j`：

`Pi_u = sum_j q_j * [M_j*(S_u-B_j) - f_sell,u - f_buy,j]`。

只在Pi_u严格>0时满足净盈利条件。BUY滑点已在B、SELL滑点已在S，不再额外扣slippage；不把已平数量的实现利润或费用加进剩余仓，也不把原整笔BUY总fee再次扣在少量剩余仓上。它只是资格判据，不能把这个假设SELL利润再次加到E_u或新可用资金。

042 `CashLedger.enter`保存原`entry_fees=initial_qty*fee_per_lot`；部分`exit`减qty但不减这个整笔entry_fees。因此剩余BUY费是`q_rem*(原BUY总fee/initial_qty)`，不是直接扣p.entry_fees。

### 可以免读fills的精确等价

root提出用positions原entry_fill，经原042 `fee_at(entry_fill,econ,scenario)`重建原BUY每手fee。**核准，等价。** 042 `adverse_quote`返回的BUY fee正是`fee_at(实际fill,econ,scenario)`；fee_at只依赖原fill、乘数及固定scenario的fee_min/bps。本研究成本表和静态epoch经济字段冻结，故pos.entry_fill＋原multiplier＋同一本A的scenario足以重建；部分减仓不改变每手BUY成本。不需要为此额外读取fills/closed。

不得改用u价、entry_reference或新scenario；不得把该研究模型静态费率声称为逐历史日真实券商费。若绑定字段不同/缺失或不能按原round-trip精度恢复，则记录unknown，不能猜。u SELL报价仍需冻结tick/滑点规则及同epoch经济字段，不能只把u.close直接当可平价。

## F0及单候选乐观必要上界

旧仓占用按原账本：`F_family=sum(q_rem*entry_risk_per_lot)`、`F_all=sum_all(q_rem*entry_risk_per_lot)`，实际已平/减仓数量自然不再占用；但浮盈、当前stop改善、假设未来SELL均不释放旧F0。使用原u日结E_u，已含mark浮盈一次；不再额外加Pi_u。

令`r_u`为原070 NARROW `.25N`、u成本和滑点所得每手风险，`m_u`为原`1.1*u.close*mult*margin_rate`每手buffered margin；lot为冻结正整数round_lot：

- `R_family=max(0, .0025*E_u-F_family)`；
- `R_all=max(0, .02*E_u-F_all)`；
- `M_all=max(0, .25*E_u-existing_buffered_margin_u)`；
- `q_real_upper=min(R_family/r_u, R_all/r_u, M_all/m_u, entry_capacity_qty_u)`；
- `q_lot_upper=floor_to_lot(q_real_upper)`。

成本/分母有限正值、lot/cap及权益来源不明确则unknown，不把NaN/错误除法当0。E≤0、永久insolvency等原禁入另保留原规则。本上界的margin分母**仅buffered margin，不加fee**：原共同缩放就是按该量约束；D自己的margin+BUYfee检查只可能在u已分配qty_cap以下减量，不会推高它。给保证金分母额外加fee会人为收紧上界，不能用来证明不可能。

忽略其它普通新订单竞争，给这个候选独享剩余组合风险/保证金；容量用原u估计的最大entry cap，忽略旧仓或其它订单未来D容量占用，才能保持乐观。不得扣D平仓的现金流/释放后重配额度，也不得借D.low/D.close/D真实退出/成交明细来判u可行性。D.open之后的实际风控只能减量/取消，故最终新增qty≤u上界；但上界>0不能证明联合分配后仍有一手。

## 为什么全零还需要batch-neutral条件

070 `reserve_batch`先把全部候选的**实数**target风险/保证金相加计算joint_scale，再逐订单floor；131 `reserve_capped`甚至在共同scale之后才截entry cap。所以一个最后0手、但实数target>0的新增候选，也能改变其它原订单数量。

纯算术反例，不是一次运行：E=100、组合风险剩余.25，普通请求每手risk=.1、实数目标2.5手，原A取整2手。重复候选家族剩余.20、每手risk=1，单项乐观上界只有.20手（整数0）。若先把这.20风险放入batch，总需求.45，scale=.25/.45；普通请求变1.388…手、取整1，新增仍0。A和C已经不同，虽从未直接加仓。

root已确认：新增`q_lot_upper<lot`在任何batch/预留/账户状态写入前剔除；不改普通A请求集合/排序/参数，不记录会影响后续决策的候选状态。这个精确机制才适用下述归纳证明，不应在审计后又删除该条件。

### 首次分歧归纳

1. 对四个独立冷启动/成本book，各自从相同初始资金/空仓和原prewindow规则开始。
2. 假设到某u前A与C全部有效状态相同，则同输入下u权益、原持仓F0/保证金、原信号及普通请求相同。
3. 任何C新分歧只能从579新增的合格重复同epoch净盈利候选产生。若原A这时的所有此类候选均已知上界不足一手，则它们在batch和状态写入前全部无副作用剔除；普通A预算/执行请求没有改变。
4. 没有新增请求时旧退出/执行顺序也沿A，不先用D.low修改开盘资格，不调stop/风险/标记、也不D重分钱。后续同一市场输入产生相同数量/费用/持仓/权益；到下一u仍相同，和“首次分歧”矛盾。

因此在**全域枚举、无关键unknown、四本全部全零及上述无副作用合同**成立时，可签“这个精确C在冻结研究模型内不会偏离原A”，免跑四C。它不是生产成交恒等或真实最大损失保证。

若某候选上界≥lot，A路径之后的潜在加仓又会改变E/仓位/其它预算；不能继续把原A后续行静态相加冒充C路径，也不能把A路径candidate数当C真实交易数。此时probe仅给后续是否值得正式冻结C执行时序的证据，实际cash仍需另行授权，不能自动开始。

## 最少输入及输出合同

后续probe最少只需已接受157 manifest与其四OWN book的：

1. 完整冻结`signals_VOLUNTARY_RESELECT`及原u候选组织/家族优先规则；不从A真实BUY筛“重复信号”，否则遗漏被occupied拒绝的候选。保留全u/年/family，包括0候选。
2. 各A `positions`逐u剩余仓：root/event/family/product/actual epoch、qty、entry_fill、multiplier、原risk_per_lot、mark/mark_state、force_next/reduce_to_next等；各A `daily`的u E、initial_risk、buffered_margin及insolvency状态。源日期/账户/成本映射必须一致，不拿D快照顶u。
3. 同epoch冻结经济字段和原scenario成本/lot/tick/cap规则；候选u.close/N/容量已有字段优先直接复用。只有必要元数据若仅在accepted native cache，才按协议一次读取或抽取，不新增SQL/下载，不要求重播现金或原模型。

无需fills/closed、D OHLC/未来退出、回测收益归因或模型训练表。manifest为`stage157_voluntary_cash_v1`、`completed_with_metadata_continuation`，四本是OWN而非`baseline_books`，既有A unknown限制不删除。

最少输出每个候选的完整身份、u/D映射、占用同epoch/净profit与费用基础、拒绝/unknown理由、家族/组合/保证金残额、原每手r/m/lot/cap、连续及整数上界和binding约束；另按book/u月/年/family含零聚合。unknown不填0，除非独立已知硬约束确实支配到0且清楚标注这个判定；“无关键unknown”只针对能改变本次必要界/资格的未知，不抹掉原共同路径已有的历史执行限制。

结果分三种：全四本已知全零且batch-neutral满足→条件模型路径恒等/停止；至少一条正上界→仅未排除，不能报C收益或真实机会数；存在关键unknown→未识别，不签全零证明。不加“年龄/盈R/单位数”的参数搜索，不据probe分布再挑产品/年份或释放F0救机制。593由本独审在真实终态后审实际probe，当前不跑。

## 本阶段记录与反思

- 新增：本stage与小decision；策略/模型/参数实际改动0；新增/修改/删除回测结果0。
- 期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率全部N/A；目前没有测量候选数或qty，不编造结果。
- 547fit/282完成cash＋1旧partial不变，当前0fit/0cash/SQL/行情GET/大表读取。
- 开始/结束按新收益过拟合：否，未看新账户收益或扫描阈值；长期同史自适应研究风险仍高。此纯必要界不是alpha证据。
- 开始/结束继续价值：先做小必要界有价值，避免明知无一手还跑四现金；未经容量/批量中性判定直接加仓或放风险无价值。全零则按精确机制收口，有正上界也需审D时序而不是宣称成功。
- 不改LINE/registry/根总账/Git/生产，完整全98/95目标仍active，未签正式/加注/生产资格，历史研究不等今天日线。
