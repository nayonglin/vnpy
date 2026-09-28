# Stage000A 静态历史边界数据合同修订

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility`
- 记录时间：2026-09-05 07:51 CST
- 阶段性质：Stage001唯一执行前、无标签数据结构修订
- 是否重要突破：否

## 发现

- active m0005 `combined_eligibility.csv`共634行、57个快照。
- `2019-12-31`唯一快照有18个静态品种，`score_type=stage182_promoted_static18_pre_ai_boundary`，score全部为0，没有固定`fu.SHFE`卫星。
- 首个真实动态逻辑回归快照是`2022-01-28`；之后56个月均为10个模型排名品种加固定`fu`。
- 该检查只读取正式资格表的日期、品种、score_type、score、rank和top_n，没有读取交易、收益、回撤、标签或未来价格；未运行策略回放。

## 修订

- 正式基准仍从`2020-01-02`冷启动，保证2022年后的账户状态来自完整A路径。
- 2019-12-31静态边界只参与正式路径资格，不进入事件样本、未来标签、训练或skip动作。
- 动态事件按candidate记录的`ai_product_pool_signal_date`精确匹配active release动态快照；不得回填静态期LR分数。
- 覆盖门由“总数>=250、2020-2025各>=24”改为“动态事件总数>=150、2022-2025各>=24”；long/short各>=40、产品>=15保持不变。150是对12项冻结特征保留约12.5个事件/特征的最低资格门，不代表足以证明模型有效，后续仍必须purged walk-forward与真实前向OOS。
- 动态月份集合冻结为active release中的56个明确日期，首月`2022-01-28`、末月`2026-08-31`；每月必须恰为10个模型排名行加rank11固定`fu`，固定行为不进入cutoff。静态边界必须唯一且精确为18行、全零分数、无固定`fu`，否则fail-close。
- 根事件必须满足`ai_eval_date < decision_date`且`decision_date`位于`2020-01-02 -> 2026-08-28`冻结区间，先校验时序再做样本过滤。

## 边界与结论

- 标签读取0、标签构造0、模型fit/predict 0、候选回测0、holdout 0、CTP/账户/订单0、生产写入0。
- 期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率：不适用，尚未运行回测。
- 过拟合判断：本次修订本身不是结果拟合，因为只按上线材料已存在的制度切点排除无LR含义的静态行；但把最低总数降至150会提高小样本风险，因此历史结果仍不得晋级，且不得在看见实际事件数后再次降门。
- 继续价值：有条件存在；若动态事件不足150或任一年度/方向门失败，本线立即关闭，不再救援。
- 决策：`stage000a_pre_ai_static_boundary_excluded_before_unique_run_authorization`。
