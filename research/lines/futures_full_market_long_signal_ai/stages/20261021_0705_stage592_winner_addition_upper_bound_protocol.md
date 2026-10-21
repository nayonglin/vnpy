# Stage592：原额度内赢家重复信号加仓上界协议

- 时间：2026-10-21 07:05 CST；研究线 `futures_full_market_long_signal_ai`；不是重要突破，正式C9不变。
- 版本变化：新增一次0训练/0现金的必要乐观上界检查；新增参数无，修改/删除原参数无。原风险家族0.25%、组合2%、保证金25%、buffer1.1和窄止损0.25N均不变。
- 依据：589最小IO设计、590独立审查、591多批次源码可行性；根审核接受margin不加fee、原BUY每手fee可由entry_fill精确重建，以及新增不足一手必须共同batch前无副作用剔除的条件。
- 输入：原157四OWN账本与缓存signals、原经济投影；按各cutoff与原家族winner顺序。免重放A/大数据/native/SQL/下载。
- 输出：盈利有效同epoch候选数量、原预算乐观手数上界及未知。正上界不是实际新增成交，全部已知零只有满足batch-neutral合同才可免资金回测证明模型路径恒等。
- 调研判断：原Turtle发布页和vnpy维护源码均说明加仓与仓位/止损联动；不能把传统参数包直接当增益证据，本轮只检验原额度能否执行。来源和边界已固定在协议。
- 回测结果：本阶段未跑；期末权益、总收益、最大回撤、Sharpe、总滑点、交易数、胜率均N/A，不删除或改写旧A结果。累计547实际fit/282完成cash与1旧partial不变。
- 开始反思：新增选参过拟合否；没有阈值扫描或未来盈亏择样。同历史反复择题风险高，仍保留。继续价值是：先排除不可能加一手的机制。
- 后续：589必要合成fixture/source-ready→root唯一actual→593独立全量审查→594裁决。未授权现金、加注或生产；总目标active。

[冻结协议](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage592_winner_addition_upper_bound_protocol/protocol.json)
