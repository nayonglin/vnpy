# Stage134：月份排序归因设计输入

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-18 22:25 CST。
- 独立设计，非突破；纯归因不触发正式A/B/C。无实现、行情、标签、fit/cash/SQL运行；391fit/118cash不变；只增本文件。
- 已读registry、LINE、128协议；registry展示了成绩摘要，但未据此选规则，未再读结果文件。

开始：新增按收益选参过拟合否，历史择题风险仍在。继续价值是：区分扩池、正分过滤、正分内排序，才能知道AI提供了什么。

调研采用[QuantConnect官方](https://www.quantconnect.com/docs/v2/writing-algorithms/securities/asset-classes/futures/requesting-data/universes)及[LEAN源码](https://github.com/QuantConnect/Lean/blob/master/Common/Securities/Future/FutureFilterUniverse.cs)的“先定义当时合约集合、再选具体月”分层；不照搬海外到期过滤或假设连续合约可成交。[Li等原论文](https://arxiv.org/html/1003.5956v2)说明离线评价依赖动作支持与反馈结构；这里有全部冻结动作标签，因此精确枚举优于模拟随机样本，这是本设计推论，不借其i.i.d.保证为期货收益背书。

令E为(p,u)事前合格且分数已知的全部actual_epoch，S为其中score>0；沿用全部经济、容量、anchor、退出/费用口径。只加两个均匀控制：

1. **R+：均匀选S，S空则不做。** B−R+只移除正分月内排序，是主归因；|S|=1贡献严格为0，不伪装排序样本。
2. **Rall：均匀选E，E空则不做。** B−Rall混合排序和sign，不能单独证明排名。B参与条件下，R+−Rall仅测正分月份过滤；所有E非空的product事件上再拆S空/非空，才包含“全负分时不做”的sign准入效果。后者是family仲裁前的产品诊断。

控制exact product：从u时点候选意向冻结B原有普通优先/F次序、family赢家及决策前状态，只换赢家的月份；不得从全family混抽，不让负分普通产品抢F，不因某月事后成交/闭合才纳入。每个(p,u)等权，不能让月份多的产品自动多权。

再设确定性**K**：同一B赢家产品仅当canonical∈S才选canonical，否则不做且不让F补位。逐事件B−K=(B−R+)+(R+−Rall)+(Rall−K)，分别为排序、月份sign过滤和盲选扩池差。canonical∈S层的末项最接近纯扩池；canonical不在S层是新增准入，另分canonical失格/非正分。K不是原A；原A可能选另一family成员，恒等式不能冒充账户B−A完整分解。

本轮随机重复最少为**0**：对既有own-policy成本后Y直接计算R+的sum(Y)/|S|和Rall的sum(Y)/|E|；不挑seed、阈值、基线。保留全399252母行、98目录、95family、六所及全部未观察/未成熟状态。只要正概率动作Y未知，完整期望就未知，报告已知/未知概率质量或既有合法区间；不按未来closed取交集、不将未知填0。明确“不做”的政策结果0与未知不同。

单动作均值足以回答排序是否提供条件增量；按既定时间/held范围报告，不新增择优门。它不能给复利、DD或未来占仓效果。只有要声称月份排序解释资金账户B−A改善时，才另冻结R+资金重放；手数、保证金、持仓时长使平均标签不能替代账户。届时重复数由事前Monte Carlo精度决定，不取最好随机路径；本轮无需新增账户。

结果未运行；权益、收益、DD、Sharpe、滑点、次数、胜率均N/A；策略参数无变更。

结束：新增收益救参过拟合否；历史择题风险仍有。继续价值是，仅做有限归因；未证明排序前不加注、调整B或晋级。若B−R+无稳定增量，不能归功AI排序。
