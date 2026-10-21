# Stage592：actual前修正完整模型时段

- 时间：2026-10-21 07:06 CST；研究线`futures_full_market_long_signal_ai`；非突破。
- 589实施前以原156 cutoff_for和157 execute指出：primary_2020账户跨2020—2026，2023后使用2023模型；不应把账户起点误作全期固定signals.cutoff。Root实读源确认。
- 冻结v1保留；v2只纠正这条域定义，并绑定156/157原源码；账户按其保存的daily窗口取全signals，逐u按年份验证模型cutoff。所有收益/风险/费用/加仓和零手batch-neutral规则不变。
- 尚未发生实际表读取/actual；无重跑、无新增训练/现金、无结果择参。期末权益/收益/回撤/Sharpe/滑点/交易/胜率均N/A。累计547fit/282完成cash与1旧partial不变。
- 反思：新增结果过拟合否，纠正漏域防止漏掉2023后机会；历史适应性择题风险仍高。继续价值是，已有数据足以核算必要上界，先修正范围再唯一actual。
- 后续唯一授权以v2 SHA为准；独审593合并核这次scope更正，无需回放旧基准。

[v2协议](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage592_winner_addition_upper_bound_protocol/protocol_v2.json)
