# Stage075 一次预算行为支持审计：合同冻结

- line_id：`futures_full_market_long_signal_ai`；2026-10-18 17:06 CST。沿现分支与checkout，不动正式版本。
- 这是074收益盲提案的有限可行性检查，**不是新策略、alpha、校准、优化器或金融回测**。此前073真实12fit/24cash与独审完成，累计333fit/66cash；本次不改旧门或旧结果。
- 只看预先指定的`NARROW_COMMON_primary_2020_stress`。不因其收益选择或换窗口/臂/成本，不扩大为另一套矩阵。
- 调研：[SPO原论文](https://arxiv.org/abs/1710.08005)与[Cvxportfolio维护者策略源码](https://raw.githubusercontent.com/cvxgrp/cvxportfolio/master/cvxportfolio/policies.py)支持预测和当时约束下的决策分开检查，不能证明换分配就有收益。此处只问动作空间是否存在，否决直接换solver/RL或把高分当预期人民币。

## 输入、边界与判定

1. 主数据只读取已验收的229690B `reservations.csv.gz`，SHA `23eadd5a1ac31924703bece8daf9bfb289953fb6b3110b5ee4205920fa6b19cf`。可读绑定的cash/model manifest与072审查receipt，但不重算模型。分数继承072已逐预测/执行核对的固定前向分数，只检当前CSV的u时正分数/cutoff与身份，避免重读966084预测。
2. 固定u字段白名单见协议。实际D_qty、D_state、D_unit_*、execution_date、D.open、盈亏、exit、closed/open最终状态、未来持有区间均不参与筛行、排序、证书和数量。完整预算行原ID及非proposal/减仓行都保留状态；不将它们伪造成新开仓候选。
3. 候选仅`budget_kind=new_entry`、原u已经选定且正分数的完整预留记录；一family至多一个。现有仓与原u权益、冻结风险、缓冲保证金不改变，不提前平仓/释放旧仓。拒绝、破产暂停和同family占用不是可挪用空间。没有新选品或新阈值。
4. 与原协议完全相同：个体风险上限`S=.0025*E`，可用总风险`R=max(0,.02*E-existing_risk)`，可用缓冲保证金`M=max(0,.25*E-existing_buffered_margin)`；每手风险r含kN*M及费滑，每手缓冲保证金m、lot来自保存u数值。原u没有另设独立费用全局cap，本次不偷加/放宽；仅认可既定u约束，不能认证券商资金可用性。
5. 对每个候选，用保存十进制值求最大的单候选可行整数上界：`U_i=lot_i*min(floor(S/(r_i*lot_i)),floor(R/(r_i*lot_i)),floor(M/(m_i*lot_i)))`。原数量`b_i=qty_cap`。先核原向量在这些约束内；打印精度边界或缺失必需u字段若无法识别，明确unknown，不用epsilon放宽上限。
6. **支持定义是至少一个候选可以增量一lot，允许放弃其他当日新单。** 固定event_id/budget_id字典序：先找`b+一lot`整体仍可行的直接增加；否则若有`U_i>=b_i+lot_i`，用该i增加一lot、其余新单置0作竞争重分配证书。两类都必须逐项验证原个体/总风险/保证金/lot/family约束。保存原与替代完整向量、精确额度/占用、原ID与种类；不按score幅度或未来收益选择证书。
7. 此判定是本域的完整单坐标增加存在性证明，不是只试一个donor的局部启发：因所有资源消耗非负，任意可行替代中若有某坐标增加，则把其他新单置0仍可行；若全部`U_i<=b_i`，任何可行替代都不能增加任一候选。仍然可以少买或全部不买，本审计**不否定降风险动作、其他候选域或别的信息机制**。
8. 分开披露：原共同scale<1、至少两可个体买一lot的真竞争、不可个体交易的fractional proposal拖累、取整后直接剩余额度、原cap本来一lot不可达。合法替代不等于净收益改善、机会损失或更低DD；不求最优，不算假想PnL。
9. D依旧只在每单u配额内减量/取消，不增量、不回收取消余额或当天平仓资金。这里没有实际替代执行，更不拼接新现金路径。

## 最少执行与后续

- 新增一份小分析脚本和真正边界合成检查：个体一lot不达、可直接增加、需竞争放弃、不可增加/只能减仓、未来字段不影响证书。旧suite与旧金融均不跑。
- 独立agent先反证合同/实现，root绑定最终source与protocol后由唯一owner执行一次。fresh输出、保留失败，无自动修复重跑。实际仅一遍必要小CSV，0SQL/价格/labels/fit/cash/download/大库hash/优化器/生产操作。输出保留所有u行、每候选上界/状态、每u判定和确定性证书及summary/terminal/manifest。独立review只对这批小数值与证书全面核，不重审旧金融。
- 若无支持，停止分配题，不换账本凑支持；若有支持，只接受“同一u动作可以不同”。没有分数幅度校准或收益证据，不自动设计高分加注/solver。是否值得金融对照必须另冻，不能从本结果直接跳过。
- 新增/修改/删除交易参数、金融结果均0；期末权益/收益/DD/Sharpe/滑点/交易数/胜率N/A。过拟合判断：本次没有收益搜索；历史择题风险仍在。继续价值：有，限一次小支持反证；不是更高收益/更低回撤的成果，完整goal仍active未达成。
