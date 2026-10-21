# Stage595：同epoch赢家新批次最小实现合同草案（一页）

时间2026-10-21 07:15 CST；line_id=`futures_full_market_long_signal_ai`，已读registry。仅设计，供root后续冻结；不写引擎、不actual、不再web、不改LINE。累计547fit/282完成cash＋1旧partial不变；财务指标均N/A。

1. **隔离与资格。** 只复制131局部执行函数，复用原纯账本/报价/指标/选择；四条A157 OWN路径复用，不重放A。u按C自己的权益、持仓和原winner判断：occupied family仅允许同actual epoch重复有效信号新增root，不换月、不挑次优。任一该family存活root stale、缺basis/报价、deferred/force/reduce、K/生命周期不支持，即阻断add或保留unknown。旧root的SL0、boundary更新、anchor、expiry、entry risk与成本基础独立不改，新root用本次N与原0.25N初损。

2. **净盈利与额度。** 同epoch剩余各root净浮盈求和严格>0：`Σ[q*M*(u不利SELLfill−entry_fill)−entry_fees*q/initial_qty−q*u退出费]`；slip已在fill，不双扣；仅资格计算，不再次向现金账收费。旧部分退出的实现利润/退出费不计入剩余浮盈；entry_fees原总额仍归原root最终净PnL。`F0_family=Σ剩余qty*各批原entry_risk`，家族剩额`max(0,.0025*E−F0_family)`；总风险.02E、保证金25%/1.1原额，浮盈已在E，旧stop变近不释放F0。

3. **u共同预算。** 只把在u已知家族/总/保证金/容量硬上限下连一手都无的add预批剔除；fresh不加此筛选，保持原实数target。其余add以家族剩余风险/本次unit risk为实数target，与fresh一起按原jointscale、allocated risk/margin/fee和整数规则缩放；缩放/容量cap后零手或取消均不重分。D严格只减不加，不用开盘退出或其他取消补钱。

| D阶段 | 精确边界 |
|---|---|
| ①开盘旧义务 | 按原优先级处理missing/deferred/force、u已定reduce、`open<=旧boundary` gap；不读low。已知开盘任何同family退出即取消add，不转fresh；原reduce资格已在u阻断add。 |
| ②冻结开盘单 | 按原open不利报价、20low、SL0、生命周期、own allocation执行fresh/add。只对合格add豁免occupied，不读Dlow/high/close，不重测D盈利。 |
| ③日内止损 | 再用Dlow逐root处理旧批与新批原boundary；旧批稍后stop不能撤销已发生的开盘BUY；新批可以当天亏损stop。 |
| ④收盘后继 | 全部存活root才标close、更新原next boundary/anchor/K，按C ownstate准备下个u。不得提前以Dclose算开盘资金。 |

4. **无add等价性。** 原u occupied规则已保证fresh与旧仓family不重叠；D手数只依u冻结订单及自己的open报价，不依别family当日stop释放额。因此四阶段下无add时每root成交参考价/数量/费用、stop、close、日末现金恒等式与后继预算应与原A普通行为数值一致。不得另加D瞬时权益/保证金闸门改变fresh；不要求fill日志顺序字节相同。最小合成边界须验证这一点；若出现取整临界导致路径差异，不能用“日志排序”掩盖，应保留旧算术或暂停，而不重跑四A。

5. **共享容量。** `G=原floor(.01*V_u/lot)*lot`，`S=全部旧同epoch剩余qty`，add上限`floor_lot(max(0,G−S)/2)`；fresh S=0退化原G/2。共享键为(account,epoch,D)，开盘守`gross_filled_before+remaining_old_SELL_reserve+2*q<=G`。旧仓卖出只将sell reserve转为已用gross，不释放BUY额度；D不得加q。风险退出不硬截以掩盖超额；缺容量/超额按原unknown保留并标相关epoch/day批次，不逐root重复发G。

**盲点与下一步。** 589只是原A路径、忽略旧S占量的乐观一手上界；冷2023支持偏2026、11unknown仍在，不能当作C真实新增成交/收益或跨周期证明。待593独审后，root才决定冻结一次至多4C cash及独立复审。本草案不签收益、不直接授权cash；不加profitR/间隔/次数/年代/产品阈值，不移老stop、不放F0。开始/结束本步按收益拟合否，长期同史择题风险高；一轮固定反证有条件价值，救参无价值。goal/production/increased_betting均false。

小决定：`outputs/stage595_multi_root_implementation_contract_draft/decision.json`。
