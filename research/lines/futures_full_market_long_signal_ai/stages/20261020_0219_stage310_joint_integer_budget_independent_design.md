# Stage310：联合整数预算独立复核，条件GO，不是先到先得修bug

- line_id：`futures_full_market_long_signal_ai`；2026-10-20 02:19 CST；非重要突破、非正式A/B。
- 从registry仅读线名/line_id，静读303及070/131/042/157必要函数。未读306/307新成绩或全历史收益；0实现、0大表/标签/价格/SQL、0fit/cash、0求解器运行，只新增本文，不改303/LINE/registry。
- 开始判断：同史择题与score幅度误校准风险存在；核预算机制和可冻结性有价值。本题已由303在本轮OI结果前提出。

## 独立判断与原核事实

**条件GO：值得另冻一次0fit/最多4cash的完整分配政策反证。原核不是先到先得，没有发现此类bug。** 不引入新信息、标签、Kelly、协方差或期限模型；本记录不授权本轮allocator实施/现金。

[070 reserve_batch](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage070_policy_kernel.py:55)对全部候选先算`.0025E/r_i`，统一scale后分别floor到lot；风险/保证金/费用仍按实数target冻结。[131 reserve_capped](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage131_contract_choice_kernel.py:47)只裁qty_cap，不重分余量。[D执行](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage070_policy_kernel.py:73)只能在各单自己的冻结额度内减量，没有前单先占全局余额的递减闸。循环顺序不等于先来抢钱；实数统一比例对排列不变，尚未执行浮点临界floor排列审计。

[042 family规则](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage042_cross_session_experiment.py:140)仍先排occupied/经济不合格、普通优先F、再产品/epoch确定，不跨family比score。Ledger F0是entry risk_per_lot×当前qty，不因抬stop或浮盈释放。303对此判断正确；旧ONE_LOT_PREFILTER、固定log目标及未定义大组合方案的关闭边界不变。

## 一组可冻结政策

仅复用原纯COMMON52的156同K完整choices/score与157信号，不使用OI候选。新账本在**自己的**u权益/持仓状态上执行原prepare/scale；仅原accepted批次至少2个不同family且原`scale<1`时换算子，其余沿旧核。不先删不足一lot者再重算scale，不抄旧账户历史触发集。后续占用/可执行集合可因数量路径自然不同。

`L_i`为每lot组含多少手，`k_i∈Z≥0`为lot组数，**`n_i=L_i*k_i`才是手数**。`d_i=.25*N_u*M_i`，`s_i`为冻结净R预测，`r_i=d_i+u双腿费滑`，`m_i=1.1*u_close*M_i*margin_rate`，`f_i=原roundtrip_fee`。

```text
maximize Σ n_i*s_i*d_i
n_i=L_i*k_i，0≤n_i≤原u entry_capacity_qty_i
n_i*r_i≤.0025E                     各family未缩放风险上限
Σ n_i*r_i≤max(0,.02E-F0)           原持仓F0不释放
Σ n_i*m_i≤max(0,.25E-M0)           M0是原buffered margin
```

净R已含成本，目标不能再扣fee/slip；r的成本只作资源约束，m只含buffer margin。原上限、F0、family占用、普通/F优先、容量、K/anchor及退出不变。原[131信号](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage131_contract_choice_cash.py:97)已保留score与自身N，无需新预测。`score*d`只恢复净CNY量纲，原成熟first-exit预测并非校准好的K资金期望，不称组合最优或因果利润。

## 预定工程精度与数值最优性

**δ=10⁻⁶ CNY格网是拟冻结工程政策，不是unique optimum，也不是数学exact oracle。** 以u原float64结果的roundtrip十进制字符串作Decimal输入：每lot资源`A_i=ceil(L_i*r_i/δ)`、`B_i=ceil(L_i*m_i/δ)`；原各family/risk/margin额度向下floor；容量按L整除。主目标`C_i=round_half_even(L_i*s_i*d_i/δ)`。

优化这一明确保守离散版本，不能声称等价于未量化实数式。资源ceil/cap floor不越原上限，但临界lot可能排除，须披露；目标误差界`δ/2*Σk_i`，资源保守差小于`δ*Σk_i`。不因结果改δ。

- 列序固定`(family_id,product_id,reference_epoch,event_id)`。SciPy milp取整数变量、非负有限界、`presolve=True,mip_rel_gap=0`；同批主解及所有tie阶段合计最多10秒/100000 nodes。异常/限额/证据不满足，整候选失败保留终态，不能换solver、放gap、重试或回退贪心继续账本。
- 保存完整系数/约束/原u输入、版本/options/status、原x、最终k、fun/dual bound/gap/node/time。x距整数≤10⁻⁷才取整，再用Python整数核所有约束与主目标，资源不允许正向容差，并核原未量化cap不超。系数及可能的目标/资源整数和绝对值须<2⁵⁰，超界unsupported，不暗缩单位。
- 主解及tie解须status0/success、finite bound、mip_gap=0；重算目标与fun一致，min incumbent到dual lower bound的绝对差在`[0,0.5)`个目标格内。若所有个别上界已联合可行，可用非负C给出全上界的解析最优证据。否则仅有可行incumbent不足。
- 主目标最优整数值O固定后，以`ΣC_i*k_i=O`约束，按列序逐个最大化k_i并固定前缀，选lexicographically最大k；每阶段同样核验，共享同批总计算预算。不用epsilon扰动主目标或输入行序碰巧决定并列者。

这些是**solver数值最优性证据，不是形式化精确证明**。若必须要求未量化r/s/m的数学exact解，SciPy double接口不足以签发该强主张，应停止强版本。不能用status0掩盖这个区别，亦不沿precision/tie/计算限额作meta优化。

## 整数冻结会改变D行为

新u按n冻结`qty_cap=n,allocated_risk=n*r,allocated_buffered_margin=n*m,allocated_fee=n*f`。f仍供原D的margin+entry_fee约束，不再加进m/主目标。D仍只减/取消，不跨单回收余额，不在u用未来D价优化；原reductions和已持F0照旧，不借尚未兑现的减仓释放额度。

旧核在floor/容量后仍保留实数target预算缓冲，新整数额度可能令D更早减量/取消。因此是**联合整数+score目标+整数冻结额度**的完整政策，不是纯score因果，也不能全叫“修浪费”。即使新旧n相同，D额度未必同；只有包括所有冻结额度/执行输入的完整身份相同，才可独立核等价skip，不能仅比selected或qty。

## 最低必要fixture（本阶段只设计，未写/未跑）

1. **穷举tiny最优/lot/目标**：r=m=1000、每family风险cap2500、剩余R/M各3000；A lot2、B lot1，容量均2手，d900，score .5/.1。旧scale .6后qty(0,1)，新最优n(2,1)、k(1,1)、目标990。另两资源手算反例：A(r,m,v)=(2,3,4)、B=(3,1,5)、C=(1,2,1.9)，各最多一手、R4/M3；score/r贪心先A得4，B+C最优6.9。期待值由独立枚举而非被测solver生成。
2. **tie/排列/precision**：两个同价值/资源、只能选一个的family，反转输入仍选冻结lex向量；δ边界验证资源ceil、cap floor、原cap不超、零可行解，枚举核主目标和tie。
3. **触发/F0/D缓冲**：scale1、单family及occupied/overcap沿旧路径；F0不因浮盈/抬stop释放。固定u与较差D价验证只减、无跨单回收，并包含旧实数target尚可支撑而新整数冻结需减量的例子。

三组足够，不跑旧suite或铺新优化框架。不能拿真实native批次代替tiny。

## 公平比较、依赖与停止

未来若root另冻并授权：0fit，最多候选2020连续/2023独立空仓×base/stress四本新cash，原157四控制只读、0重放；100万初资及原末日/日历/全98母域固定。完整递归新权益/占用/D路径，不加总旧拒单事后PnL或冻结旧成交集。两stress期末权益严格更高且DD严格更浅才有探索性支持，base/原配对每日log区间如实报告；利用率不是通过门。

保留完整批次/无变化批次、family/年份、u可行解及同状态旧公式反事实、D减量/取消、费用滑点、集中度、开放/stale/执行unknown与正财富。任何actual须独立agent审新政策数学、账本、统计/未知与bug，不重训/重放旧控制。无触发/经济等价/金融门失败就关闭固定包，不救risk、score温度、精度、tie、阈值、相关性、期限或目标；不授PIT、盘口、窄损安全、加注或生产资格。

本机仅find_spec和metadata确认SciPy1.17.1，未import求解器/安装/运行问题。恰两维护者页：[当前milp](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html)、[1.17分支](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.optimize.milp.html)，核double接口、time/node/gap选项和status/dual bound返回。当前网页1.18不是升级指令，本机功能留将来tiny验证，不重复303论文。

新增/修改/删除实现、实际参数、回测结果均0，权益/收益/DD/Sharpe/滑点/交易/胜率N/A。结束过拟合：新增按306/307成绩调参否，同史适应性风险是。继续单一机制反证有条件价值，称先到先得修bug/纯score因果/扩meta优化无价值。root当前完成305—309，本记录不授权额外cash，不改303/LINE/registry，完整用户目标未完成。
