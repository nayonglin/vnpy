# Stage079 剔除不可达一手的分数预算拖累：固定模型资金机制比较

- line_id：`futures_full_market_long_signal_ai`；2026-10-18 17:19 CST。
- 原目标全市场高质量做多/窄损/更高收益更低回撤保留。075—077已真实证明159个u有合法增量空间，但没有证明分配替代能赚钱。累计仍333fit/66cash。
- 本轮只检验一个无新参数的资金机制；不是新增信息、分数校准或正式版本候选。不创建正式A/B/C，不把正式月池或生产身份流程套入用户明确独立的全市场研究；若后来有实质候选，再按version-ab-experiment和多周期要求考虑正式验证。
- 重要突破：否，当前0新fit/0新cash。本合同在本轮收益前固定，原结果与原门不改。

## 第一性原理与唯一变化

原u先给所有正分数候选相同0.25%目标风险的分数手数，再按总风险/保证金统一缩放、向下取整。即使某候选原约束下一手永远不可达，其分数手数仍参与缩放分母，可能压低其他可交易候选。审计发现317个候选个体一手本来不可达；不能把这些候选靠换分配变合法，但可以检验它们应否消耗其他候选的分数预算。

[SPO原论文](https://arxiv.org/abs/1710.08005)与[Cvxportfolio维护者策略源码](https://raw.githubusercontent.com/cvxgrp/cvxportfolio/master/cvxportfolio/policies.py)支持区分预测和可行决策，不证明这个改动有收益。这里没有可信score幅度校准，因此不按高分倾斜、不改score>0，不追求填满额度或先做整数solver。检验的是原有正分数信号能否更有效通过同一资金约束。

**唯一新规则 ONE_LOT_PREFILTER**：在原u选约/family/经济/期限/持仓/破产与超额暂停规则完成后，对本批新单，以当时E、现有冻结风险/缓冲保证金求S=.0025E、R=max(0,.02E-existingrisk)、M=max(0,.25E-existingmargin)。原unit risk r、buffered margin m、round_lot L不变。只有`L*r<=S`、`L*r<=R`、`L*m<=M`均成立，才把该候选的原实数目标S/r放入共同缩放分母。不可达行仍保留原身份/正分数/原目标与确定拒绝原因，但joint input/allocated risk/margin/fee/qty cap均0。不能将它删除出母体或改成模型负类。

对保留候选仍用原公式：总目标风险与保证金、共同scale、prefloor target、lot floor、u各单风险/保证金/费用配额。没有其他排序、再分配轮次、Hamilton/高分优先、额外一手、风险恢复或D余额回收；不调整最小手数或单笔/总风险cap。新u数量变化可能改变后续持仓与权益，必须真实独立回放，不拼原账户状态或累加局部假想PnL。

## 固定输入与4个新账户

- 固定Stage071的NARROW/COMMON完整2020+161014分数及2020/2023前向更新时钟；不消费SETTLEMENT/OHLC_PROXY，不做新fit、校准、标签构建或OI。完整399252母体、普通/F和unknown保持，只有因果ready20且score>0请求。
- 固定NARROW SL0=原D.open−0.25N(u)，Wilder20、max(SL0,causal20low)、quote取消、旧epoch强退、gap与stale/延期退出均继承070，不改entry/exit/label目标。开放不强平、unknown不填0。
- 100万元、0.25%单family/2%总风险/25%缓冲保证金/buffer1.10、base/stress成本不变；D只在该单u配额内减量/取消，不回收余款、不用当天卖出资金。已有仓risk_per_lot持续冻结，风险/保证金超额与破产处理不变。
- **只新增4cash**：2020连续/2023独立冷启×base/stress，截止2026-10-16。参考为已独审070 `NARROW_COMMON_*`对应4账户；只读取其现存daily/summary和既有bootstrap indices，不重跑基线。2026部分年，两个起点重叠。
- 一次native加载供4账户共享；0模型/labels/下载/大DB-H5 hash/旧金融重跑。加载窗口及经济来源沿已接受052 market-only bridge；不调用55或旧实验入口。

## 证据、解释与冻结停止规则

- 新实现只新增隔离工具、必要新行为检查和独审；旧070源码/结果不改，不全局monkeypatch。实现应直接沿用既有纯quote/ledger/市场定义，差异只在u reserve批次，保存每条prefilter状态、原raw target、实际joint input、scale与数量/配额。
- 只检查真正新边界：个体/剩余风险/剩余保证金一lot不可达分别为0、可达集合缩放、无剔除时与原reserve一致、保留所有记录、D配额只减不增。必要合成检查和一次独立源码复核足够；root精确SHA授权后唯一actual，失败保存无自动重试。
- 保存完整4账户fill/reservation/rejection/daily/position/closed/open、年度与所有family含零、被prefilter候选/日数与实际数量变化、费滑/换手/保证金/未决/零价情景。一次必要native数组中保存少量确定性新行为/退出路径案例供0SQL独审，不复制全市场raw数据。
- 复用同源日252块/2000次/seed20261018既有indices，比较新−原对应净log增长与DD。信息/目标没有变化，任何收益差只解释为资金机制和内生持仓路径，不叫新信息alpha。u合法也不保证D真的多成交。
- 继续该规则至少需要2020stress新收益更高、DD不更深，配对净增长CI下端>0；base同方向，2023两成本收益差非负、DD不更深。参考非空才比较DD，空参考按既定N/A；如果只多收益但DD加深、只一窗口/成本奏效、CI跨0或差异未决可以翻转，则不支持晋级。不按成绩再调过滤阈值、加score排序、改变单品种/窗口或成本救规则。
- 若规则不获支持，停止本预算可达预过滤方案；075支持证书仍有效，不把失败改成“没有动作空间”。OI的078仅作为后继信息提案保留，不同时叠加。
- 真实回测后必须独立agent全面检查新资金预算/逐笔/权益/成本/归因/置信度/bug；计算通过也不等于生产或goal完成。

## 反思与计数

本次新增/修改交易参数0，只有固定可达预过滤算法；原模型与退出参数不变，删除参数0，当前金融新结果0。期末权益/收益/DD/Sharpe/滑点/交易次数/胜率尚N/A。开始是否新增按成绩调参过拟合：否，机制由u支持证据提出，未按未来盈亏挑候选，但研究者已见旧收益，不能称全盲；本次single rule不扫参。继续价值：有，限一次0fit/4cash直接反证是否改善原目标；有空间不等于值得更大投注，目标active未达成。
