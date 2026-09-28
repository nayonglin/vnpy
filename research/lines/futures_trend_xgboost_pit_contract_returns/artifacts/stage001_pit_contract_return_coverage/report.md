# Stage001 PIT逐合约收益覆盖审计

- 决策：`stage001_pit_contract_return_coverage_fail_stop_no_features`。
- 正式候选样本：`459`；完整候选窗口：`445`。
- 完整Top窗口：`415` / `459`。
- required missing cells：`5959`。
- PIT/fallback/跨合约违规：`0` / `0` / `0`。
- 本阶段只审计标签前市场数据，不读取账户边际标签，不训练模型，不运行回测，不连接CTP，不调用订单API。
