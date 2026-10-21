# Stage128：合约月选择的容量及资金合同建议

- 时间：2026-10-18 21:25 CST；研究线 `futures_full_market_long_signal_ai`。只读设计，非重要突破；未实现、SQL、fit、现金回测、下载或修改旧材料。本文是root冻结协议的输入，不是已生效参数。
- 已读registry、Stage127、070 kernel/cash及其042报价、账本和候选选择。按brainstorming做有限方案设计；目标仍为六所全品种long，未缩成旧月池。

## 判断

推荐**新开预留完整roundtrip、退出完整审计**，暂不重写部分平仓。固定1%只是一项收益前研究约束，不是开盘盘口容量证据。为可能当日窄损预留一买一卖，能避免“一手容量开仓后必然退出超额”的内部矛盾；若后续退出容量不绑定，无需另铺执行系统。直接给全部退出硬cap会改变持仓、后续预算及风险，需要另一完整政策，不适合混入这次月份选择检验。完全不设容量则易让冷门合约制造虚构收益。

调研沿用127已查的[RBA期限原论文](https://www.rba.gov.au/publications/rdp/2017/2017-03/data-and-measurement-of-commodity-risk-premiums.html)、[德银原披露](https://www.sec.gov/Archives/edgar/data/1159508/000095010308001034/dp09574_fwp.htm)与[LEAN筛选源码](https://github.com/QuantConnect/Lean/blob/master/Common/Securities/Future/FutureFilterUniverse.cs)：月份选择是独立经济动作，但这些资料均不证明国内薄月开盘可成交或1%是最佳比例。不重查相同来源，不按收益改参与率。

## u收盘至D执行的精确顺序

1. 保留399252母表及全部 `(event_id, epoch)` 动作状态。仅u已观察、同epoch连续20日/N/low20可用、精确经济参数合格、D仍在已声明生命周期内的月份可行动；没有55日突破前筛。u必须有canonical anchor；canonical容量不足不妨碍B另选可交易月，anchor无观察则两臂保留 `no_anchor`。
2. 毛容量 `C_u=L*floor(.01*V(epoch,u)/L)`，新开上限 `E_u=L*floor(C_u/(2L))`，L为round_lot。只用u本epoch日量，为当天可能的BUY+SELL预留完整周转；C只有一手时不新开，C两手时可开一手。未知、负数、非法质量不得填0；已知不足单列 `capacity_below_one_roundtrip`。A只在canonical可行动且正分时请求；B在**E_u至少一手**的可行动月中取最高正分月，tie由root声明。不能先选0cap月再整体拒绝；全状态保留。
3. 每family最多一仓，普通/F仍合并占位；family优先级沿070（普通优先、再product/epoch），容量准入在这一步之前。选月不增加family名额。
4. 原070先按u权益联合预留，风险单位仍 `.25*N*M + 往返费 + 两边不利滑点`；单family风险0.0025、总风险0.02、缓冲保证金0.25、buffer1.10，本金100万。原联合缩放及整数化之后，`qty_cap=min(original_qty_cap,E_u)`；保留原分配的risk/margin/fee上界，容量剩余不用来重算联合缩放或补给其他家族。预算缩为0不改选第二月份。
5. D只按本月open和自身已冻结预算减量，再取u新开上限；不以D成交量放大、筛选或补仓。先处理旧仓强平/减仓/stop，再新开；同日平过family不重开。D缺价记 `entry_execution_unknown`，理想账本不生成fill，但不是已知真实零仓位；不能回找下一有价日当D。费率、tick不利成交、滑点已在成交价内、静态经济快照局限均沿070；不再重复扣滑点。

## 持仓与容量审计

初开存 `anchor_epoch=canonical(u)`，不要求held=anchor。未来每个source收盘v：自身生命周期优先；canonical(v)无观察或不同于anchor，签发下一source open退出请求；请求一经签发不因代表回归撤回。自身stop、20low、生命周期均依held epoch；不是“held≠当日代表即DAY”。缺held价继续070 stale/deferred理想清算，不宣称恢复了真实历史路径；没有代表观察也不得静默延长。

每个理想fill审计**准确前一个native calendar日D−1**的本epoch量，而非D量、前一条有价记录或母表u_index−1。若该日缺失/非法则容量未知，不回填。`C_D=floor_lot(V(epoch,D−1)/100,lot)`。每账户独立、同 `(epoch,D)` 的所有BUY及SELL毛手数累计共享一份C_D，不能买卖抵消，reduction与随后stop不能各享一份；不同模拟账户不拼接容量。当日新开再stop也累计2q。

BUY已受E_u硬约束，故当日完整stop的2q≤C_u；它不保证未来日量缩水后的退出。SELL保留070理想数量、报价和账本，逐笔记录前序消耗、参考日期/量、cap、qty和累计超额。参考未知或累计>C_D标 `execution_capacity_unknown`，不截断SELL、不延后“补成交”、不删除利润或把unknown填0。episode及账户吸收性unknown；该账户不可称全部可执行。比较的差异现金路径受影响，晋级门为unknown，不能靠理想增量通过；共同未知也不能当实盘资格。0超限只表示固定日线假设下未发现冲突。

## 权重、检验与限定

标签成熟只用自身政策的已知结果；全部月份同family留出。训练日期总权不随月份数增大：延续原family并发权重，再在同family-u的可用月份间等分，最后等权u；不按将来closed数量给预测样本准入。未知及未成熟保留，不能填0。A/B用同一个评分器及成熟训练，不训练“每月一个赢家”。

只需有限fixture：199/200量与L=2时399/400的roundtrip边界；B最高分0cap但次高可交易；D巨量不改变u cap；减仓+stop累计超限；当日BUY+SELL毛计且2q≤C；D−1缺量不回找；held≠anchor初开不触发DAY、anchor改变再回归请求仍保留；生命周期与缺价优先级；cap后预算不再分配。容量不绑定且held=anchor时应退化旧070局部执行；**A有共同容量限制后，不保证整条曲线逐点等于旧070**。

开始/结束过拟合反思：历史同数据择题风险**是**；本次按收益挑参与率**否**（尚无结果）。继续价值**是**，限一次固定月份动作检验。权益、收益、回撤、Sharpe、滑点、交易数、胜率均N/A；不加风险，不构成正式候选。
