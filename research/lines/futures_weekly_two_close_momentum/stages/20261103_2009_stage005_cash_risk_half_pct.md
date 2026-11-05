# Stage005 可用现金 0.5% 按初始止损定手数

- 方案冻结于 2026-11-03 20:09 CST。研究线 `futures_weekly_two_close_momentum`，非重要突破。沿用隔离研究入口。
- B 为固定一手参照，C 为 Stage004 可用现金 2%。新增 D，仅把 C 的新开仓风险预算从可用现金 2% 降到 0.5%。各自保存完整账本。
- 19 品种、初始权益 30 万元、2015-01-01 至 2026-11-03、同一冻结数据及合约参数。均线过滤、周线触发及后续日开盘成交代理、初始止损来源、开仓排序、成本、换月手数与资金规则沿用 C。账户可用现金为开仓估值权益扣除存量静态保证金。
- 手数为 0.5% 预算除以一手初始止损距离对应金额向下取整，并受保证金及开仓成本上限约束。小于一手、开盘触及或穿越止损的信号跳过。周线确认后实际退出损失可超过初始预算。
- 校验 B 和 C 账本的复跑一致性，独立核算 D 的逐笔定量、保证金、资金和信号，重点比较开收盘资金缺口、手数及回撤。
- CME 的仓位计算框架使用止损距离及单笔风险预算，LEAN 期货模型将保证金作为独立的下单约束。沿用这两个口径的本地实现。仅验证用户指定的 0.5%，该比例是在观察 C 的风险后提出，属于样本内迭代。
- 参考 [CME Proper Position Size](https://www.cmegroup.com/education/courses/trade-and-risk-management/proper-position-size) 和 [LEAN 期货购买力模型](https://github.com/QuantConnect/Lean/blob/master/Common/Brokerages/DefaultBrokerageModel.cs)。
