# Stage642：原u旧槽续接的唯一预算合同建议

- line_id：`futures_full_market_long_signal_ai`；2026-10-21 11:30 CST。只读640小decision、131/070必要源码及157小manifest；不读实际表/native/score/Y，不实现、不actual，0fit/0cash/0新Y。原A四账复用，拟议最多4C由root另冻643授权。本stage不改LINE/registry/既有记录或正式C9。
- 640已接受28/18/13/9个账户结构事件、去重28，仅说明存在触点，不证明一手或收益。本合同运行时看C自身状态，不把28个A路径事件当未来白名单。
- 刷新一份维护者一手源码：[LEAN BuyingPowerModel](https://raw.githubusercontent.com/QuantConnect/Lean/master/Common/Securities/BuyingPowerModel.cs)，实际核到订单initial margin包含fee、未完成量仍占预算、减仓与新增区别。只用作“订单/费用/占用必须单列”的结构参考，不复制其证券保证金或收益规则。

**建议GO_FREEZE_ONE_CONTRACT，以下是同一份合同，不留风险/阈值/预算变体。** 若root不能接受所列u锚的只减量虚拟额度约束，则NO_GO，不另造比例。金融上限沿原`.0025E/.02E/.25E`、buffer1.10和NARROW `.25N`。

1. **对象与u时钟。** 只在C自身原u、纯voluntary K=次D、source生命周期严格更晚、旧仓无stale/force冲突/减量/超限的原家族，取得原同u main m=1、pureK有效的唯一winner，另一真实epoch；先取原winner再相交，不next-best。保留635/639的canonical、K来源和unknown规则。不依赖后验A成交名单，不去K、不加仓。
2. **普通单先冻结。** 在C的u状态按原131 prepare/reserve_capped原样生成ordinary reservations；所有旧仓（含待K退出者）的原F0和buffered margin仍占用。ordinary顺序、比例、预算不变。replacement不进这个共同batch，不能提高ordinary可用额，也不能抢其预留；这是旧槽替换例外，不是全局释放旧仓资金后重算。
3. **每个旧槽独占。** 旧剩余数量h、原每手风险r_old，`Rold=h*r_old`；`Bold=h*mark_u*M_old*margin_rate_old*1.10`。仅本parent可用该槽。u风险槽`Rslot=min(Rold,.0025E_u)`，资金槽`Bslot=Bold`；不再加组合剩余额、不分配其他family退出资金。原ordinary已占free pool，不能把同一free pool再给replacement。
4. **u预留两腿成本。** 用原adverse_quote/fee、070 unit_estimate及真实新lot，旧SELL费估计`c_old,u=h*fee_at(mark_u)`；新每手`r_u`沿原含双边fee/slip风险，`m_u`为原buffered margin。令`f_u`为原070的fee_roundtrip_per_lot，u整数上限唯一为`floor_lot(min(entrycap_u, Rslot/r_u, max(0,Bslot-c_old,u)/(m_u+f_u)),lot)`。冻结`Ra=q_u*r_u`、`Ba=q_u*(m_u+f_u)`，不把取整余量再分配。只保留正量；不足一lot无副作用剔除，旧仓仍照K退出。滑点已在原quote/risk内，不额外记账扣一次。
5. **D两腿不可互相冒充。** 先按原旧仓循环执行旧K全平；必须确认本parent全部h手以原SELL不利报价退出且无冲突，才可使用本槽。缺行情、未平/部分平、unknown或非预定K原因不买新；禁止先买后平或同时long两月。新BUY保持原D.open、原不利quote、tick、stale-breakout、cap、lifecycle等检查。
6. **旧平仓损失只减额度。** 对本parent记`ell=max(0,h*M_old*(mark_u-sell_fill_D)+old_sell_fee_D)`，D资金槽`B_D=max(0,Bslot-ell)`。盈利对应ell=0，绝不扩大槽；u旧fee估计由D实际fee替换，不能把两者相加重复收费。old fee是旧腿真实扣款；新fee是新腿真实扣款。旧entry费既已付过，不再补扣。
7. **u锚，不取D账本授信。** 原131旧仓循环可能已使用D.low/close；不得从当时ledger.totals读取equity、日内止损释放或利润来授信。只存u快照与普通已冻预留，D仅加入已确认K平仓的ell；无需给其他旧仓重建D.open账户，不改原事件排序。
8. **固定D虚拟额度。** 对本u已经确认完整K平仓的replacement parent，`Evirt=max(0,E_u-sum(ell))`。正收益全部忽略；旧费随ell只计一次。只称它为u锚的预算收缩，**不声称真实D各时点/全账户都满足硬cap**，也不是新的可分配资金或真实ledger权益。其他退出、ordinary取消/缩量和盈利都不进入可用额。
9. **每槽D自身只缩量。** `R_D=min(Ra,.0025Evirt)`，`B_D=min(Ba,max(0,Bslot-ell))`；用新D.open的原070 unit_estimate得到`r_D,m_D,f_D`，`q_self=floor_lot(min(q_u,R_D/r_D,B_D/(m_D+f_D)),lot)`，再保留原报价/cap/lifecycle执行检查。这样u已冻结old fee先从槽中预留，D改用含实际old fee的ell后取min，不会把估计old fee再扣一次，也不因盈利/少收费扩大quota。
10. **可用槽只算一次。** ordinary原allocated risk和`allocated_buffered_margin+allocated_fee`仍全额保留；取消也不退款。非replacement旧仓保留u原F0/M占用。仅本轮已完整K平仓且q_self>0的parent允许移出旧Rold/Bslot；其余父槽仍占用，不转授。令这部分固定占用为Rother/Bother。不存在同family旧long和新long同时借槽；原free pool已给ordinary，replacement只用自家旧槽。
11. **一次共同缩量，无循环。** `Rfree=max(0,.02Evirt-Rother)`、`Bfree=max(0,.25Evirt-Bother)`；所有q_self>0的replacement共同`scale=min(1,Rfree/sum(q_self*r_D),Bfree/sum(q_self*(m_D+f_D)))`（零分母原约定1），q_D=floor_lot(scale*q_self)。这是固定u snapshot/预留加已确认K腿损失的只减量预算guard，不是D全账户重估。floor/取消/未成交余额不循环；未知取消该续接，保留旧K平仓，ordinary完全不变。
12. **新root路径与来源。** 新root用原新epoch raw D.open−.25N_new,u、原low20/anchor与新effective K/source lifecycle；原BUY/SELL fee/slip独立入账。不能搬旧绝对stop、用连续调整价接续，不能保留旧root并追加手数。保存parent/root、新旧epoch、K来源、u槽、fee估计/实际、ell/Eminus及每次缩量原因。新stop重启是公开的机制行为，不伪称保持旧经济stop。
13. **四C固定结束，不救案。** 2020/2023×base/stress，原157四A不重放；0新model/label。所有原unknown及material replacement unknown留account unknown。先由root643固定原比较门、原indices及报告，独审四C；失败关闭精确合同，不改slot比例、risk、stop、选月或D收益授信。费用/资金审计不得将预留上界当实际重复支出。

开始/结束反思：本轮无新收益、无调参，合同只使用原风险数字，预算设计本身不是收益过拟合；同历史连续试验仍有选择风险。继续价值：是，仅一次精确四C能回答这28个结构触点是否值得成本；结构支持小且大量重叠，不视为28个独立收益样本或稳定优势。财务指标、实际成交和一手资格目前均N/A；本stage不授权实际。
