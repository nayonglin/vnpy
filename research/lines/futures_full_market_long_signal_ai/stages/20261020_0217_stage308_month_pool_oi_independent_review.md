# Stage308：滞后月份池OI份额独立总审

时间：2026-10-20T02:17+08:00；研究线 `futures_full_market_long_signal_ai`。唯一308记录，不改作者、LINE、registry或生产；非重要突破。

结论：**核心阻断0；新源、六标量、全域选择与四现金核算一致，但固定包主经济门失败，应关闭。** root真实终态305/session26644、306/session41662、307/session19950均exit0。本轮实际6fit/4候选cash、源1SQL，旧52 refit/旧控制重放0；累计 **453 fit / 246 cash**。reviewer自己0fit/cash/SQL/网络/旧suite，原全市场高质量long→窄损→加注总目标未完成。

304唯一新增量为候选真实合约在exact前一源日v=u−1、同精确exchange.product的accepted正V已观察成交月份池OI份额；普通与_F分池，canonical单边量不重复转factor。池内任一坏OI或单位unknown使整池unknown，查询缺v不carry；q0/单月q1合法，总OI0未知。没有增加log、阈值、minpool、近远月或新missing槽；六个无截距alpha1 residual scalar是唯一新拟合项。旧52、原权重/Y、K/止损/退出/风险/费用均不变。302两世界代数反例仅支持新增信息，不证明alpha或净多资金流；先验沿302/304已接受原文，本次没有追加网络探针。

源独审只读一次新compact OI NPZ及codes、一次129三identity列。独立重算全部1552456行unit state/rule、212852池和exactv映射，q/state误差0；可用1450039、unknown102417，合法q0=648/q1=7668。unknown为查询无exactlag102387、命中零总池30；源全部池中零/非有限总量431。native9520epochs、raw97产品与原母域98产品的区别保留；所有native单位known。没有二次SQL、旧OHLCV/原价重资格、大hash或来源补造。lag1不授first-seen/PIT。

六原train共1386540行各一流12列，成熟域/原w/Y直接float逐位、held sha256家族排除核齐；各fold本次q全部finite。一次COMMON26与六compact7arrays全行核验：s52和残差误差0，独立fsum正规式gamma最大差9.72e−17、z/delta最大约6.67e−16。六gamma均由各自训练得负值，不按成绩改符号或借main给held。

独立重构全部1933480score并重建K先过滤、positive argmax、ordinary/F family优先，全main/held chosen与proposed身份、选中score和12保存anchors误差0；未声称对比不存在的全row新score文件。原399252母行/98产品保留，main与held union各161014完整。对同K旧控制：**main4365→5065，changed1602=762新增+62取消+778换月；held5877→6886，changed2430=1092新增+83取消+1255换月**。selection_summary内同newscore的unconstrained-vs-K比较另列，不作为这些增量计数。

held最小5label列单流独核：known equal-u均值held0 **+0.002301555760**、held1 **+0.002643352757**，但distinctunknown分别9/22。同动作未决增量0、异动作unknown绝不填0；先family-u再equal-u。已知均值非害通过只是原129首次退出R诊断，不是共同K funded现金，也不因unknown而冒称完整held资格。main变化后仍按冻结原预算跑完整4cash，没有以heldR替代现金或新增执行门。

四新账户独立结果（胜率=closed根净PnL>0；滑点已计入fill，不能现金重复扣）：

| 账户 | 期末权益 | 收益 | 最大回撤 | Sharpe | 费用 | 滑点金额 | closed交易数 | 净胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| primary_2020 / base | 2,078,966.86 | 107.8967% | -14.2702% | 0.866549 | 61,018.14 | 162,802.66 | 1489 | 12.4244% |
| primary_2020 / stress | 1,510,716.21 | 51.0716% | -13.6766% | 0.767804 | 75,398.79 | 182,669.61 | 1038 | 12.1387% |
| cold_2023 / base | 1,547,783.88 | 54.7784% | -9.4643% | 0.984257 | 20,991.12 | 54,579.91 | 550 | 12.0000% |
| cold_2023 / stress | 1,444,736.73 | 44.4737% | -6.6714% | 1.039545 | 36,278.27 | 84,042.80 | 435 | 12.4138% |

四本×9账本各一次：Decimal tick/费滑、逐fill gross、closed/open库存与PnL、daily现金/权益/保证金、u预留/D仅减量、拒绝及容量unknown/stale守恒通过；5065新signal完整准入，未限旧4365。44年度/22paired年度及closed盈利右尾集中度由账本重算一致；2026为partial、年度为连续账户切片。四账execution_unknown均true；两primary有historical stale，cold无historical stale，均保留，不认证实盘可成交真值。费用与引用点价沿冻结接受来源核算，不重做历史价格资格。

旧157四summary/daily仅一次核曲线、0重放；两个固定070 indices各一次，4×2000 paired每日log增长分布重算，落盘差≤1.13e−17。**2023base CI=[−0.0003046464056,−0.0000480567254]全负；其余3跨0**，并非四个都跨0。主stressΔ权益 **−17,703.5045**、ΔDD **−2.317310pp**；coldstress **−81,909.09 / −0.248597pp**。四组收益均下降，两个stress回撤都更深，四个严格条件全失败。base只描述，正held均值不能覆盖真实资金反证。

置信度边界：观察成交池不是全上市月份/交易所总OI/资金迁移；历史归档/单位合同不证first-seen；静态margin、假设费滑、容量unknown与stale保留。相关动作/源日、两重叠窗口、block252 CI和长期同史择题不等于独立alpha发现。无新增按结果调参，但历史适应风险仍是。固定lag1/池/OI份额+线性offset继续价值为**否**，按304关闭，不救符号、分母、nearfar、窗口、品种、模型、label、stop或risk；303 allocator是另案、本轮未actual。

完整收据：`outputs/stage308_month_pool_oi_independent_review/receipt.json`，精确绑定305/306/307、原协议/静审、逐项核验与一次读取预算。本独审到此结束，root写309决定，不新增探针或实验。
