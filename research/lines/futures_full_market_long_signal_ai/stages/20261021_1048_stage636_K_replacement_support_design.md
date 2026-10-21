# Stage636：K日替换支持审计的字段与最小冻结建议

- line_id：`futures_full_market_long_signal_ai`；记录时间2026-10-21 10:48，Asia/Shanghai。
- 性质：承接635的独立结构设计，非重要突破。本轮仅小源码、manifest和CSV表头；不读数据行、新收益、大行情/标签/分数全表，不实现、不运行支持审计。0 fit、0 cash、0 SQL、0新数据下载。
- 只写本stage及`outputs/stage636_K_replacement_support_design/decision.json`；不改635、LINE、registry、正式C9。

## 调研与判断

本轮单次网页批次复核[CME原始换月说明](https://www.cmegroup.com/education/courses/introduction-to-futures/understanding-futures-expiration-contract-roll)及[QuantConnect维护者GitHub期货示例](https://github.com/QuantConnect/Documentation/blob/master/03%20Writing%20Algorithms/03%20Securities/99%20Asset%20Classes/06%20Futures/02%20Handling%20Data/99%20Examples.html)，沿635已定位的`liquidate(old)`、另发新合约订单结构：真实换月是两腿；新root需要自己的报价、风险和止损，feed换月不是订单。本轮不扩来源或下载工程。

**建议有条件冻结一次0fit/0cash结构审计，直接使用157四个已验收A现金回测账，而不是以233独立单手路径代替账户持仓。** 头部字段足够恢复A在u的持仓及D日完全K退出，再查同u原m=1替代意图；不足以认证替换至少一手或真实成交。没有结构支持就停止，避免先写策略引擎。

## 原源已确认的预算，避免两个0.25混淆

131从070继承，070从绑定的042继承常量；042第30行明确：`INITIAL=1_000_000; SINGLE_RISK=.0025; TOTAL_RISK=.02; MARGIN_CAP=.25; MARGIN_BUFFER=1.10`。

- 单候选未共同缩放的风险预算是`0.0025 * E_u`，即权益的0.25%。不是已持仓每个family自动获得可重复使用的新增额度。
- 组合初始风险上限`0.02E_u`；buffered margin上限`0.25E_u`，buffer为1.10。
- NARROW的`0.25N`是价格止损尺度。070每手u风险还加原双边fee和双边slippage；共同batch再按组合剩余风险、保证金缩放并按lot取整，131另受原u entry capacity限制。
- 因此单凭替代信号存在、旧仓数量>0或`entry_capacity_qty>0`，均不能声称新月至少一手可做。本次结构审计不计算新rootqty，不认证预算，不读economic/native补算。

## 最小数据清单：只复用已验收投影

路径均相对本线。decision提供来自原manifest的完整绑定；本轮只看header，未全量重hash或parse这些数据表。

| 投影 | 已见大小 | 最少白名单字段与作用 |
|---|---:|---|
| `outputs/stage157_voluntary_cash/actual_run1/signals_VOLUNTARY_RESELECT.csv.gz` | 583,263B | `event_id,mother_event_id,action_sequence_index,product_id,family_id,u_date,u_index,D_index,reference_epoch,anchor_epoch,cutoff`；`potential,label_history_ready20,N_u,entry_capacity_qty`；`source_lifecycle_index,voluntary_boundary_index,effective_lifecycle_index,effective_boundary_origin,K_state,K_date`。恢复旧entry的真实epoch、anchor与纯K来源；同时直接提供新u原main m=1意图。 |
| `outputs/stage627_full_admission_diagnostic/actual_run1/calendar.json` | 100,858B | 原calendar和其来源绑定，严格u/D/K索引与日期。不是按自然日减一天。 |
| `outputs/stage627_full_admission_diagnostic/actual_run1/mother_identity.csv.gz` | 19,563,157B | `product_id,family_id,u_date,u_index,reference_epoch`及原event/sequence身份。查旧product在u的canonical reference；不重读原129 mothers。此缓存虽无特征/标签，压缩文件仍约19.56MB，应如实计IO。 |
| 157四账户各`positions.csv.gz` | 合计245,888B | `account_id,scenario,date,root_id,event_id,family_id,product_id,epoch,qty,mark_state,stale_days,force_next,reduce_to_next`。这是原A现金回测的实际账内u日剩余仓位，不是独立单手假设持仓，更不是实盘仓位。 |
| 四账户各`fills.csv.gz` | 合计402,765B | `account_id,scenario,date,root_id,event_id,family_id,product_id,epoch,side,qty,reason,capacity_state`。D旧root完全退出证明与冲突/unknown披露；不读取价格、收益、fee/slip金额。 |
| 四账户各`reservations.csv.gz` | 合计2,085,306B | `account_id,scenario,u_date,execution_date,budget_kind,event_id`及存在时的`root_id,existing_qty,target_existing_qty,D_qty,D_state`。识别u计划的旧仓减量冲突，不重新reserve或计算新订单。 |
| 四账户各`daily.csv.gz` | 合计318,303B | `account_id,scenario,date,equity,initial_risk,buffered_margin,ever_insolvent,stale_positions`。只检查原A在u是否处于永久暂停/已超原risk或margin上限；不输出权益路径和金融绩效。 |

以上数据绑定字节合计23,299,540B，不含小manifest/源/协议；未来实际若获授权，应每源一次同buffer/hash/白名单parse，不再读取E、原score、labels_K、selected_K_literals或native。

选择157signals而不读627 E的依据：157的`signal_identification.json`记录4,365个原main selected actions；627已有`check_main`逐字检查原156选中的main动作。root接受该已验收一致性。新probe不重做选月、不再扫描26MB左右E，也不靠去掉正分后重选。若信号文件/绑定或身份一致性在实际中失败就unknown/停止，不自行补造winner。

四账户固定为`NARROW_VOLUNTARY_RESELECT_{primary_2020,cold_2023}_{base,stress}`。接受原157 manifest的`completed_with_metadata_continuation`，但继续核原terminal与资产绑定，不能因状态字符串不同误报未完成。

## 精确u/K/entry/current判定

1. **u身份与观察窗口。** 从账户`positions.date`取u，原calendar定位整数u_index，D=u_index+1；D必须仍在该账户原窗口及calendar内。窗口末u不强补D。旧root的entry-u与当前替换u不同，不要求二者cutoff相同；当前新意图必须满足原156 `cutoff_for(u_date)`。
2. **entry及纯K来源。** 位置`event_id`唯一join原157 entry signal；交叉检查root/event/family/product/epoch，不能仅按family猜entry。要求entry signal的origin精确`voluntary_calendar`，`source_lifecycle_index > K_old`、`effective_lifecycle_index = voluntary_boundary_index = K_old = D`，K已知且在calendar。`same_source_and_voluntary`和source先到不进入纯K样本。K是本线名义月份前一月首个源交易日的自愿退出，不认证交易所/账户法定到期边界。
3. **u当前旧仓可观察状态。** 要求`qty`为正整数、`mark_state=native_close`、`stale_days=0`、`force_next=lifecycle_exit`、`reduce_to_next`为空/None。非空零是计划减到0，不能按布尔false放行；不可把NaN、缺字段或解析失败当无冲突。
4. **排除K优先级掩盖的canonical冲突。** 131 `anchor_request`先判expiry，才判已有force、当前reference缺失或变化。故`force_next=lifecycle_exit`不足以排除这些变化。用entry signal的旧`anchor_epoch`，对照627母身份缓存中**旧product在当前u**的reference；缺失、空或多值为unknown，明确不同则conflict。不能用新winner的anchor替代旧product的reference，尤其ordinary/_F不同product时。
5. **u减量/暂停冲突。** 检查该root的`existing_position_reduction`reservation及position的reduce字段；u日daily按原常量判断`ever_insolvent`及已超risk/margin。base两表header无`root_id/existing_qty/target_existing_qty`列，stress两表有；未来parser必须允许可选列。若实际出现reduction行却无root身份则unknown，不能因缺列直接声称无减仓，也不为正常空集合造错误。
6. **D完成性另列，不回填u。** 旧root在D的SELL必须为`lifecycle_exit`，整数总量等于u账内剩余qty；不准用原入场总qty。任何其他old-root SELL/BUY、同family其他root成交或部分平仓分别记conflict/unknown。旧close的`capacity_state`未知单列，不能洗成已证明真实可成交。D实现的账内退出仅是事后支持证据，不是可在u预知的交易特征。
7. **新意图逐字复用。** 从原signals按`(family_id,u_index)`取得唯一原main winner，再检查另一真实epoch；不得先剔旧epoch再找next-best。核u/D/cutoff、`potential`、ready20、N有限正值、原entrycap及`D<effective_lifecycle_index`且`D<K_new`。新K若after-calendar但D严格早于已知target，只能沿原156状态表达，不伪造精确K。无原意图是known no-match；重复、缺身份、不能核时钟是unknown。经济metadata/listed/lot/报价/容量和新root资金仍未认证。

## 唯一最小冻结建议与输出层次

这只是root下一协议的建议，不是本stage执行授权。只做表连接和原状态核验，不实现新reserve/quote/stop/现金kernel。

- 以`account_id + old_root_id + u_index`为审计事件键，保留四账户原窗，不合并成独立样本。主2020与冷2023、base/stress有共同市场历史，计数相加不是更多独立机会。
- 固定漏斗：全部已持仓K计划候选 → 纯voluntary来源及u无已知冲突 → D账内完全K退出 → 原同u m=1/pureK不同epoch意图 → 未解unknown。每层均按账户、year、family、月份列支持；全95 family含0。raw key缺失、未匹配与已知不支持分开，不只展示成功行。
- 至少保留`u_planned_status`、`D_observed_close_status`和`replacement_intent_status`三列；不得只输出D成功子集并称u事前支持率。无任何替换收益、胜率、ROI/DD/Sharpe、CI或新模型。
- 如果完整覆盖下四A都没有真实账内K事件，或全部事件均没有原替代意图，且未解unknown为0，则此精确机制缺乏首次分歧支持，NO_GO，不做新现金。**unknown未解时，只能partial/unknown，不得把零已证支持当完整否决。**
- 若有结构支持，只说明值得root另行决定是否冻结一次完整现金合同；绝不等价于账户资金允许、至少一手可成交或存在净收益。

## 为何不用233标签代持仓

233及627 `selected_K_literals`确有独立child的filled/entry_date、K、timing/unknown时钟；233还验证entry_index=D及.25N风险分母。但这些是原单手路径，不含157账户是否预算拒绝/已被其他root占用/按资金缩量。627小投影也没有entry_index或source_lifecycle。它们可以描述独立路径到K的支持，不能认证本机制所需账户旧仓；本次最小冻结完全不需要再读它们。已知的quote_K分支并不解决组合资金、单手lot或真实报价资格。

## 结果与反思

- 本轮新增/修改/删除策略参数及源码：均无。输出是设计记录和小decision。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率：全部N/A；没有读取或生成新金融结果。
- 运行前/后过拟合判断：本轮0实际、没有看新收益或改变选月，设计本身不新增拟合；序贯候选研究仍有选择风险，后续仅核结构并在零支持时停止，不能以新阈值救案。
- 继续价值：**是，仅一次0fit/0cash支持审计有价值**，能以现成约23.3MB投影拒绝没有实际触点的执行设想；本轮不授权实跑。正支持也只进入后继合同决策，不保证alpha。
- 不更新LINE、registry、总账或正式C9；635保持原样。
