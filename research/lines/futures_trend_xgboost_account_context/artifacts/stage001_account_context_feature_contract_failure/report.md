# Stage001 XGBoost账户组合上下文标签前可行性失败

- 决策：`stage001_account_context_prelabel_contract_fail_sparse_position_history_close_line`。
- 正式入口错误码：`candidate_activity_days_zero`。
- 首个失败：`2022-04-29 / rank11 / lc.GFEX / 120日活动0天`。
- 完整覆盖：459行/51个月；27行、16个月、11个品种的候选活动天数为0。
- 正式rank10也有4个月活动天数为0；32行、19个月在Top9下行日上的候选标准差为0。
- `2025-10-31`的Top9下行日仅18天，低于冻结合同20天。
- 结论：冻结`position_changes`是正式策略实际损益轨迹，不足以为每个未持有候选提供连续120日组合关系；六项特征无法对完整rank10..18面板定义。
- 不允许缩短窗口、补值、删除月份/品种或改相关公式；不进入Stage002，不读取账户标签或holdout，不训练XGBoost，不运行回测，不连接CTP，不调用订单API。

