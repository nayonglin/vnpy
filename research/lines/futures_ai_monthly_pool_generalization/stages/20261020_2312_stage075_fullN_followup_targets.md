# Stage075 保留完整N的后续目标识别

- line_id：`futures_ai_monthly_pool_generalization`；2026-10-20 23:11—23:13 CST。
- 非重要alpha突破；复用已审045/002合同，未改排名边界、未知定义、成熟时钟和612训练floor。

## 调研与判断

沿用[scikit-learn概率评价说明](https://scikit-learn.org/stable/modules/calibration.html)及[上游时间切分代码](https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/model_selection/_split.py)的边界：标签数量不是有效预测或独立经验，未观察成员仍保留在月N，label_end须严格早于训练cutoff。

## 变更与结果

使用Stage073新纯证据源，完整19,698格、8,398竞争asof、8,165成熟不变；4,767条件点值使robust标签1,366→1,374（新增8：3top/5bottom），总688top/686bottom、155月份/86历史产品域。旧1,366类别全同，旧known rank区间只收窄。新标签分布于2022-06/07和2025-12/2026-01/02，5新增点值与8新增标签详细行均保存。

新增数据版/对比收据/显式AI资产角色与SHA；模型、特征、C、阈值、年度、floor和正式资格均未改，0fit。旧060target和全部历史run保留。Stage074独审全秩界、旧标签单调、时钟与floor均通过，不构成正式训练或晋级认证。

本阶段非账户回测，期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率N/A。输出`outputs/stage075_targets_followup_augmented/`。

开始/结束新增按成绩择参过拟合：否，未知保留完整N、统一数据补充；依赖同一历史行情与后验source假设，仍不能称无选择偏差。继续可靠补数据价值是，立即为8条增量重训价值否，改用冻结4738概率检验结论是否改变。
