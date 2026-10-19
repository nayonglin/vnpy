# Stage038：原风险预算与真实开盘复核合同（独立只读意见）

时间：2026-10-19 18:15（Asia/Shanghai）。研究线：`futures_trend_full_market_noai_one_lot`。本记录不修改旧冻结代码、源账本或LINE，不运行金融回放，也不代表尚未落盘的新实现已通过审查。

用户新指令是“必须在原风险预算内，一手超预算就不开”。应恢复fixed_size=0，原生全部筛选/预算/资金门所得数量只能向下封顶1，任何后续floor/recovery/rollover路径不能把已拒绝0恢复1。保持min_position_size=1只是禁止分数合约，不授权把0取成1；native min_risk_per_trade是货币预算参数，不能与错误数量保底混淆而删除。

## 原生预算链

native按risk_mode选择regular/breakout/ma_cross_breakout/OI等risk_ratio；预算是 `min(max(limited_balance×risk_ratio,min_risk_per_trade),max_risk_per_trade)×effective_multiplier×overheat_scale×directional_30d_multiplier`。effective_multiplier已包含streak及恢复/OI等模块的最终结果。limited_balance是“可用sizing_equity扣真实/预留保证金”与“资本使用比例预算扣保证金”较小值，sizing_equity还可能受static/dynamic/layered cap影响。

因此真实填单不可简单取equity×0.018，也不可再把已包含的multiplier乘一遍。env/portfolio等weight在native中有些是数量门，不能不加区分重复乘到risk_amount。应记录最终risk_budget sizing snapshot，先确认它已经通过所有后置volume门，selected>0，再cap1。

## 真实开盘闸门

填单前先定位当前state中contract、direction、原始signal时间匹配且entry_price_synced=False的唯一1手layer。用其当前因果有效stop与真实bar.open计算货币风险，不能用signal close距离，也不能先把entryprice写入实际仓位再检查。方向校验：long必须open>stop>0，short必须0<open<stop；已越stop的新开意图应取消，不能用abs把无效stop方向伪装成可接受风险。

一手风险按native最小tick风险口径：`max(sign×(open-stop)×size, max(tick×size,1))`。有效预算必须绑定这一原始intent的最终risk_amount（诊断target_risk_amount）；缺失、非finite、<=0、重复匹配都fail-closed，不得回退固定一手、base资本、默认1.8%或某个最新同合约历史行。恰等于预算可允许，超过预算拒绝（只用数值舍入容差，不设经济放宽）。

建议原signal最终risk_amount作为不可上调的授权上限。如果同时对当前开盘资金重算预算，取原预算与当前因果资金重算结果的min；重算应是纯账户函数，保持原risk_mode及已确定的因子，并明确静态/dynamic cap规则。不得调用整套on_bars或重新喂当天close/high/low/AM来“重算”，否则引入未来。不得只按equity比例缩放原预算，因min/max clamp与预留保证金非线性。

当前资金使用已验证的prepare_opening_risk：settled balance加旧仓到今日真实open的holding leg、再扣已真实发生的费用；旧仓缺正量报价用已知前值。不能把未成交close或state已清空当保证金释放，必须以实际pos为底；前一close真实成交后才可释放。当前权益<=0不得沿用native某些`or base_capital`回退。

不要按实际fill重新挪动原stop来凑预算，也不能用当日收盘才形成的新ATR中点给入场闸门降risk。pending延迟重挂保留原signal/layer预算，order_reissue_datetime单独记录。必须覆盖rollover_reopen的所有OPEN，不只是flat-entry；新合约无正当risk_budget记录就不能默许以旧合约风险/数量替代。

## 拒单与审计

在pos、entry-sync、trade/fee记账改变前拒。cancel order、set target0，清理且仅清理匹配的未成交layer、pending_active intent与pending_entry_diagnostics关联；保留诊断并标rejected而非假装从未生成。已存在真实仓位与pending close不得被清理，实际保证金仍保留。移除预算缓存须按intent而非只按vt，避免误删重挂/后续新signal记录。

最少审计字段：original intent/layer id、signal datetime/order id、reissue datetime、fill day/open、effective stop、contract multiplier/tick、signal risk ratio/multiplier/final budget、当前开盘equity/actual margin、可用预算、fill stop-risk、volume=0/1、拒绝理由。之后实际成交entry_risk必须与这些填单前记录吻合。

## 边界与建议回归

应覆盖信号内预算但gap后超预算拒；同日close任意变化不改变开盘决策；long/short镜像；恰等预算与超小量；native0在所有wrapper后仍0；缺budget/stop/size/price和eq<=0；stop方向无效；重挂原identity；rollover不绕过；两个OPEN顺序占用真实资金；未成交平仓不释放；reject后无假持仓且不抹真实仓。

原生stop-distance预算一般不含未来未知滑点/退出价，实际已发生费用应扣权益并另列，不应暗中发明新的极端成本模型。止损距离风险是计划情景，日线close触发/下一open成交、跳空/涨跌停/缺价均可能使实际亏损超过它，不能写成保证最大亏损。

调研：[CME仓位规模说明](https://www.cmegroup.com/education/courses/trade-and-risk-management/proper-position-size)把账户预算、止损距离与合约数量连接；[CME仓位与风险管理](https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/position-and-risk-management)区分按风险选数量与按经纪保证金可开的最大数量。本地实现应以原生实际公式为准，不套用外部固定百分比。

未新增/修改/删除任何金融结果或参数。开始与结束反思：修复用户合同语义与真实开盘前安全检查，不按2024亏损挑品种/阈值，未见过拟合操作。继续有价值；后续新实现仍需独立静态审查、合成边界验证及实际结果审查，不能由此意见直接签发PASS。
